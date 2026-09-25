"""Self-test for sayit.stt — runs with only numpy + stdlib."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from sayit.stt import FasterWhisperBackend, _resolve_task


def test_construct_without_faster_whisper():
    # Lazy load: constructing must not import faster_whisper or touch a GPU.
    b = FasterWhisperBackend(model="large-v3-turbo", device="cuda", compute_type="float16")
    assert b.model == "large-v3-turbo"
    assert b.device == "cuda"
    assert b.compute_type == "float16"
    assert b._model is None  # nothing loaded yet


def test_empty_audio_returns_empty():
    b = FasterWhisperBackend()
    assert b.transcribe(np.zeros(10, dtype=np.float32)) == ""
    assert b._model is None  # short-circuited before any model load


def test_resolve_task():
    assert _resolve_task("en", "en") == ("transcribe", "en")
    assert _resolve_task(None, "en") == ("transcribe", None)
    task, _lang = _resolve_task("hi", "en")
    assert task == "translate"
    assert _resolve_task("hi", "hi") == ("transcribe", "hi")


if __name__ == "__main__":
    test_construct_without_faster_whisper()
    test_empty_audio_returns_empty()
    test_resolve_task()
    print("stt self-test PASSED")
