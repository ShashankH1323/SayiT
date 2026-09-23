"""Phase 1 orchestrator: wires audio -> STT -> clean -> paste behind a hotkey toggle."""

from __future__ import annotations

import enum
import logging
import threading

import os
from wisper.config import Config
from wisper.audio import AudioCapture
from wisper.stt import FasterWhisperBackend, GroqWhisperBackend, ResilientGroqSTTBackend
from wisper.clean import RuleCleaner
from wisper.inject import paste_text
from wisper import history, sound

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
            if getattr(self.config, "stt_provider", "groq") == "local" and cleanup_mode in ("light", "rule"):
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

    def _build_stt(self):
        """Construct the STT backend based on config.stt_provider and key availability."""
        has_groq_key = bool(os.environ.get("GROQ_API_KEY", "").strip())
        local_backend = FasterWhisperBackend(
            self.config.model, self.config.device, self.config.compute_type
        )
        provider = getattr(self.config, "stt_provider", "groq")
        if provider == "groq" and has_groq_key:
            groq_model = getattr(self.config, "groq_model", "whisper-large-v3-turbo")
            groq_backend = GroqWhisperBackend(model=groq_model)
            return ResilientGroqSTTBackend(groq_backend, local_backend)
        return local_backend

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
        """Set the Groq Whisper model name (e.g. whisper-large-v3-turbo)."""
        try:
            self.config.groq_model = model
            self.config.save()
            if hasattr(self.stt, "groq"):
                self.stt.groq.model = model
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

