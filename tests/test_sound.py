"""Unit tests for wisper.sound: verifying tactile pure-bass acoustic earcons."""

import numpy as np
import pytest

from wisper import sound


def _spectral_stats(sig: np.ndarray, sr: int = 44100):
    fft = np.abs(np.fft.rfft(sig))
    freqs = np.fft.rfftfreq(len(sig), 1 / sr)
    total_energy = np.sum(fft**2)
    bass_energy = np.sum(fft[freqs < 200] ** 2) / total_energy * 100.0
    sub_energy = np.sum(fft[freqs < 100] ** 2) / total_energy * 100.0
    high_energy = np.sum(fft[freqs >= 2000] ** 2) / total_energy * 100.0
    peak_f = freqs[np.argmax(fft)]
    max_amp = float(np.max(np.abs(sig)))
    return {
        "bass_energy": bass_energy,
        "sub_energy": sub_energy,
        "high_energy": high_energy,
        "peak_f": peak_f,
        "max_amp": max_amp,
    }


@pytest.mark.parametrize(
    "cue_name,cue_obj",
    [
        ("start", sound._SOUND_START),
        ("stop", sound._SOUND_STOP),
        ("paste", sound._SOUND_PASTE),
        ("cancel", sound._SOUND_CANCEL),
        ("error", sound._SOUND_ERROR),
    ],
)
def test_preloaded_sound_cues_are_pure_bass(cue_name, cue_obj):
    """Verify that every loaded sound cue meets the pure tactile bass requirement."""
    assert cue_obj is not None
    assert cue_obj.sig is not None and len(cue_obj.sig) > 0
    assert cue_obj.sr == 44100
    assert cue_obj.wav_bytes is not None and len(cue_obj.wav_bytes) > 44

    stats = _spectral_stats(cue_obj.sig, cue_obj.sr)

    # 1. > 99% energy strictly below 200 Hz
    assert stats["bass_energy"] >= 99.0, (
        f"{cue_name} bass energy (<200Hz) is {stats['bass_energy']:.2f}%, expected >= 99.0%"
    )

    # 2. Strong sub-bass content (<100Hz)
    assert stats["sub_energy"] >= 75.0, (
        f"{cue_name} sub energy (<100Hz) is {stats['sub_energy']:.2f}%, expected >= 75.0%"
    )

    # 3. Peak fundamental is strictly in the sub/bass range (30Hz - 90Hz)
    assert 30.0 <= stats["peak_f"] <= 90.0, (
        f"{cue_name} peak frequency is {stats['peak_f']:.1f}Hz, expected between 30 and 90 Hz"
    )

    # 4. Zero click sound in the treble (>2000Hz)
    assert stats["high_energy"] < 0.05, (
        f"{cue_name} high-frequency energy (>2kHz) is {stats['high_energy']:.2f}%, expected < 0.05%"
    )

    # 5. Amplitude is normalized and safe from digital clipping
    assert 0.70 <= stats["max_amp"] <= 0.98


@pytest.mark.parametrize(
    "fallback_fn",
    [
        sound._fallback_start,
        sound._fallback_stop,
        sound._fallback_paste,
        sound._fallback_cancel,
        sound._fallback_error,
    ],
)
def test_procedural_fallback_synthesis(fallback_fn):
    """Verify procedural synthesizers work cleanly without asset files."""
    sig, sr = fallback_fn()
    assert sr == 44100
    assert isinstance(sig, np.ndarray)
    assert sig.dtype == np.float32

    stats = _spectral_stats(sig, sr)
    assert stats["bass_energy"] >= 99.0
    assert stats["sub_energy"] >= 75.0
    assert 30.0 <= stats["peak_f"] <= 90.0
    assert stats["high_energy"] < 0.05


def test_public_sound_functions_non_blocking_safe():
    """Verify all public play functions execute safely without crashing."""
    sound.play_start()
    sound.play_stop()
    sound.play_paste()
    sound.play_cancel()
    sound.play_error()
