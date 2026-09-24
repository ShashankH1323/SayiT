"""Standalone self-test for the pywebview bridge (wisper/webui.py::Api).

Run: python tests/test_webui_bridge.py   (no pytest; prints PASS/FAIL per check,
exits non-zero on any failure). Uses fakes for the WisperApp, its audio/config,
and monkeypatches the wisper.audio/history/models modules the Api calls, so it
needs no GPU, mic, keyboard, pywebview, or the real config.json/history.jsonl.
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wisper import webui
from wisper.webui import Api
from wisper.app import State
from wisper.config import Config
from wisper import stt as real_stt, models as real_models

logging.getLogger("wisper").setLevel(logging.CRITICAL)  # silence expected warnings


class FakeCapture:
    """Stands in for app.audio (the AudioCapture instance)."""

    def __init__(self):
        self.device = None
        self._level = 0.0
        self._monitoring = False

    def start_monitor(self, dev=None):
        self._monitoring = True

    def stop_monitor(self):
        self._monitoring = False

    def current_level(self):
        return self._level


class FakeWindow:
    def __init__(self):
        self.calls = []
        self.uid = "fake-win-1"
        self.on_top = False
        self.size = (720, 720)

    def minimize(self):
        self.calls.append("minimize")

    def destroy(self):
        self.calls.append("destroy")

    def resize(self, w, h):
        self.size = (w, h)
        self.calls.append(("resize", w, h))


class FakeApp:
    """Records routed calls; holds a real Config with save() stubbed to a counter."""

    def __init__(self):
        self.state = State.IDLE
        self.last_text = ""
        self.last_error = ""
        self.audio = FakeCapture()
        self.config = Config()
        self.saves = []
        self.config.save = lambda *a, **k: self.saves.append(1)  # never touch real config.json
        self.calls = []

    def toggle(self):
        self.calls.append(("toggle",))

    def cancel(self):
        self.calls.append(("cancel",))

    def set_hotkey(self, v):
        self.calls.append(("set_hotkey", v))

    def set_stt_provider(self, v):
        self.calls.append(("set_stt_provider", v))

    def set_groq_model(self, v):
        self.calls.append(("set_groq_model", v))

    def set_model(self, v):
        self.calls.append(("set_model", v))


_fails = []


def check(name, cond, detail=""):
    ok = bool(cond)
    print(f"{'PASS' if ok else 'FAIL'}: {name}" + (f"  ({detail})" if detail and not ok else ""))
    if not ok:
        _fails.append(name)


class FakeAudioModule:
    """Stands in for the wisper.audio module (list/refresh only)."""

    def __init__(self, devices):
        self._devices = devices
        self.refreshed = False

    def list_input_devices(self):
        return list(self._devices)

    def refresh_input_devices(self):
        self.refreshed = True
        return list(self._devices)


class FakeHistoryModule:
    def __init__(self):
        self.calls = []

    def load(self, size=None):
        self.calls.append(("load", size))
        return [{"ts": "2026-01-01T00:00:00", "text": "hello"}]

    def delete_record(self, ts, text):
        self.calls.append(("delete_record", ts, text))
        return True

    def clear_all(self):
        self.calls.append(("clear_all",))


class FakeModelsModule:
    def __init__(self, status, dl_result=None, dl_error=None, downloaded=False):
        self._status = status
        self._dl_result = dl_result
        self._dl_error = dl_error
        self._downloaded = downloaded
        self.started = []

    def model_status(self):
        return list(self._status)

    def download(self, name):
        if self._dl_error is not None:
            raise self._dl_error
        return self._dl_result

    def start_download(self, name):
        if self._dl_error is not None:
            raise self._dl_error
        self.started.append(name)

    def download_progress(self):
        return {"active": bool(self.started), "name": self.started[-1] if self.started else None, "done": False, "error": None, "pct": 50.0}

    def is_downloaded(self, name):
        return self._downloaded


def swap(attr, value):
    """Temporarily replace webui.<attr>, returning the original for restore."""
    orig = getattr(webui, attr)
    setattr(webui, attr, value)
    return orig


def test_status_and_control():
    app = FakeApp()
    api = Api(app)

    expected = {
        State.IDLE: "idle", State.RECORDING: "recording",
        State.TRANSCRIBING: "processing", State.CLEANING: "processing",
        State.PASTING: "processing", State.ERROR: "error",
    }
    for member, want in expected.items():
        app.state = member
        check(f"get_status maps {member.name}->{want}", api.get_status()["state"] == want)

    app.state = State.IDLE
    s = api.get_status()
    check("get_status keys", set(s) == {"state", "last_text", "last_error", "level"}, sorted(s))
    check("get_status last_error '' -> None", s["last_error"] is None)

    app.audio._level = 0.42
    check("get_status level passthrough", abs(api.get_status()["level"] - 0.42) < 1e-9)
    app.audio._level = 2.0
    check("get_status level clamps high", api.get_status()["level"] == 1.0)
    app.audio._level = -1.0
    check("get_status level clamps low", api.get_status()["level"] == 0.0)
    app.last_text, app.last_error = "hi there", "Boom()"
    s = api.get_status()
    check("get_status last_text", s["last_text"] == "hi there")
    check("get_status last_error passthrough", s["last_error"] == "Boom()")

    check("toggle returns None", api.toggle() is None)
    check("cancel returns None", api.cancel() is None)
    check("toggle/cancel routed", app.calls == [("toggle",), ("cancel",)], app.calls)
    check("start_preview returns None", api.start_preview() is None)
    check("start_preview set monitoring", app.audio._monitoring is True)
    check("stop_preview returns None", api.stop_preview() is None)
    check("stop_preview stopped monitoring", app.audio._monitoring is False)


def test_settings_options():
    app = FakeApp()
    api = Api(app)

    want_keys = {"hotkey", "input_device", "model", "device", "compute_type",
                 "samplerate", "language", "output_language", "cleanup_mode",
                 "stt_provider", "groq_model", "sound_effects", "history_size",
                 "paste_mode", "noise_suppression", "input_threshold",
                 "launch_at_login", "show_minibar"}
    settings = api.get_settings()
    check("get_settings keys", set(settings) == want_keys, sorted(settings))
    check("get_settings values match config", settings["hotkey"] == app.config.hotkey
          and settings["model"] == app.config.model)

    opts = api.get_options()
    check("get_options keys", set(opts) == {"cleanup_modes", "paste_modes",
          "stt_providers", "groq_models", "languages", "local_models"}, sorted(opts))
    check("get_options cleanup_modes", opts["cleanup_modes"] ==
          ["light", "casual", "formal", "structured", "raw"])
    check("get_options paste_modes", opts["paste_modes"] == ["auto", "ctrl_v", "ctrl_shift_v", "off"])
    check("get_options stt_providers", opts["stt_providers"] == ["groq", "local"])
    check("get_options groq_models = real", opts["groq_models"] == list(real_stt.GROQ_AVAILABLE_MODELS))
    check("get_options local_models = real", opts["local_models"] == list(real_models.AVAILABLE_MODELS))
    check("get_options languages incl auto", "auto" in opts["languages"] and len(opts["languages"]) > 1)


def test_set_setting_and_device():
    app = FakeApp()
    api = Api(app)

    check("set_setting hotkey routes to method", api.set_setting("hotkey", "ctrl+x") is None)
    check("set_setting stt_provider routes", api.set_setting("stt_provider", "local") is None)
    api.set_setting("groq_model", "whisper-large-v3")
    api.set_setting("model", "small")
    check("special keys -> app methods", app.calls == [
        ("set_hotkey", "ctrl+x"), ("set_stt_provider", "local"),
        ("set_groq_model", "whisper-large-v3"), ("set_model", "small")], app.calls)

    saves_before = len(app.saves)
    api.set_setting("language", "hi")
    check("config key setattr", app.config.language == "hi")
    check("config key saved", len(app.saves) == saves_before + 1)

    saves_before = len(app.saves)
    api.set_setting("bogus_key", 123)
    check("unknown key ignored (no setattr)", not hasattr(app.config, "bogus_key"))
    check("unknown key not saved", len(app.saves) == saves_before)

    saves_before = len(app.saves)
    check("set_device returns None", api.set_device("Mic B — MME") is None)
    check("set_device strips api suffix -> audio.device", app.audio.device == "Mic B")
    check("set_device -> config.input_device", app.config.input_device == "Mic B")
    check("set_device saved", len(app.saves) == saves_before + 1)
    api.set_device("")
    check("set_device empty -> None (auto)", app.audio.device is None)


def test_devices_history_models_window():
    app = FakeApp()
    api = Api(app)

    fake_audio = FakeAudioModule([("Mic A — WASAPI", 3), ("Mic B — MME", 7)])
    orig = swap("audio", fake_audio)
    try:
        devs = api.list_devices()
        check("list_devices -> labels (str[])", devs == ["Mic A — WASAPI", "Mic B — MME"], devs)
        check("list_devices all str", all(isinstance(d, str) for d in devs))
        r = api.refresh_devices()
        check("refresh_devices returns labels", r == ["Mic A — WASAPI", "Mic B — MME"])
        check("refresh_devices calls refresh", fake_audio.refreshed)
    finally:
        swap("audio", orig)

    fake_hist = FakeHistoryModule()
    orig = swap("history", fake_hist)
    try:
        out = api.history_load(10)
        check("history_load returns records", out and out[0]["text"] == "hello")
        check("history_load passes size", ("load", 10) in fake_hist.calls)
        check("history_delete returns None", api.history_delete("t1", "x") is None)
        check("history_delete routed", ("delete_record", "t1", "x") in fake_hist.calls)
        check("history_clear returns None", api.history_clear() is None)
        check("history_clear routed", ("clear_all",) in fake_hist.calls)
    finally:
        swap("history", orig)

    orig = swap("models", FakeModelsModule([("m1", True), ("m2", False)]))
    try:
        check("models_status -> dict", api.models_status() == {"m1": True, "m2": False})
    finally:
        swap("models", orig)

    orig = swap("models", FakeModelsModule([], dl_result="/cache/m.bin"))
    try:
        r = api.download_model("large-v3")
        check("download_model ok shape", r == {"name": "large-v3", "started": True, "error": None}, r)
        prog = api.download_progress()
        check("download_progress shape", prog.get("active") is True, prog)
    finally:
        swap("models", orig)

    orig = swap("models", FakeModelsModule([], dl_error=RuntimeError("no fw"), downloaded=False))
    try:
        r = api.download_model("large-v3")
        check("download_model error shape", r.get("started") is False and "no fw" in str(r.get("error")), r)
    finally:
        swap("models", orig)

    # Preview audio monitor
    check("start_preview returns None", api.start_preview("Test Mic") is None)
    check("start_preview sets monitoring", app.audio._monitoring is True)
    check("stop_preview returns None", api.stop_preview() is None)
    check("stop_preview stops monitoring", app.audio._monitoring is False)

    win = FakeWindow()
    api._window = win
    check("window_minimize returns None", api.window_minimize() is None)
    check("window_close returns None", api.window_close() is None)
    check("window ops routed", "minimize" in win.calls and "destroy" in win.calls, win.calls)
    
    # window mode & drag
    check("window_drag returns True", api.window_drag() is True)
    check("set_window_mode minibar", api.set_window_mode("minibar") is None)
    check("set_window_mode full", api.set_window_mode("full") is None)
    check("window_quit returns None", api.window_quit() is None)

    api._window = None
    check("window ops no-op when no window", api.window_minimize() is None
          and api.window_close() is None and api.set_window_mode("full") is None)


def main():
    test_status_and_control()
    test_settings_options()
    test_set_setting_and_device()
    test_devices_history_models_window()
    print("-" * 40)
    if _fails:
        print(f"{len(_fails)} FAILED: {_fails}")
        sys.exit(1)
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()



