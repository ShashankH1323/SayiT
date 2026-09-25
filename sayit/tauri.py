"""Tauri Bridge & IPC Server for Say It backend.

Supports two Tauri integration patterns:
1. Tauri Sidecar via stdio IPC (`--tauri-ipc`):
   Tauri executes Say It as a child process and sends JSON-lines over stdin,
   receiving JSON-lines responses and events over stdout.
2. Tauri Localhost HTTP Server (`--server`):
   A lightweight, zero-dependency REST API with CORS headers so Tauri's frontend
   can fetch `http://localhost:47888/api/...`.
"""

from __future__ import annotations

import json
import logging
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

from sayit import audio, history, models, stt
from sayit.app import SayItApp

log = logging.getLogger("sayit")


class SayItBridge:
    """JSON-serializable API controller wrapping SayItApp."""

    def __init__(self, app: SayItApp):
        self.app = app

    def get_status(self) -> dict:
        try:
            level = float(self.app.audio.current_level())
        except Exception:
            level = 0.0
        return {
            "state": self.app.state.value,
            "last_text": self.app.last_text or "",
            "last_error": self.app.last_error or None,
            "level": max(0.0, min(1.0, level)),
        }

    def toggle(self) -> dict:
        self.app.toggle()
        return {"success": True, "state": self.app.state.value}

    def cancel(self) -> dict:
        self.app.cancel()
        return {"success": True, "state": self.app.state.value}

    def list_devices(self) -> list[str]:
        return [label for label, _ in audio.list_input_devices()]

    def refresh_devices(self) -> list[str]:
        return [label for label, _ in audio.refresh_input_devices()]

    def set_device(self, name: str | None) -> dict:
        bare = name.rsplit("—", 1)[0].strip() if name else None
        self.app.audio.device = bare
        self.app.config.input_device = bare
        self.app.config.save()
        return {"success": True, "device": bare}

    def get_settings(self) -> dict:
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
            "stt_provider": getattr(c, "stt_provider", "groq"),
            "groq_model": getattr(c, "groq_model", "whisper-large-v3-turbo"),
            "sound_effects": getattr(c, "sound_effects", True),
            "history_size": c.history_size,
            "paste_mode": getattr(c, "paste_mode", "auto"),
            "noise_suppression": getattr(c, "noise_suppression", False),
            "input_threshold": getattr(c, "input_threshold", 0.0),
        }

    def set_setting(self, key: str, val) -> dict:
        if key == "hotkey":
            self.app.set_hotkey(str(val))
        elif key == "stt_provider":
            self.app.set_stt_provider(str(val))
        elif key == "groq_model":
            self.app.set_groq_model(str(val))
        elif key == "model":
            self.app.set_model(str(val))
        elif hasattr(self.app.config, key):
            setattr(self.app.config, key, val)
            self.app.config.save()
        return {"success": True, "key": key, "val": val}

    def get_models(self) -> dict:
        local_status = dict(models.model_status())
        return {
            "groq_models": list(stt.GROQ_AVAILABLE_MODELS),
            "local_models": [
                {"name": m, "downloaded": bool(local_status.get(m, False))}
                for m in models.AVAILABLE_MODELS
            ],
        }

    def download_model(self, name: str) -> dict:
        threading.Thread(target=models.download, args=(name,), daemon=True).start()
        return {"success": True, "downloading": name}

    def list_history(self, limit: int = 50) -> list[dict]:
        return history.load(limit)

    def delete_history(self, ts: str, text: str) -> dict:
        history.delete_record(ts, text)
        return {"success": True}

    def clear_history(self) -> dict:
        history.clear_all()
        return {"success": True}

    def copy_to_clipboard(self, text: str) -> dict:
        import pyperclip
        pyperclip.copy(text)
        return {"success": True}


def run_stdio_ipc(app: SayItApp) -> None:
    """Run line-delimited JSON-RPC loop over stdin/stdout for Tauri sidecar."""
    from sayit.hotkey import HotkeyListener

    bridge = SayItBridge(app)
    app._listener = HotkeyListener(app.config.hotkey, app.toggle)
    app._listener.start()
    log.info("[sayit] Tauri stdio IPC active")

    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except Exception as e:
                resp = {"error": f"Invalid JSON: {e}"}
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()
                continue

            msg_id = req.get("id")
            cmd = req.get("cmd")
            args = req.get("args", {})

            try:
                if cmd == "status":
                    res = bridge.get_status()
                elif cmd == "toggle":
                    res = bridge.toggle()
                elif cmd == "cancel":
                    res = bridge.cancel()
                elif cmd == "devices":
                    res = bridge.list_devices()
                elif cmd == "refresh_devices":
                    res = bridge.refresh_devices()
                elif cmd == "set_device":
                    res = bridge.set_device(args.get("name"))
                elif cmd == "settings":
                    res = bridge.get_settings()
                elif cmd == "set_setting":
                    res = bridge.set_setting(args.get("key"), args.get("val"))
                elif cmd == "models":
                    res = bridge.get_models()
                elif cmd == "download_model":
                    res = bridge.download_model(args.get("name"))
                elif cmd == "history":
                    res = bridge.list_history(args.get("limit", 50))
                elif cmd == "delete_history":
                    res = bridge.delete_history(args.get("ts"), args.get("text"))
                elif cmd == "clear_history":
                    res = bridge.clear_history()
                elif cmd == "copy":
                    res = bridge.copy_to_clipboard(args.get("text", ""))
                else:
                    res = {"error": f"Unknown command: {cmd}"}

                resp = {"id": msg_id, "result": res}
            except Exception as exc:
                resp = {"id": msg_id, "error": str(exc)}

            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            app.audio.stop()
        except Exception:
            pass
        if app._listener:
            app._listener.stop()


def make_http_handler(bridge: SayItBridge):
    """Create a CORS-enabled HTTP handler bound to a SayItBridge instance."""
    class SayItHTTPHandler(BaseHTTPRequestHandler):
        def _send_cors_headers(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

        def do_OPTIONS(self):
            self.send_response(204)
            self._send_cors_headers()
            self.end_headers()

        def _send_json(self, data: dict | list, status: int = 200):
            payload = json.dumps(data).encode("utf-8")
            self.send_response(status)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _read_json(self) -> dict:
            try:
                length = int(self.headers.get("Content-Length", 0))
                if length > 0:
                    raw = self.rfile.read(length)
                    return json.loads(raw.decode("utf-8"))
            except Exception:
                pass
            return {}

        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/")
            if path in ("/api/status", "/status"):
                self._send_json(bridge.get_status())
            elif path in ("/api/settings", "/settings"):
                self._send_json(bridge.get_settings())
            elif path in ("/api/devices", "/devices"):
                self._send_json(bridge.list_devices())
            elif path in ("/api/models", "/models"):
                self._send_json(bridge.get_models())
            elif path in ("/api/history", "/history"):
                qs = parse_qs(parsed.query)
                limit = int(qs.get("limit", [50])[0])
                self._send_json(bridge.list_history(limit))
            else:
                self._send_json({"error": "Not found", "path": path}, status=404)

        def do_POST(self):
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/")
            body = self._read_json()

            if path in ("/api/toggle", "/toggle"):
                self._send_json(bridge.toggle())
            elif path in ("/api/cancel", "/cancel"):
                self._send_json(bridge.cancel())
            elif path in ("/api/devices/refresh", "/devices/refresh"):
                self._send_json(bridge.refresh_devices())
            elif path in ("/api/devices/set", "/devices/set"):
                self._send_json(bridge.set_device(body.get("name")))
            elif path in ("/api/settings", "/settings"):
                key = body.get("key")
                val = body.get("val")
                self._send_json(bridge.set_setting(key, val))
            elif path in ("/api/models/download", "/models/download"):
                self._send_json(bridge.download_model(body.get("name")))
            elif path in ("/api/history/delete", "/history/delete"):
                self._send_json(bridge.delete_history(body.get("ts"), body.get("text")))
            elif path in ("/api/history/clear", "/history/clear"):
                self._send_json(bridge.clear_history())
            elif path in ("/api/copy", "/copy"):
                self._send_json(bridge.copy_to_clipboard(body.get("text", "")))
            else:
                self._send_json({"error": "Not found", "path": path}, status=404)

        def log_message(self, format, *args):
            pass  # Suppress default server log spam

    return SayItHTTPHandler


def run_server(app: SayItApp, port: int = 47888, host: str = "127.0.0.1") -> None:
    """Run a local CORS-enabled HTTP server for Tauri frontends."""
    from sayit.hotkey import HotkeyListener

    bridge = SayItBridge(app)
    app._listener = HotkeyListener(app.config.hotkey, app.toggle)
    app._listener.start()

    handler_cls = make_http_handler(bridge)
    httpd = HTTPServer((host, port), handler_cls)
    msg = f"[sayit] HTTP API server listening on http://{host}:{port} — ready for Tauri"
    log.info(msg)
    print(msg)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        try:
            app.audio.stop()
        except Exception:
            pass
        if app._listener:
            app._listener.stop()
