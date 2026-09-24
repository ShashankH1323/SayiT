"""Phase 1 orchestrator: wires audio -> STT -> clean -> paste behind a hotkey toggle."""

from __future__ import annotations

import enum
import logging
import threading

import os
from wisper.config import Config
from wisper.audio import AudioCapture
from wisper.stt import FasterWhisperBackend, GroqWhisperBackend, NullBackend
from wisper.clean import RuleCleaner
from wisper.inject import paste_text
from wisper import history, sound, models

log = logging.getLogger("wisper")


class State(enum.Enum):
    IDLE = "idle"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"
    CLEANING = "cleaning"
    PASTING = "pasting"
    ERROR = "error"


_DEFAULT_STT_PROMPT = (
    "Dictating notes and speech with technical terms like Python, Git, GitHub, SQL, API, and Indian languages like Hindi and Kannada."
)


class WisperApp:
    """Toggle-driven dictation loop. State machine guarded by a single global lock:
    one utterance at a time (# ponytail: single human speaker, so no per-utterance queue)."""

    def __init__(self, config: Config, *, audio=None, stt=None, cleaner=None, paste=None):
        self.config = config
        self.audio = audio or AudioCapture(config.samplerate, config.input_device)
        self._stt_key = self._stt_config_key()  # config tuple the live stt was built from
        self.stt = stt or self._build_stt()
        self.cleaner = cleaner or RuleCleaner()
        self.paste = paste or paste_text
        self.state = State.IDLE
        self.last_text = ""   # last cleaned transcription, for the UI
        self.last_error = ""  # repr of the last processing failure, for the UI
        self._lock = threading.Lock()
        self.idle_event = threading.Event()
        self.idle_event.set()
        self._cancel_requested = threading.Event()
        self._listener = None  # HotkeyListener, set in run(); swapped by set_hotkey()

    def cancel(self):
        """Cancel recording or in-flight processing immediately: stop capture,
        discard audio, do not transcribe/paste/record. Restores state to IDLE."""
        with self._lock:
            if self.state is State.RECORDING:
                try:
                    self.audio.stop()
                except Exception as exc:
                    log.warning("[wisper] audio stop during cancel: %s", exc)
                self.state = State.IDLE
                self.idle_event.set()
                if getattr(self.config, "sound_effects", True):
                    sound.play_cancel()
                return

            if self.state in (State.TRANSCRIBING, State.CLEANING, State.PASTING):
                self._cancel_requested.set()
                self.state = State.IDLE
                self.idle_event.set()
                if getattr(self.config, "sound_effects", True):
                    sound.play_cancel()
                return

            if self.state is State.ERROR:
                self.state = State.IDLE
                self.last_error = ""
                self.idle_event.set()

    def toggle(self):
        """Hotkey callback. Must not block: recording start/stop is cheap, the heavy
        work runs on a worker thread. A re-entrant toggle while busy is ignored."""
        with self._lock:
            if self.state in (State.IDLE, State.ERROR):
                # ERROR is a resting state (see _process): a fresh toggle clears it
                # and starts over, so the stale error stops showing.
                self.last_error = ""  # clear a stale error on a fresh attempt
                self._cancel_requested.clear()
                # No usable engine (provider "none", missing Groq key, or local model
                # not downloaded) -> don't open the mic for a capture that can only
                # fail; surface the setup prompt instead. Guarding here covers the
                # global hotkey too, not just the in-app key handler.
                self._refresh_stt()
                if isinstance(self.stt, NullBackend):
                    self.last_error = (
                        "No speech engine configured — choose Cloud (Groq) or "
                        "On-Device in Transcription settings."
                    )
                    self.state = State.ERROR
                    return
                if getattr(self.config, "sound_effects", True):
                    sound.play_start()
                try:
                    self.audio.start()
                except Exception as exc:
                    log.exception("[wisper] audio start failed")
                    self.last_error = repr(exc)
                    self.state = State.ERROR
                    if getattr(self.config, "sound_effects", True):
                        sound.play_failure()
                    return
                self.state = State.RECORDING
                self.idle_event.clear()
            elif self.state is State.RECORDING:
                # Leave RECORDING synchronously under the lock so a second toggle
                # lands in a busy state and cannot spawn a duplicate worker.
                self.state = State.TRANSCRIBING
                if getattr(self.config, "sound_effects", True):
                    sound.play_stop()
                threading.Thread(target=self._process, daemon=True).start()
            # else: TRANSCRIBING / CLEANING / PASTING -> busy, ignore.

    def _process(self):
        """Worker: stop capture, transcribe, clean, paste. Success ends in IDLE;
        any failure discards the utterance and rests in ERROR (never a partial
        paste). ERROR is a resting state the next toggle clears, and the UI shows
        the error only while ERROR is current -- so it never lingers under "Idle"."""
        try:
            pcm = self.audio.stop()
            if self._cancel_requested.is_set():
                self.state = State.IDLE
                return
            # Pre-STT seam: optional denoise + silence-gate (defaults are no-ops).
            pcm = self.audio.preprocess_for_stt(
                pcm, self.config.samplerate,
                self.config.noise_suppression, self.config.input_threshold,
            )
            if pcm is None or getattr(pcm, "size", len(pcm)) == 0:
                self.state = State.IDLE  # gated as silence: skip STT/clean/paste
                return
            # Rebuild the STT backend if the engine selection changed since it was
            # built, so an in-app engine switch takes effect without a restart.
            # Unchanged config keeps the existing backend (and any loaded local model).
            self._refresh_stt()
            try:
                raw = self.stt.transcribe(
                    pcm,
                    self.config.language,
                    self.config.output_language,
                    prompt=_DEFAULT_STT_PROMPT,
                )
            except TypeError:
                raw = self.stt.transcribe(pcm, self.config.language, self.config.output_language)
            if self._cancel_requested.is_set() or not raw:
                self.state = State.IDLE
                return
            self.state = State.CLEANING
            cleanup_mode = self.config.cleanup_mode
            # Groq-requiring cleanup modes (light/casual/formal/structured) reach the
            # network via reform.py. Only take that path when actually on cloud
            # (groq + key); otherwise clean locally with the delete-only rule pass.
            on_cloud = self.config.stt_provider == "groq" and self._has_groq_key()
            if not on_cloud and cleanup_mode in ("light", "casual", "formal", "structured"):
                cleanup_mode = "rule"
            cleaned = self.cleaner.clean(raw, cleanup_mode, self.config.output_language)
            if self._cancel_requested.is_set() or not cleaned:
                self.state = State.IDLE
                return
            self.last_text = cleaned
            # Record before pasting: a valid transcript is saved to history even
            # if the paste step later fails, so the user never loses their words.
            history.record(cleaned, self.config.history_size)
            self.state = State.PASTING
            if self._cancel_requested.is_set():
                self.state = State.IDLE
                return
            self.paste(cleaned, self.config.paste_mode)
            if getattr(self.config, "sound_effects", True):
                sound.play_paste()
            self.state = State.IDLE
        except Exception as exc:
            if self._cancel_requested.is_set():
                self.state = State.IDLE
                return
            log.exception("[wisper] processing failed; utterance discarded")
            self.last_error = repr(exc)
            self.state = State.ERROR
            if getattr(self.config, "sound_effects", True):
                sound.play_failure()
        finally:
            self._cancel_requested.clear()
            self.idle_event.set()

    def run(self):
        """Start the hotkey listener, then run the tkinter UI on the main thread until
        the window closes. Deferred imports keep the keyboard hook and tkinter off the
        import path so the app stays testable headlessly."""
        from wisper.hotkey import HotkeyListener
        from wisper.ui import WisperUI

        self._listener = HotkeyListener(self.config.hotkey, self.toggle)
        self._listener.start()
        msg = f"[wisper] ready — press {self.config.hotkey} to dictate (Ctrl+C to quit)"
        log.info(msg)
        print(msg)
        try:
            WisperUI(self).run()  # blocks on mainloop; KeyboardInterrupt propagates out
        finally:
            try:
                self.audio.stop()  # release the mic if we tore down mid-recording (BUG 2)
            except Exception:
                log.exception("[wisper] audio.stop() on shutdown failed")
            self._listener.stop()

    def set_hotkey(self, new_hotkey: str) -> None:
        """Rebind the global toggle hotkey at runtime (called by the UI settings pane).
        On a bad hotkey string the previous binding is restored and the error is left
        in last_error for the UI; never raises.

        # ponytail: rebind stops/starts the whole hook; fine for a manual settings change.
        """
        from wisper.hotkey import HotkeyListener

        old = self._listener
        try:
            if old is not None:
                old.stop()
            new = HotkeyListener(new_hotkey, self.toggle)
            new.start()  # raises on an unparseable hotkey before we commit anything
            self._listener = new
            self.config.hotkey = new_hotkey
            self.config.save()
        except Exception as exc:
            log.exception("[wisper] set_hotkey failed; restoring previous binding")
            self.last_error = repr(exc)
            self._listener = old
            if old is not None:
                try:
                    old.start()  # re-register the previous hook (stop() cleared it)
                except Exception:
                    log.exception("[wisper] could not restore previous hotkey")

    @staticmethod
    def _has_groq_key() -> bool:
        return bool(os.environ.get("GROQ_API_KEY", "").strip())

    def _stt_config_key(self) -> tuple:
        """The config tuple _build_stt selects on; toggle()/_process rebuild when it
        changes. Includes local-model availability so a mid-session download takes
        effect (otherwise the live NullBackend would persist until restart)."""
        c = self.config
        downloaded = models.is_downloaded(c.model) if c.stt_provider == "local" else False
        return (c.stt_provider, c.model, c.device, c.compute_type,
                c.groq_model, self._has_groq_key(), downloaded)

    def _refresh_stt(self) -> None:
        """Rebuild the backend if the engine selection or its availability changed."""
        if self._stt_config_key() != self._stt_key:
            self.stt = self._build_stt()

    def _build_stt(self):
        """Build the STT backend from config.stt_provider — engines are strictly opt-in.
        Nothing loads here (FasterWhisperBackend is lazy), no GPU, no network:
          groq  -> cloud GroqWhisperBackend if a key is present, else NullBackend
                   (no silent local fallback).
          local -> FasterWhisperBackend only if the model is already downloaded,
                   else NullBackend (never triggers a download / GPU spike).
          none / unknown -> NullBackend.
        """
        provider = self.config.stt_provider
        if provider == "groq":
            if self._has_groq_key():
                groq_model = getattr(self.config, "groq_model", "whisper-large-v3-turbo")
                backend = GroqWhisperBackend(model=groq_model)
            else:
                backend = NullBackend()
        elif provider == "local" and models.is_downloaded(self.config.model):
            backend = FasterWhisperBackend(
                self.config.model, self.config.device, self.config.compute_type
            )
        else:
            backend = NullBackend()
        self._stt_key = self._stt_config_key()  # remember what we built from
        return backend

    def set_stt_provider(self, provider: str) -> None:
        """Switch between 'groq' and 'local' STT providers."""
        try:
            self.config.stt_provider = provider
            self.config.save()
            self.stt = self._build_stt()
        except Exception as exc:
            log.exception("[wisper] set_stt_provider failed")
            self.last_error = repr(exc)

    def set_groq_model(self, model: str) -> None:
        """Set the Groq Whisper model name (e.g. whisper-large-v3-turbo). The live
        backend is rebuilt lazily on the next toggle/transcribe via _refresh_stt
        (groq_model is part of _stt_config_key)."""
        try:
            self.config.groq_model = model
            self.config.save()
        except Exception as exc:
            log.exception("[wisper] set_groq_model failed")
            self.last_error = repr(exc)

    def set_model(self, name: str) -> None:
        """Switch the active local STT model at runtime. The backend is lazy -- construction
        is cheap and the weights load on the next transcribe -- so this won't block the
        caller. Failures are logged into last_error; never raises."""
        try:
            self.config.model = name
            self.config.save()
            self.stt = self._build_stt()
        except Exception as exc:
            log.exception("[wisper] set_model failed")
            self.last_error = repr(exc)

