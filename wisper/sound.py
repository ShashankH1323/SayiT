"""Tactile mechanical keyboard bass thock auditory cues (earcons) for Wisper.

Provides audible, tactile, deep, and bass-heavy mechanical keyboard acoustic feedback:
- START: Tactile Cherry MX mechanical switch bottom-out thock when dictation begins.
- STOP: Complementary mechanical switch release / toggle thock when dictation stops.
- CANCEL: Soft, muted low-end mechanical dismissal tap (Escape cue).
- PASTE: Resonant sub-bass resolution thock confirming transcription and paste.

Outputs directly to Windows native waveOut audio session via winsound (asynchronous,
<5ms latency, non-blocking) with graceful sounddevice fallback.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
import wave

import numpy as np

log = logging.getLogger("wisper")

try:
    import winsound
except ImportError:
    winsound = None

_ASSETS_DIR = Path(__file__).resolve().parent / "assets" / "sounds"


class _SoundCue:
    __slots__ = ("sig", "sr", "path", "wav_bytes")

    def __init__(self, sig: np.ndarray, sr: int, path: str | None = None, wav_bytes: bytes | None = None):
        self.sig = sig
        self.sr = sr
        self.path = path
        self.wav_bytes = wav_bytes


def _to_wav_bytes(sig: np.ndarray, sr: int = 44100) -> bytes:
    """Convert float32 audio to 16-bit WAV bytes."""
    pcm16 = (np.clip(sig, -1.0, 1.0) * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm16.tobytes())
    return buf.getvalue()


def _synthesize_thock(freq_start: float, freq_end: float, duration_s: float, peak: float = 0.95) -> tuple[np.ndarray, int]:
    sr = 44100
    n = int(sr * duration_s)
    t = np.linspace(0, duration_s, n, endpoint=False)
    freqs = np.geomspace(freq_start, freq_end, n)
    phase = 2 * np.pi * np.cumsum(freqs) / sr
    body = np.sin(phase) + 0.45 * np.sin(2 * phase) + 0.16 * np.sin(3 * phase)
    attack = np.sin(np.clip(t / 0.003, 0, 1) * (np.pi / 2))
    decay = np.exp(-t * (36.0 / (duration_s / 0.085)))
    sig = body * attack * decay
    sig = (sig / np.max(np.abs(sig))) * peak
    return sig.astype(np.float32), sr


def _load_cue(filename: str, fallback_args: tuple) -> _SoundCue:
    wav_path = _ASSETS_DIR / filename
    if wav_path.is_file():
        try:
            with open(wav_path, "rb") as f:
                wav_bytes = f.read()
            with wave.open(io.BytesIO(wav_bytes), "rb") as w:
                sr = w.getframerate()
                ch = w.getnchannels()
                sw = w.getsampwidth()
                nf = w.getnframes()
                raw = w.readframes(nf)
                if sw == 2:
                    sig = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                elif sw == 1:
                    sig = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
                elif sw == 4:
                    sig = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
                else:
                    sig = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                if ch == 2:
                    sig = sig.reshape(-1, 2).mean(axis=1)
                return _SoundCue(sig.astype(np.float32), sr, str(wav_path), wav_bytes)
        except Exception as e:
            log.warning("Failed loading sound cue %s (%s); synthesizing", filename, e)

    sig, sr = _synthesize_thock(*fallback_args)
    wav_bytes = _to_wav_bytes(sig, sr)
    return _SoundCue(sig, sr, None, wav_bytes)


# Preload and cache all sound cues into memory at module load time (zero latency during hotkeys)
_SOUND_START = _load_cue("start.wav", (98.0, 52.0, 0.090, 0.96))
_SOUND_STOP = _load_cue("stop.wav", (125.0, 72.0, 0.075, 0.93))
_SOUND_CANCEL = _load_cue("cancel.wav", (80.0, 46.0, 0.085, 0.90))
_SOUND_PASTE = _load_cue("paste.wav", (90.0, 50.0, 0.140, 0.96))


def _play(cue: _SoundCue) -> None:
    """Play sound cue asynchronously with zero latency via native winsound; fallback to sounddevice."""
    if winsound is not None:
        try:
            if cue.path and Path(cue.path).is_file():
                winsound.PlaySound(cue.path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                return
            elif cue.wav_bytes:
                winsound.PlaySound(cue.wav_bytes, winsound.SND_MEMORY | winsound.SND_ASYNC)
                return
        except Exception as e:
            log.debug("winsound cue failed: %s; trying sounddevice", e)

    try:
        import sounddevice as sd
        sd.play(cue.sig, cue.sr)
    except Exception as e:
        log.debug("sounddevice play failed: %s", e)


def play_start() -> None:
    """Play deep mechanical switch bottom-out thock when recording begins."""
    _play(_SOUND_START)


def play_stop() -> None:
    """Play tactile mechanical switch release thock when recording stops."""
    _play(_SOUND_STOP)


def play_cancel() -> None:
    """Play soft mechanical dismissal tap when recording is cancelled."""
    _play(_SOUND_CANCEL)


def play_paste() -> None:
    """Play resonant sub-bass resolution thock when transcription completes and text pastes."""
    _play(_SOUND_PASTE)
