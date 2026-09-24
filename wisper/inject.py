"""Instant whole-paragraph text injection: clipboard-set + one paste (doc 05).

Primary method per doc 05: set the transcript on the clipboard -> send ONE
paste keystroke. Atomic (one clipboard write + one paste), app-agnostic, and
correct for Unicode/Indic (the target shapes the text itself). The prior
clipboard is intentionally NOT saved or restored -- the dictated text is left
on the clipboard so the user can manually paste it anywhere even if focus was
not on a text field.
"""
import time

try:
    import keyboard
except ImportError:
    keyboard = None
try:
    import pyperclip
except ImportError:
    pyperclip = None

# ponytail: hardcoded clipboard-race delay (doc 05 "Timing / race concerns").
# Machine-dependent; tune here, or switch to a clipboard-viewer signal instead
# of a fixed sleep if a fast app misses the paste.
SET_TO_PASTE_DELAY = 0.03      # let a fast app finish reading the freshly-set clipboard

# "auto" == Ctrl+V (doc 05 default). Ctrl+Shift+V branch is for terminals
# (PSReadLine / Windows Terminal / VS Code integrated terminal) where Ctrl+V is
# "quoted insert", not paste -- caller selects it via mode="ctrl_shift_v".
_MODE_KEYS = {
    "auto": "ctrl+v",
    "ctrl_v": "ctrl+v",
    "ctrl_shift_v": "ctrl+shift+v",
}


def _paste_keys(mode: str = "auto") -> str:
    """Map an inject mode to a `keyboard` hotkey string. Pure -> unit-testable."""
    try:
        return _MODE_KEYS[mode]
    except KeyError:
        raise ValueError(f"unknown paste mode {mode!r}; use one of {sorted(_MODE_KEYS)}") from None


def _require_deps() -> None:
    missing = [n for n, m in (("keyboard", keyboard), ("pyperclip", pyperclip)) if m is None]
    if missing:
        raise RuntimeError(
            f"paste_text needs missing package(s): {', '.join(missing)} "
            f"(pip install {' '.join(missing)})"
        )


def paste_text(text: str, mode: str = "auto") -> None:
    """Drop `text` into the focused field via clipboard + one paste keystroke.
    The text is permanently kept on the clipboard so the user can manually Ctrl+V
    anywhere even if focus was not on a text field."""
    _require_deps()
    if mode == "off":
        pyperclip.copy(text)      # copy-only no-op paste: leave it on the clipboard, no keystroke
        return
    keys = _paste_keys(mode)      # validate mode BEFORE touching the clipboard
    pyperclip.copy(text)          # keep dictated text in clipboard
    time.sleep(SET_TO_PASTE_DELAY)
    try:
        keyboard.send(keys)       # attempt paste keystroke
    except Exception:
        pass
