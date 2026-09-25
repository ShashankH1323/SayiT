"""Standalone smoke test for Api.set_window_mode (no pytest — __main__ + asserts,
per project convention). Verifies the UI-thread-marshalling freeze-fix LOGIC
without a real GUI.

The real bug (cross-thread window ops from the JS-bridge worker -> "Not
Responding") can only surface with a live WinForms form on its UI thread; that
path is covered empirically by the freeze watchdog. Here we lock down the
_apply body's decisions:

  * form-None branch (tests / non-winforms / unresolved uid): _apply runs
    inline, returns None, never raises; minibar -> resize(120,32)+on_top=True,
    full -> on_top=False (+resize, since there's no real form size to gate on).
  * form-present-inline branch: the idempotency guard skips the redundant
    720x720 resize when the WinForms form already reports 720x720.

Run: python tests/test_set_window_mode_smoke.py
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.getLogger("wisper").setLevel(logging.CRITICAL)  # silence expected warnings

from wisper.webui import Api


class StubWindow:
    """Records resize() and on_top writes; carries a uid so form resolution can
    be steered (a uid absent from BrowserView.instances -> form-None branch)."""

    def __init__(self, uid):
        self.uid = uid
        self.resizes = []
        self.on_top_writes = []
        self._on_top = False

    @property
    def on_top(self):
        return self._on_top

    @on_top.setter
    def on_top(self, v):
        self._on_top = v
        self.on_top_writes.append(v)

    def resize(self, w, h):
        self.resizes.append((w, h))

    def move(self, x, y):
        pass


class _Handle:
    def ToInt64(self):
        return 0  # hwnd 0 -> _set_taskbar_visible/_taskbar_ok stay harmless no-ops


class FakeForm:
    """Minimal stand-in for the WinForms Form: already 720x720, on its own
    thread (InvokeRequired False -> _apply runs inline, no BeginInvoke)."""

    def __init__(self, w=720, h=720):
        self.Width = w
        self.Height = h
        self.InvokeRequired = False
        self.Handle = _Handle()
        self.WindowState = None
        self.activated = 0

    def Activate(self):
        self.activated += 1


def test_form_none_branch():
    """The branch tests actually hit: uid not registered -> form is None."""
    win = StubWindow("smoke-no-form")
    api = Api(None)  # __init__ only sets self.app/self._window; app unused here
    api._window = win

    assert api.set_window_mode("full") is None, "full must return None"
    assert api.set_window_mode("full") is None, "second full must return None"
    assert api.set_window_mode("minibar") is None, "minibar must return None"

    if sys.platform != "win32":
        print("PASS: form-none branch (non-win32: set_window_mode is a no-op)")
        return

    # full legs (no real form -> size can't be gated, so 720x720 is requested).
    assert (720, 720) in win.resizes, f"full must resize(720,720); got {win.resizes}"
    # minibar leg: compact size + goes on_top.
    assert (120, 32) in win.resizes, f"minibar must resize(120,32); got {win.resizes}"
    assert win.on_top is True, "minibar must leave window on_top=True"
    assert True in win.on_top_writes, "minibar must set on_top True"
    # on_top is written only when it needs to change (guarded): full started at
    # False so it never rewrote False; now that minibar left it True, full clears it.
    assert api.set_window_mode("full") is None
    assert win.on_top is False, "full must clear on_top"
    assert False in win.on_top_writes, "full must write on_top False when it was True"
    print("PASS: form-none branch (returns None, no raise, minibar/full route correctly)")


def test_idempotent_resize_with_form():
    """Idempotency guard: with a form already at 720x720, full must NOT resize."""
    if sys.platform != "win32":
        print("SKIP: idempotency guard (needs win32 WinForms/clr)")
        return
    try:
        from webview.platforms.winforms import BrowserView
    except Exception as e:
        print(f"SKIP: idempotency guard (winforms import failed: {e})")
        return

    win = StubWindow("smoke-with-form")
    form = FakeForm(720, 720)
    BrowserView.instances[win.uid] = form
    try:
        api = Api(None)
        api._window = win
        assert api.set_window_mode("full") is None
        assert api.set_window_mode("full") is None  # idempotent
        assert (720, 720) not in win.resizes, (
            f"full must skip redundant 720x720 resize when form already 720x720; got {win.resizes}")
        assert win.on_top is False, "full must leave on_top=False"
        assert form.WindowState is not None, "full must set WindowState=Normal"
        print("PASS: idempotency guard (no redundant resize when form already 720x720)")
    finally:
        BrowserView.instances.pop(win.uid, None)


def main():
    test_form_none_branch()
    test_idempotent_resize_with_form()
    print("-" * 40)
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
