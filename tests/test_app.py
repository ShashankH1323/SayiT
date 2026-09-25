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

from sayit.app import SayItApp as WisperApp, State
from sayit.config import Config
from sayit.clean import RuleCleaner

# The error-path case intentionally makes STT raise; the app logs it via
# log.exception and recovers. Silence that expected traceback so it can't be
# misread as a test failure.
logging.getLogger("sayit").setLevel(logging.CRITICAL)


class FakeAudio:
    def __init__(self):
        self._recording = False

    def start(self):
        self._recording = True

    def stop(self):
        self._recording = False
        return np.zeros(1600, dtype=np.float32)

    def preprocess_for_stt(self, pcm, samplerate, noise_suppression=False, input_threshold=0.0):
        return pcm  # default seam is identity; matches AudioCapture with no gating

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


class SlowCleaner:
    """Blocks in clean() until released, so a cancel can fire mid-CLEANING (the
    slow-cloud-cleanup window where the reported hotkey-death bug lived)."""

    def __init__(self, release):
        self._release = release

    def clean(self, raw, mode="rule", lang="en"):
        self._release.wait(5)
        return "cleaned text"


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
    # "you know" is a BOUNDARY filler: clean.py removes it only utterance-initial or
    # comma-adjacent and deliberately KEEPS it mid-sentence (documented under-removal).
    assert sink[0] == "So I think you know it's fine.", f"unexpected paste: {sink[0]!r}"

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

    # 5) Superseded-worker race: cancel() (then a fresh run) strips a still-running
    #    worker of all authority — it must NOT paste, write history, reset live
    #    state, or release the live run's idle gate. Repro of the reported bug:
    #    cancel while transcribing, then re-dictate before the old worker finishes.
    release5 = threading.Event()
    sink5 = []
    app5 = WisperApp(Config(), audio=FakeAudio(), stt=SlowStt(release5),
                     cleaner=RuleCleaner(), paste=lambda t, mode="auto": sink5.append(t))
    app5.toggle()  # IDLE -> RECORDING
    app5.toggle()  # -> worker (rid) spawned, now blocked inside SlowStt.transcribe
    time.sleep(0.05)
    app5.cancel()  # supersedes the worker: _run_seq bumped, state -> IDLE
    assert app5.state is State.IDLE, f"cancel did not reach IDLE: {app5.state}"

    # Stand in for a fresh live run that took over after the cancel.
    app5.state = State.RECORDING
    app5.last_text = "LIVE-RUN-TEXT"
    app5.idle_event.clear()  # live run is in progress

    release5.set()   # let the stale worker run to completion
    time.sleep(0.3)  # give a broken guard time to (wrongly) paste / reset

    assert sink5 == [], f"superseded worker pasted: {sink5!r}"
    assert app5.state is State.RECORDING, f"superseded worker clobbered live state: {app5.state}"
    assert app5.last_text == "LIVE-RUN-TEXT", f"superseded worker overwrote last_text: {app5.last_text!r}"
    assert not app5.idle_event.is_set(), "superseded worker released the live run's idle gate"

    # 6) Superseded DURING CLEANING (the reported hotkey-death bug): a cancel while
    #    the (slow, e.g. Groq cloud) cleanup pass runs must leave state at IDLE --
    #    NEVER stuck at PASTING with no worker -- and the stale worker must not paste
    #    or record to history. Before the fix, the run-token check sat AFTER the
    #    worker wrote state=PASTING, so a cancel mid-clean left state=PASTING and the
    #    next toggle saw a busy state and did nothing (hotkey looked dead).
    import sayit.app as app_mod
    recorded = []
    orig_record = app_mod.history.record
    app_mod.history.record = lambda text, size: recorded.append(text)
    try:
        clean_release = threading.Event()
        sink6 = []
        app6 = WisperApp(Config(), audio=FakeAudio(), stt=FakeStt(),
                         cleaner=SlowCleaner(clean_release),
                         paste=lambda t, mode="auto": sink6.append(t))
        app6.toggle()  # IDLE -> RECORDING
        app6.toggle()  # -> worker: transcribe returns fast, then blocks in clean()
        time.sleep(0.1)
        assert app6.state is State.CLEANING, f"expected CLEANING, got {app6.state}"
        app6.cancel()  # supersede the worker mid-CLEANING
        assert app6.state is State.IDLE, f"cancel mid-clean did not reach IDLE: {app6.state}"
        clean_release.set()  # let the stale worker finish its cleanup pass
        assert app6.idle_event.wait(timeout=5)  # cancel set it; worker must not clear it
        time.sleep(0.2)  # give a broken guard time to (wrongly) set PASTING / paste
        assert app6.state is State.IDLE, (
            f"superseded worker left state at {app6.state} (bug: stuck PASTING, hotkey dead)"
        )
        assert sink6 == [], f"superseded worker pasted: {sink6!r}"
        assert recorded == [], f"superseded worker recorded to history: {recorded!r}"
    finally:
        app_mod.history.record = orig_record

    print("app self-test PASSED")


if __name__ == "__main__":
    main()
