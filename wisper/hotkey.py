"""Global, system-wide toggle hotkey for Wisper (Windows-first, `keyboard` lib).

Doc 05: `keyboard` needs no admin on Windows and is focus-independent. `add_hotkey`
installs a low-level hook on `keyboard`'s own daemon thread, so `start()` is
non-blocking and fires even when Wisper has no focused window.
"""
from collections.abc import Callable

try:
    import keyboard
except ImportError:  # keep the module importable without the dep
    keyboard = None


class HotkeyListener:
    """Register a global toggle hotkey; `on_toggle` fires on each press of `hotkey`."""

    def __init__(self, hotkey: str, on_toggle: Callable[[], None]):
        self.hotkey = hotkey          # e.g. "ctrl+alt+space", from user config
        self.on_toggle = on_toggle
        self._handle = None

    def start(self) -> None:
        if keyboard is None:
            raise RuntimeError("hotkey needs the 'keyboard' package: pip install keyboard")
        if self._handle is not None:
            return  # already registered
        # keyboard owns the hook thread (daemon) -> this returns immediately.
        # on_toggle runs on that hook thread; the orchestrator must keep it fast
        # (hand heavy work to a worker/queue) -- doc 05 threading gotcha.
        self._handle = keyboard.add_hotkey(self.hotkey, self.on_toggle)

    def stop(self) -> None:
        if keyboard is None or self._handle is None:
            return
        keyboard.remove_hotkey(self._handle)
        self._handle = None
