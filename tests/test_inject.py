"""Runnable, assert-based self-test for wisper.inject / wisper.hotkey.

Passes with stdlib only (deps are import-guarded). Run: python tests/test_inject.py
"""
import os
import sys

# repo root on path so `wisper` (namespace pkg) imports when run as a script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wisper.inject import _paste_keys  # noqa: E402
from wisper.hotkey import HotkeyListener  # noqa: E402


def test_paste_keys():
    assert _paste_keys("auto") == "ctrl+v"
    assert _paste_keys("ctrl_v") == "ctrl+v"
    assert _paste_keys("ctrl_shift_v") == "ctrl+shift+v"


def test_listener_construct():
    # construct only -- start() needs a real global hook / keyboard access
    HotkeyListener("ctrl+alt+space", lambda: None)


def test_clipboard_roundtrip():
    try:
        import pyperclip
    except ImportError:
        print("pyperclip not importable -- skipping clipboard round-trip")
        return
    try:
        prior = pyperclip.paste()
        pyperclip.copy("wisper-test-123")
        assert pyperclip.paste() == "wisper-test-123"
        pyperclip.copy(prior)  # restore
    except pyperclip.PyperclipException as e:
        print(f"no clipboard available -- skipping clipboard round-trip ({e})")


def test_copy_resilient_graceful_fail():
    """A locked clipboard (copy raises) must be swallowed, not propagated."""
    from wisper import inject

    calls = {"n": 0}

    def boom(_):
        calls["n"] += 1
        raise RuntimeError("clipboard locked")

    orig_copy = inject.pyperclip.copy if inject.pyperclip else None
    orig_pc = inject.pyperclip
    orig_kb = inject.keyboard
    orig_sleep = inject.time.sleep
    inject.pyperclip = type("P", (), {"copy": staticmethod(boom)})()
    inject.keyboard = type("K", (), {"send": staticmethod(lambda *_: None)})()  # satisfy _require_deps
    inject.time.sleep = lambda *_: None  # no real delay in the test
    try:
        assert inject._copy_resilient("x", attempts=3) is False
        assert calls["n"] == 3, calls["n"]  # retried the full count
        # paste_text must NOT raise even when the copy path fails
        inject.paste_text("x", mode="off")
        inject.paste_text("x", mode="auto")
    finally:
        inject.time.sleep = orig_sleep
        inject.keyboard = orig_kb
        inject.pyperclip = orig_pc


def test_copy_resilient_succeeds_after_retry():
    from wisper import inject

    calls = {"n": 0}

    def flaky(_):
        calls["n"] += 1
        if calls["n"] < 2:
            raise RuntimeError("locked once")

    orig = inject.pyperclip
    orig_sleep = inject.time.sleep
    inject.pyperclip = type("P", (), {"copy": staticmethod(flaky)})()
    inject.time.sleep = lambda *_: None
    try:
        assert inject._copy_resilient("x", attempts=3) is True
        assert calls["n"] == 2, calls["n"]  # failed once, then succeeded
    finally:
        inject.time.sleep = orig_sleep
        inject.pyperclip = orig


if __name__ == "__main__":
    test_paste_keys()
    test_listener_construct()
    test_clipboard_roundtrip()
    test_copy_resilient_graceful_fail()
    test_copy_resilient_succeeds_after_retry()
    print("inject self-test PASSED")
