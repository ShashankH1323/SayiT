"""pywebview bridge for Wisper's native UI.

A frameless Edge WebView2 window (offline, no server) that loads
``wisper/web/index.html`` and exposes ``window.pywebview.api`` -> the ``Api``
class below. Every method is JSON-serializable in and out; the frontend polls
``get_status()`` at ~30fps.

``webview`` is imported lazily inside :func:`launch`, so this module (and its
tests) import fine without pywebview installed. The functional core is never
modified -- ``Api`` only routes to ``WisperApp`` and the ``wisper.*`` modules.
"""
from __future__ import annotations

import logging
from pathlib import Path

from wisper import audio, history, models, stt
from wisper.app import State

log = logging.getLogger("wisper")

# Absolute path to the frontend entry (built by a separate agent). Referenced
# lazily; it need not exist at import time.
_INDEX = Path(__file__).resolve().parent / "web" / "index.html"

# Preferred entry: the built React app at <repo root>/dist/index.html. Falls
# back to _INDEX (vanilla web/index.html) when the build is absent.
_BUILT = Path(__file__).resolve().parent.parent / "dist" / "index.html"

# Real State enum member -> one of the 4 states the frontend understands.
# recording = capturing; processing = transcribe/clean/paste; idle = ready or
# just-finished; error = last op failed.
_STATE_MAP = {
    State.IDLE: "idle",
    State.RECORDING: "recording",
    State.TRANSCRIBING: "processing",
    State.CLEANING: "processing",
    State.PASTING: "processing",
    State.ERROR: "error",
}

# set_setting keys routed to WisperApp methods (which persist config themselves).
_SETTING_METHODS = {
    "hotkey": "set_hotkey",
    "stt_provider": "set_stt_provider",
    "groq_model": "set_groq_model",
    "model": "set_model",
}
# All other writable keys: plain Config attributes (setattr + save).
_CONFIG_KEYS = (
    "input_device", "samplerate", "device", "compute_type", "language",
    "output_language", "cleanup_mode", "sound_effects", "history_size",
    "paste_mode",
)
_LANGUAGES = ["auto", "en", "hi", "kn", "es", "fr", "de", "it", "pt", "ja", "zh"]


def _bare_device_name(label):
    """Strip a device label's ' — <HostAPI>' suffix so the remainder is a valid
    AudioCapture name-substring. Empty/None -> None (auto)."""
    if not label:
        return None
    return label.rsplit("—", 1)[0].strip() or None


class Api:
    """``window.pywebview.api``. Holds a WisperApp; each method routes to core."""

    def __init__(self, app):
        self.app = app
        self._window = None  # set by launch(); used by window_minimize/close

    # --- status / control -------------------------------------------------
    def get_status(self):
        app = self.app
        try:
            level = float(app.audio.current_level())
        except Exception:  # a live meter must never break the poll loop
            level = 0.0
        return {
            "state": _STATE_MAP.get(app.state, "idle"),
            "last_text": app.last_text or "",
            "last_error": app.last_error or None,  # "" -> null per contract
            "level": max(0.0, min(1.0, level)),
        }

    def toggle(self):
        self.app.toggle()
        return None

    def cancel(self):
        self.app.cancel()
        return None

    def start_preview(self, device=None):
        dev = _bare_device_name(device)
        self.app.audio.start_monitor(dev)
        return None

    def stop_preview(self):
        self.app.audio.stop_monitor()
        return None

    # --- devices ----------------------------------------------------------
    def list_devices(self):
        return [label for label, _ in audio.list_input_devices()]

    def refresh_devices(self):
        return [label for label, _ in audio.refresh_input_devices()]

    def set_device(self, name):
        dev = _bare_device_name(name)  # store the matchable name in both places
        self.app.audio.device = dev
        self.app.config.input_device = dev
        self.app.config.save()
        if getattr(self.app.audio, "_monitoring", False):
            self.app.audio.start_monitor(dev)
        return None

    # --- settings ---------------------------------------------------------
    def get_settings(self):
        c = self.app.config
        return {
            "hotkey": c.hotkey,
            "input_device": c.input_device,
            "model": c.model,
            "device": c.device,
            "compute_type": c.compute_type,
            "samplerate": c.samplerate,
            "language": c.language,
            "output_language": c.output_language,
            "cleanup_mode": c.cleanup_mode,
            "stt_provider": c.stt_provider,
            "groq_model": c.groq_model,
            "sound_effects": c.sound_effects,
            "history_size": c.history_size,
            "paste_mode": c.paste_mode,
        }

    def get_options(self):
        return {
            "cleanup_modes": ["light", "casual", "formal", "structured", "raw"],
            "paste_modes": ["auto", "ctrl_v", "ctrl_shift_v"],
            "stt_providers": ["groq", "local"],
            "groq_models": list(stt.GROQ_AVAILABLE_MODELS),
            "languages": list(_LANGUAGES),
            "local_models": list(models.AVAILABLE_MODELS),
        }

    def set_setting(self, key, value):
        if key in _SETTING_METHODS:
            getattr(self.app, _SETTING_METHODS[key])(value)  # persists internally
        elif key in _CONFIG_KEYS:
            setattr(self.app.config, key, value)
            self.app.config.save()
        else:
            log.warning("[wisper] set_setting: ignoring unknown key %r", key)
        return None

    # --- models -----------------------------------------------------------
    def models_status(self):
        return {name: bool(ok) for name, ok in models.model_status()}

    def download_model(self, name):
        try:
            path = models.download(name)  # blocking; pywebview runs api calls off-thread
            return {"name": name, "downloaded": True, "path": str(path), "error": None}
        except Exception as exc:
            return {"name": name, "downloaded": models.is_downloaded(name),
                    "path": None, "error": repr(exc)}

    # --- history ----------------------------------------------------------
    def history_load(self, size=None):
        return history.load(size)

    def history_delete(self, ts, text):
        history.delete_record(ts, text)
        return None

    def history_clear(self):
        history.clear_all()
        return None

    # --- window -----------------------------------------------------------
    def window_minimize(self):
        if self._window is not None:
            self._window.minimize()
        return None

    def window_close(self):
        if self._window is not None:
            self._window.destroy()
        return None


_window = None  # module ref to the live window (single-window app)


def launch(app):
    """Create the frameless native window and block on the pywebview loop.

    Windows uses the default edgechromium/WebView2 backend. The frontend owns
    its own drag region via CSS ``-webkit-app-region``, so easy_drag is off.
    """
    global _window
    import webview  # lazy: keeps this module importable/testable without pywebview

    api = Api(app)
    _window = webview.create_window(
        "Say It",
        url=(_BUILT if _BUILT.exists() else _INDEX).as_uri(),
        js_api=api,
        width=720,
        height=720,
        min_size=(600, 600),
        frameless=True,
        easy_drag=False,
        background_color="#FAFAFC",
    )
    api._window = _window
    webview.start()
