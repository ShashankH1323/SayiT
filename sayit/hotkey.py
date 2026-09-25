"""Global, system-wide toggle hotkey for Say It (Windows-first, `keyboard` & `mouse` libs).

Supports standard keyboard hotkeys (e.g. "ctrl+space", "alt+space", "f8") as well
as mouse buttons and side keys (e.g. "mouse4", "mouse5", "middle", "ctrl+mouse4").
Focus-independent hooks run on background daemon threads.
"""
from __future__ import annotations

import logging
from collections.abc import Callable

try:
    import keyboard
except ImportError:
    keyboard = None

try:
    import mouse
except ImportError:
    mouse = None

log = logging.getLogger("sayit")

MOUSE_BUTTON_MAP = {
    "mouse4": "x",
    "mouse_4": "x",
    "x1": "x",
    "back": "x",
    "mouse5": "x2",
    "mouse_5": "x2",
    "x2": "x2",
    "forward": "x2",
    "middle": "middle",
    "middle_click": "middle",
    "mouse3": "middle",
    "mouse_3": "middle",
    "right": "right",
    "right_click": "right",
    "mouse2": "right",
    "mouse_2": "right",
}


def normalize_hotkey(hotkey: str) -> str:
    """Normalize user hotkey strings to a canonical format.
    E.g. 'Control + Space' -> 'ctrl+space', 'Mouse 4' -> 'mouse4'.
    """
    if not hotkey:
        return "ctrl+space"
    s = hotkey.strip().lower()
    # Normalize spaced mouse terms
    s = s.replace("mouse 4", "mouse4").replace("mouse 5", "mouse5")
    s = s.replace("side button 1", "mouse4").replace("side button 2", "mouse5")
    s = s.replace("side 1", "mouse4").replace("side 2", "mouse5")
    s = s.replace("middle click", "middle").replace("mouse 3", "mouse3")
    parts = [p.strip() for p in s.replace("+", " ").split() if p.strip()]
    normalized_parts = []
    for p in parts:
        if p in ("control", "ctrl"):
            normalized_parts.append("ctrl")
        elif p in ("alt", "option"):
            normalized_parts.append("alt")
        elif p == "shift":
            normalized_parts.append("shift")
        elif p in ("win", "cmd", "windows", "super"):
            normalized_parts.append("windows")
        elif p in MOUSE_BUTTON_MAP:
            normalized_parts.append(p)
        else:
            normalized_parts.append(p)
    return "+".join(normalized_parts) or "ctrl+space"


class HotkeyListener:
    """Register a global toggle hotkey; `on_toggle` fires on each press of `hotkey`."""

    def __init__(self, hotkey: str, on_toggle: Callable[[], None]):
        self.raw_hotkey = hotkey
        self.hotkey = normalize_hotkey(hotkey)
        self.on_toggle = on_toggle
        self._kb_handle = None
        self._mouse_handler = None

    def start(self) -> None:
        parts = self.hotkey.split("+")
        mouse_parts = [p for p in parts if p in MOUSE_BUTTON_MAP]

        if mouse_parts:
            if mouse is None:
                raise RuntimeError("mouse hotkeys need the 'mouse' package: pip install mouse")
            btn_key = mouse_parts[0]
            btn_name = MOUSE_BUTTON_MAP[btn_key]
            modifiers = [p for p in parts if p not in MOUSE_BUTTON_MAP]

            def on_mouse_event(event):
                try:
                    if getattr(event, "event_type", None) != "down":
                        return
                    if getattr(event, "button", None) != btn_name:
                        return
                    # Check keyboard modifiers if any are required
                    if keyboard is not None:
                        for mod in modifiers:
                            if not keyboard.is_pressed(mod):
                                return
                    self.on_toggle()
                except Exception as exc:
                    log.warning("[sayit] error in mouse hotkey callback: %s", exc)

            if self._mouse_handler is None:
                self._mouse_handler = mouse.hook(on_mouse_event)
        else:
            if keyboard is None:
                raise RuntimeError("hotkey needs the 'keyboard' package: pip install keyboard")
            if self._kb_handle is not None:
                return
            self._kb_handle = keyboard.add_hotkey(self.hotkey, self.on_toggle)

    def stop(self) -> None:
        if keyboard is not None and self._kb_handle is not None:
            try:
                keyboard.remove_hotkey(self._kb_handle)
            except Exception:
                pass
            self._kb_handle = None

        if mouse is not None and self._mouse_handler is not None:
            try:
                mouse.unhook(self._mouse_handler)
            except Exception:
                pass
            self._mouse_handler = None
