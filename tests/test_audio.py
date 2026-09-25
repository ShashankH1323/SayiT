"""Self-test for sayit.audio. Runs with numpy + stdlib only.

    python tests/test_audio.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

import sayit.audio as audio
from sayit.audio import resample, to_mono


def test_to_mono():
    sr = 48000
    t = np.arange(sr, dtype=np.float32) / sr
    tone = np.sin(2 * np.pi * 440.0 * t).astype(np.float32)
    stereo = np.stack([tone, tone * 0.5], axis=1)  # (48000, 2)
    m = to_mono(stereo)
    assert m.shape == (48000,), m.shape
    assert m.dtype == np.float32, m.dtype
    assert to_mono(tone).shape == (48000,)  # 1-D passthrough


def test_resample():
    orig_sr, target_sr = 48000, 16000
    t = np.arange(orig_sr, dtype=np.float32) / orig_sr
    tone = np.sin(2 * np.pi * 220.0 * t).astype(np.float32)  # 1 s @ 48 kHz
    out = resample(tone, orig_sr, target_sr)
    assert out.dtype == np.float32, out.dtype
    assert abs(len(out) - 16000) <= 5, len(out)
    assert not np.any(np.isnan(out)), "resample produced NaNs"


# --- BUG 1: mic released on a failed open; stop() idempotent -----------------
class _FakeStream:
    """InputStream stand-in whose start() fails, so we can prove close() runs."""
    def __init__(self, **kw):
        self.closed = self.stopped = False

    def start(self):
        raise RuntimeError("fake: device could not start")

    def stop(self):
        self.stopped = True

    def close(self):
        self.closed = True


class _FakeSD:
    """Minimal sounddevice: one MME input device; InputStream.start() raises."""
    PortAudioError = type("PortAudioError", (Exception,), {})

    def __init__(self):
        self.streams = []
        self.default = type("d", (), {"device": (0, 0)})()

    def query_hostapis(self, index=None):
        apis = [{"name": "MME", "default_input_device": 0}]
        return apis[index] if index is not None else apis

    def query_devices(self, dev=None, kind=None):
        devs = [{"name": "Fake Mic", "max_input_channels": 1,
                 "hostapi": 0, "default_samplerate": 48000.0}]
        return devs if dev is None else devs[dev]

    def InputStream(self, **kw):
        s = _FakeStream(**kw)
        self.streams.append(s)
        return s


def test_stop_idempotent_no_stream():
    cap = audio.AudioCapture()
    out = cap.stop()            # nothing was ever opened
    assert cap._stream is None
    assert out.shape == (0,), out.shape
    cap.stop()                  # double stop stays safe
    assert cap._stream is None


def test_failed_start_releases_device():
    orig = audio._sd
    audio._sd = fake = _FakeSD()
    try:
        cap = audio.AudioCapture()
        err = None
        try:
            cap.start()
        except Exception as e:  # every candidate fails -> propagates
            err = e
        assert err is not None, "start() must raise once all candidates fail"
        assert fake.streams, "InputStream was never constructed"
        assert fake.streams[-1].closed, "opened device not closed -> mic leak"
        assert cap._stream is None, "self._stream must be None after failed start"
        assert not cap.is_recording()
    finally:
        audio._sd = orig


# --- BUG: Pa_Terminate() must never run while a stream is open ---------------
class _OkStream:
    """InputStream stand-in that opens and starts cleanly."""
    def __init__(self, **kw):
        self.started = self.stopped = self.closed = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def close(self):
        self.closed = True


class _RefreshSD(_FakeSD):
    """FakeSD whose streams start OK, tracking _terminate/_initialize calls."""
    def __init__(self):
        super().__init__()
        self.terminated = 0
        self.initialized = 0

    def InputStream(self, **kw):
        s = _OkStream(**kw)
        self.streams.append(s)
        return s

    def _terminate(self):
        self.terminated += 1

    def _initialize(self):
        self.initialized += 1


def test_refresh_skips_reinit_with_open_stream():
    orig, orig_count = audio._sd, audio._open_streams
    audio._sd = fake = _RefreshSD()
    audio._open_streams = 0
    try:
        cap = audio.AudioCapture()

        # 1) idle -> refresh may reinitialize PortAudio
        audio.refresh_input_devices()
        assert (fake.terminated, fake.initialized) == (1, 1), "reinit must run when idle"

        # 2) recording stream open -> Pa_Terminate would crash; must be skipped
        cap.start()
        assert audio._open_streams == 1, audio._open_streams
        audio.refresh_input_devices()
        assert fake.terminated == 1, "Pa_Terminate ran with an open recording stream"
        cap.stop()
        assert audio._open_streams == 0, audio._open_streams

        # 3) monitor stream open (the real mic-settings trigger) -> also skipped
        cap.start_monitor()
        assert audio._open_streams == 1, audio._open_streams
        audio.refresh_input_devices()
        assert fake.terminated == 1, "Pa_Terminate ran with an open monitor stream"
        cap.stop_monitor()
        assert audio._open_streams == 0, audio._open_streams

        # 4) closed again -> reinit resumes
        audio.refresh_input_devices()
        assert (fake.terminated, fake.initialized) == (2, 2), "reinit must resume when idle"
    finally:
        audio._sd, audio._open_streams = orig, orig_count


if __name__ == "__main__":
    test_to_mono()
    test_resample()
    test_stop_idempotent_no_stream()
    test_failed_start_releases_device()
    test_refresh_skips_reinit_with_open_stream()
    print("audio self-test PASSED")
