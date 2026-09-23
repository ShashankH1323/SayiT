"""Warm, low-frequency auditory cues (earcons) for Wisper.

Inspired by Wisper Flow's sound design: subtle, low-frequency, tactile acoustic
cues that act like the click of a keyboard without auditory fatigue. No harsh,
piercing 2-4 kHz beeps — pure warm sub-bass and resonant chords (160-250 Hz).

Outputs directly to the active system audio output device (including Bluetooth
headphones such as Rockerz 558) via sounddevice, falling back gracefully to
winsound if sounddevice is unavailable.
"""

from __future__ import annotations

import io
import logging
import wave

import numpy as np

log = logging.getLogger("wisper")

try:
    import winsound
except ImportError:
    winsound = None


def _synthesize_tone(freq_start: float, freq_end: float, duration_s: float, peak: float = 0.40) -> np.ndarray:
    """Generate a warm sub-bass sweep with soft cosine Tukey envelope as float32."""
    sr = 44100
    n = int(sr * duration_s)
    freqs = np.linspace(freq_start, freq_end, n)
    phase = 2 * np.pi * np.cumsum(freqs) / sr

    # Warm fundamental + subtle second harmonic for body
    sig = np.sin(phase) + 0.22 * np.sin(2 * phase)
    # Gentle Tukey / cosine bell envelope (no clicking at boundaries)
    env = np.sin(np.pi * np.linspace(0, 1, n)) ** 1.6
    sig = sig * env * peak
    return sig.astype(np.float32)


def _synthesize_chord(peak: float = 0.38) -> np.ndarray:
    """Generate a warm, satisfying Rhodes/water-drop style acoustic chord (G3 + B3 + D4)."""
    sr = 44100
    duration_s = 0.14
    n = int(sr * duration_s)
    t = np.linspace(0, duration_s, n, endpoint=False)

    # Warm G-major triad with low-mid focus: G3 (196Hz), B3 (247Hz), D4 (293.6Hz)
    sig = (
        np.sin(2 * np.pi * 196.0 * t)
        + 0.70 * np.sin(2 * np.pi * 246.9 * t)
        + 0.35 * np.sin(2 * np.pi * 293.6 * t)
    )
    # Smooth exponential decay with soft attack
    attack = np.sin(np.pi * np.clip(t / 0.015, 0, 0.5))
    decay = np.exp(-t * 22.0)
    sig = sig * attack * decay * peak
    return sig.astype(np.float32)


def _to_wav_bytes(sig: np.ndarray, sr: int = 44100) -> bytes:
    """Convert float32 audio to 16-bit WAV bytes for winsound fallback."""
    pcm16 = (np.clip(sig, -1.0, 1.0) * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm16.tobytes())
    return buf.getvalue()


# Pre-synthesize earcons once at startup (microsecond generation, <20KB RAM total)
_SOUND_START = _synthesize_tone(180, 260, 0.085, peak=0.42)   # Soft warm sub swell
_SOUND_STOP = _synthesize_tone(250, 160, 0.065, peak=0.38)    # Soft warm confirmation tap
_SOUND_CANCEL = _synthesize_tone(220, 140, 0.070, peak=0.35)  # Quick low tap for cancellation
_SOUND_PASTE = _synthesize_chord(peak=0.40)                   # Satisfying warm acoustic chime

_WAV_CACHE: dict[int, bytes] = {}


def _play(sig: np.ndarray) -> None:
    """Play sound array via sounddevice asynchronously; fallback to winsound."""
    try:
        import sounddevice as sd
        sd.play(sig, 44100)
        return
    except Exception as e:
        log.debug("sounddevice play failed: %s; trying winsound fallback", e)

    if winsound is None:
        return
    try:
        key = id(sig)
        if key not in _WAV_CACHE:
            _WAV_CACHE[key] = _to_wav_bytes(sig)
        winsound.PlaySound(_WAV_CACHE[key], winsound.SND_MEMORY | winsound.SND_ASYNC)
    except Exception as e:
        log.debug("winsound cue failed: %s", e)


def play_start() -> None:
    """Play soft, warm swell when recording begins."""
    _play(_SOUND_START)


def play_stop() -> None:
    """Play soft, warm tap when recording stops."""
    _play(_SOUND_STOP)


def play_cancel() -> None:
    """Play soft low tap when recording is cancelled."""
    _play(_SOUND_CANCEL)


def play_paste() -> None:
    """Play satisfying acoustic chord when transcription & paste complete."""
    _play(_SOUND_PASTE)
