"""End-to-end self-test for the WisperApp orchestrator. Run: python tests/test_app.py

Uses fakes for audio/STT/paste + the REAL RuleCleaner, so it needs no GPU/mic/keyboard.
"""

import logging
import sys
import threading
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wisper.app import WisperApp, State
from wisper.config import Config
from wisper.clean import RuleCleaner

# The error-path case intentionally makes STT raise; the app logs it via
# log.exception and recovers. Silence that expected traceback so it can't be
# misread as a test failure.
logging.getLogger("wisper").setLevel(logging.CRITICAL)


class FakeAudio:
    def __init__(self):
        self._recording = False

    def start(self):
        self._recording = True

    def stop(self):
        self._recording = False
        return np.zeros(1600, dtype=np.float32)

    def is_recording(self):
        return self._recording


class FakeStt:
    def transcribe(self, pcm, lang_in="en", lang_out="en"):
        return "um so i i think you know it's it's fine"


class RaisingStt:
    def transcribe(self, pcm, lang_in="en", lang_out="en"):
        raise RuntimeError("stt exploded")


class SlowStt:
    """Blocks in transcribe() until released, so a toggle can fire mid-process."""

    def __init__(self, release):
        self._release = release

    def transcribe(self, pcm, lang_in="en", lang_out="en"):
        self._release.wait(5)
        return "um so i i think you know it's it's fine"


def _record_then_process(app):
    app.toggle()  # IDLE -> RECORDING
    assert app.state is State.RECORDING, f"expected RECORDING, got {app.state}"
    app.toggle()  # RECORDING -> hand off to worker
    assert app.idle_event.wait(timeout=5), "worker never returned to idle"


def main():
    # 1) Happy path: fakes + the real cleaner, one utterance end to end.
    sink = []
    app = WisperApp(Config(), audio=FakeAudio(), stt=FakeStt(),
                    cleaner=RuleCleaner(), paste=lambda t, mode="auto": sink.append(t))
    _record_then_process(app)
    assert app.state is State.IDLE, f"not idle after run: {app.state}"
    assert len(sink) == 1, f"expected exactly one paste, got {sink!r}"
    assert sink[0] == "So I think it's fine.", f"unexpected paste: {sink[0]!r}"

    # 2) Error path: STT raises -> rest in ERROR (shown in UI), and NEVER partial-paste.
    sink2 = []
    app2 = WisperApp(Config(), audio=FakeAudio(), stt=RaisingStt(),
                     cleaner=RuleCleaner(), paste=lambda t, mode="auto": sink2.append(t))
    _record_then_process(app2)
    assert app2.state is State.ERROR, f"expected State.ERROR, got: {app2.state}"
    assert sink2 == [], f"partial paste leaked on error: {sink2!r}"
    app2.cancel()
    assert app2.state is State.IDLE

    # 3) Busy-ignore: a toggle fired mid-process must not start a second run.
    release = threading.Event()
    sink3 = []
    app3 = WisperApp(Config(), audio=FakeAudio(), stt=SlowStt(release),
                     cleaner=RuleCleaner(), paste=lambda t, mode="auto": sink3.append(t))
    app3.toggle()  # IDLE -> RECORDING
    app3.toggle()  # -> worker spawned, now blocked inside SlowStt.transcribe
    time.sleep(0.05)
    app3.toggle()  # busy -> must be ignored
    release.set()  # let the worker finish
    assert app3.idle_event.wait(timeout=5), "slow worker never finished"
    assert app3.state is State.IDLE, f"not idle after slow run: {app3.state}"
    assert len(sink3) == 1, f"busy toggle caused a double run: {sink3!r}"

    # 4) Cancel path: toggle() starts recording, cancel() stops capture, restores IDLE, no paste.
    sink4 = []
    app4 = WisperApp(Config(), audio=FakeAudio(), stt=FakeStt(),
                     cleaner=RuleCleaner(), paste=lambda t, mode="auto": sink4.append(t))
    app4.toggle()
    assert app4.state is State.RECORDING
    app4.cancel()
    assert app4.state is State.IDLE
    assert sink4 == [], f"paste leaked after cancel: {sink4!r}"

    print("app self-test PASSED")


if __name__ == "__main__":
    main()
