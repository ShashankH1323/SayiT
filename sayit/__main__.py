"""Entry point for Say It.

Default: `python -m sayit` launches the native settings & dictation control window.
Tauri Server: `python -m sayit --server [--port 47888]` launches the local HTTP API for Tauri.
Tauri Sidecar: `python -m sayit --tauri-ipc` launches the stdio JSON-RPC loop for Tauri.
Headless: `python -m sayit --headless` runs the background dictation hotkey without a window.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from sayit.app import SayItApp
from sayit.config import Config


def _setup_logging() -> None:
    try:
        logger = logging.getLogger("sayit")
        if logger.handlers:
            return
        if getattr(sys, "frozen", False):
            log_path = Path(sys.executable).parent / "sayit.log"
        else:
            log_path = Path(__file__).resolve().parent.parent / "sayit.log"
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        def _excepthook(exc_type, exc_value, exc_traceback):
            logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
            try:
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
            except Exception:
                pass

        sys.excepthook = _excepthook

        import threading

        def _thread_excepthook(args):
            if args.exc_type is SystemExit:
                return
            logger.critical(
                "Uncaught exception in thread %r",
                getattr(args.thread, "name", "?"),
                exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
            )

        threading.excepthook = _thread_excepthook
    except Exception:
        pass


def main() -> None:
    _setup_logging()
    log = logging.getLogger("sayit")
    cfg = Config.load()
    app = SayItApp(cfg)

    # Tauri stdio IPC sidecar mode
    if "--tauri-ipc" in sys.argv:
        from sayit.tauri import run_stdio_ipc
        run_stdio_ipc(app)
        return

    # Tauri HTTP API server mode
    if "--server" in sys.argv:
        from sayit.tauri import run_server
        port = 47888
        for i, arg in enumerate(sys.argv):
            if arg == "--port" and i + 1 < len(sys.argv):
                try:
                    port = int(sys.argv[i + 1])
                except ValueError:
                    pass
        run_server(app, port=port)
        return

    # Headless mode (hotkey listener without GUI)
    if "--headless" in sys.argv or "--no-ui" in sys.argv:
        from sayit.hotkey import HotkeyListener
        import threading
        app._listener = HotkeyListener(app.config.hotkey, app.toggle)
        app._listener.start()
        msg = f"[sayit] ready (headless) — press {app.config.hotkey} to dictate"
        log.info(msg)
        print(msg)
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass
        finally:
            try:
                app.audio.stop()
            except Exception:
                pass
            app._listener.stop()
        print("[sayit] stopped")
        return

    # Default: launch the clean, fast native settings & dictation window
    try:
        app.run()
    except KeyboardInterrupt:
        pass
    log.info("[sayit] stopped")
    print("[sayit] stopped")


if __name__ == "__main__":
    main()
