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


if __name__ == "__main__":
    test_paste_keys()
    test_listener_construct()
    test_clipboard_roundtrip()
    print("inject self-test PASSED")
