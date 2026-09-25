"""Tests for Say It Tauri bridge and HTTP API server."""

import json
from unittest.mock import MagicMock
from sayit.app import SayItApp, State
from sayit.config import Config
from sayit.tauri import SayItBridge, make_http_handler


class FakeAudio:
    def __init__(self):
        self._recording = False
        self.device = None

    def start(self):
        self._recording = True

    def stop(self):
        self._recording = False
        return None

    def current_level(self):
        return 0.42


def test_tauri_bridge_status():
    app = SayItApp(Config(), audio=FakeAudio(), stt=MagicMock(), paste=MagicMock())
    bridge = SayItBridge(app)
    status = bridge.get_status()
    assert status["state"] == "idle"
    assert status["last_text"] == ""
    assert status["last_error"] is None
    assert 0.0 <= status["level"] <= 1.0


def test_tauri_bridge_settings():
    app = SayItApp(Config(), audio=FakeAudio(), stt=MagicMock(), paste=MagicMock())
    bridge = SayItBridge(app)
    settings = bridge.get_settings()
    assert "hotkey" in settings
    assert "model" in settings
    assert "stt_provider" in settings

    res = bridge.set_setting("cleanup_mode", "casual")
    assert res["success"] is True
    assert app.config.cleanup_mode == "casual"


def test_tauri_bridge_toggle_cancel():
    app = SayItApp(Config(), audio=FakeAudio(), stt=MagicMock(), paste=MagicMock())
    bridge = SayItBridge(app)
    res = bridge.toggle()
    assert res["success"] is True
    assert res["state"] == "recording"

    res_cancel = bridge.cancel()
    assert res_cancel["success"] is True
    assert res_cancel["state"] == "idle"


def test_tauri_bridge_models_and_devices():
    app = SayItApp(Config(), audio=FakeAudio(), stt=MagicMock(), paste=MagicMock())
    bridge = SayItBridge(app)
    models_info = bridge.get_models()
    assert "groq_models" in models_info
    assert "local_models" in models_info

    devices = bridge.list_devices()
    assert isinstance(devices, list)


def test_tauri_bridge_history():
    app = SayItApp(Config(), audio=FakeAudio(), stt=MagicMock(), paste=MagicMock())
    bridge = SayItBridge(app)
    hist = bridge.list_history(limit=5)
    assert isinstance(hist, list)
