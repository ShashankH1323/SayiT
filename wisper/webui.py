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
import sys

from wisper import audio, history, models, stt
from wisper.app import State

log = logging.getLogger("wisper")

# Absolute path to the frontend entry (built by a separate agent). Referenced
# lazily; it need not exist at import time.
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    _ROOT = Path(sys._MEIPASS)
else:
    _ROOT = Path(__file__).resolve().parent.parent

_INDEX = Path(__file__).resolve().parent / "web" / "index.html"
_BUILT = _ROOT / "dist" / "index.html"

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
    "samplerate", "device", "compute_type", "language",
    "output_language", "cleanup_mode", "sound_effects", "history_size",
    "paste_mode", "noise_suppression", "input_threshold", "show_minibar",
)
_LANGUAGES = ["auto", "en", "hi", "kn", "es", "fr", "de", "it", "pt", "ja", "zh"]


def _bare_device_name(label):
    """Strip a device label's ' — <HostAPI>' suffix so the remainder is a valid
    AudioCapture name-substring. Empty/None -> None (auto)."""
    if not label:
        return None
    return label.rsplit("—", 1)[0].strip() or None


def _set_taskbar_visible(hwnd: int, visible: bool):
    """Toggle taskbar appearance cleanly via Win32 styles without WinForms RecreateHandle."""
    if sys.platform != "win32" or not hwnd:
        return
    try:
        import ctypes
        GWL_EXSTYLE = -20
        WS_EX_TOOLWINDOW = 0x00000080
        WS_EX_APPWINDOW = 0x00040000
        SWP_NOMOVE = 0x0002
        SWP_NOSIZE = 0x0001
        SWP_NOZORDER = 0x0004
        SWP_FRAMECHANGED = 0x0020
        cur = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        if visible:
            new_style = (cur | WS_EX_APPWINDOW) & ~WS_EX_TOOLWINDOW
        else:
            new_style = (cur | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
        ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)
    except Exception as e:
        log.debug("set_taskbar_visible error: %s", e)


def _clamp_to_workarea(window, w: int, h: int):
    """Keep a (just-resized) window fully inside the monitor work area (Win32),
    so a pill dragged to a screen edge can't reopen the full window offscreen."""
    if sys.platform != "win32":
        return
    try:
        import System.Windows.Forms as WinForms
        from webview.platforms.winforms import BrowserView
        form = BrowserView.instances.get(window.uid)
        if form is None:
            return
        wa = WinForms.Screen.FromControl(form).WorkingArea
        x = min(max(form.Left, wa.X), wa.X + wa.Width - w)
        y = min(max(form.Top, wa.Y), wa.Y + wa.Height - h)
        if (x, y) != (form.Left, form.Top):
            window.move(x, y)
    except Exception as e:
        log.debug("clamp_to_workarea error: %s", e)


def _set_launch_at_login(enabled: bool):
    """Register/unregister "SayIt" under the per-user Windows startup key
    (HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run) via winreg.
    Never raises -- the registry may be locked; log and continue. No-op off
    Windows."""
    if sys.platform != "win32":
        return
    try:
        import winreg
        run_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key, 0,
                            winreg.KEY_SET_VALUE) as key:
            if enabled:
                if getattr(sys, "frozen", False):
                    cmd = f'"{sys.executable}"'            # the built SayIt.exe
                else:
                    cmd = f'"{sys.executable}" -m wisper'  # dev: python -m wisper
                winreg.SetValueEx(key, "SayIt", 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(key, "SayIt")
                except FileNotFoundError:
                    pass  # already absent
    except Exception as e:
        log.warning("[wisper] set_launch_at_login error: %s", e)


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
            "noise_suppression": c.noise_suppression,
            "input_threshold": c.input_threshold,
            "launch_at_login": c.launch_at_login,
            "show_minibar": c.show_minibar,
        }

    def get_options(self):
        return {
            "cleanup_modes": ["light", "casual", "formal", "structured", "raw"],
            "paste_modes": ["auto", "ctrl_v", "ctrl_shift_v", "off"],
            "stt_providers": ["groq", "local"],
            "groq_models": list(stt.GROQ_AVAILABLE_MODELS),
            "languages": list(_LANGUAGES),
            "local_models": list(models.AVAILABLE_MODELS),
        }

    def set_setting(self, key, value):
        if key == "input_device":
            self.set_device(value)  # updates config + live device + monitor restart
            return None
        if key == "launch_at_login":
            enabled = bool(value)
            self.app.config.launch_at_login = enabled
            self.app.config.save()
            _set_launch_at_login(enabled)  # OS startup registration side effect
            return None
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
        """Non-blocking: kick off a background download and return at once.
        The frontend ignores this return and polls download_progress()."""
        try:
            models.start_download(name)
            return {"name": name, "started": True, "error": None}
        except Exception as exc:
            return {"name": name, "started": False, "error": repr(exc)}

    def download_progress(self):
        return models.download_progress()

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

    def window_quit(self):
        """Completely exit the application."""
        global _tray_icon
        if _tray_icon is not None:
            try:
                _tray_icon.Visible = False
                _tray_icon.Dispose()
            except Exception:
                pass
            _tray_icon = None
        if self._window is not None:
            self._window.destroy()
        return None

    def set_window_mode(self, mode: str):
        """Switch between 'full' (720x720) and 'minibar' (120x32).
        In minibar mode, window stays on_top and becomes a compact floating bar,
        and is hidden from the taskbar (accessible via the Windows tray icon)."""
        if self._window is not None:
            try:
                if sys.platform == "win32":
                    try:
                        from webview.platforms.winforms import BrowserView
                        form = BrowserView.instances.get(self._window.uid)
                        if form is not None:
                            hwnd = int(form.Handle)
                            _set_taskbar_visible(hwnd, mode != "minibar")
                            if mode != "minibar":
                                try:
                                    from System import MethodInvoker
                                    import System.Windows.Forms as WinForms

                                    def _restore():
                                        # Activate() alone won't un-minimize a WinForms form.
                                        form.WindowState = WinForms.FormWindowState.Normal
                                        form.Activate()

                                    form.BeginInvoke(MethodInvoker(_restore))
                                except Exception:
                                    pass
                    except Exception as ex:
                        log.debug("taskbar toggle error: %s", ex)

                if mode == "minibar":
                    # Reduced to half: 120 width x 32 height
                    self._window.resize(120, 32)
                    try:
                        self._window.on_top = True
                    except Exception:
                        pass
                else:
                    try:
                        self._window.on_top = False
                    except Exception:
                        pass
                    self._window.resize(720, 720)
                    _clamp_to_workarea(self._window, 720, 720)
            except Exception as e:
                log.warning("[wisper] set_window_mode failed: %s", e)
        return None

    def window_drag(self):
        """Safe non-blocking window drag dummy. pywebview handles .pywebview-drag-region natively."""
        return True


_window = None     # module ref to the live window (single-window app)
_tray_icon = None  # Windows system tray notify icon


def _setup_windows_native(window, api):
    """Enable true DWM per-pixel transparency and system tray icon on Windows."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        import clr
        clr.AddReference("System.Windows.Forms")
        clr.AddReference("System.Drawing")
        import System.Windows.Forms as WinForms
        import System.Drawing as Drawing
        from System import MethodInvoker
        from webview.platforms.winforms import BrowserView

        form = BrowserView.instances.get(window.uid)
        if form is None:
            return

        def _init_native():
            try:
                class _MARGINS(ctypes.Structure):
                    _fields_ = [
                        ("cxLeftWidth", ctypes.c_int),
                        ("cxRightWidth", ctypes.c_int),
                        ("cyTopHeight", ctypes.c_int),
                        ("cyBottomHeight", ctypes.c_int),
                    ]

                hwnd = int(form.Handle)
                m = _MARGINS(-1, -1, -1, -1)
                ctypes.windll.dwmapi.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(m))
                form.BackColor = Drawing.Color.Black

                if hasattr(form, "browser") and hasattr(form.browser, "webview"):
                    form.browser.webview.DefaultBackgroundColor = Drawing.Color.Transparent

                # Setup System Tray NotifyIcon safely on the UI thread
                global _tray_icon
                if _tray_icon is None:
                    _tray_icon = WinForms.NotifyIcon()
                    # Frameless windows have no form.Icon; fall back to the stock
                    # application icon so the tray entry (and its menu) always shows.
                    _tray_icon.Icon = form.Icon if form.Icon is not None else Drawing.SystemIcons.Application
                    _tray_icon.Text = "Say It"
                    _tray_icon.Visible = True

                    menu = WinForms.ContextMenuStrip()
                    item_open = menu.Items.Add("Open Say It")
                    item_exit = menu.Items.Add("Exit")

                    def on_open(sender, e):
                        api.set_window_mode("full")

                    def on_exit(sender, e):
                        api.window_quit()

                    item_open.Click += on_open
                    item_exit.Click += on_exit
                    _tray_icon.ContextMenuStrip = menu

                    def on_tray_click(sender, e):
                        if hasattr(e, "Button") and str(e.Button) == "Left":
                            api.set_window_mode("full")

                    _tray_icon.Click += on_tray_click
                    _tray_icon.DoubleClick += on_open
            except Exception as inner_ex:
                log.warning("[wisper] _init_native error: %s", inner_ex)

        if form.InvokeRequired:
            form.BeginInvoke(MethodInvoker(_init_native))
        else:
            _init_native()
    except Exception as e:
        log.warning("[wisper] _setup_windows_native failed: %s", e)


def launch(app):
    """Create the frameless native window and block on the pywebview loop.

    Windows uses the default edgechromium/WebView2 backend with transparent
    windowing so only the floating pill renders in minibar mode.
    """
    global _window
    import os
    os.environ["WEBVIEW2_DEFAULT_BACKGROUND_COLOR"] = "0"
    import webview  # lazy: keeps this module importable/testable without pywebview

    api = Api(app)
    _window = webview.create_window(
        "Say It",
        url=(_BUILT if _BUILT.exists() else _INDEX).as_uri(),
        js_api=api,
        width=720,
        height=720,
        min_size=(80, 24),
        frameless=True,
        transparent=True,
        easy_drag=False,
    )
    api._window = _window

    def on_shown():
        _setup_windows_native(_window, api)

    _window.events.shown += on_shown
    try:
        webview.start()
    finally:
        global _tray_icon
        if _tray_icon is not None:
            try:
                _tray_icon.Visible = False
                _tray_icon.Dispose()
            except Exception:
                pass
            _tray_icon = None
