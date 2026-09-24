"""Entry point.

Default: `python -m wisper` launches the native pywebview UI.
Fallback: `python -m wisper --classic` (or env WISPER_UI=classic) runs the old
tkinter UI via the existing WisperApp.run() path, so nothing is lost.

Composition root only -- it wires Config -> WisperApp -> a UI. It never touches
the functional core; for the native path it mirrors just the hotkey startup
that run() does, then hands off to webui.launch().
"""

import logging
import os
import sys
from pathlib import Path

from wisper.app import WisperApp
from wisper.config import Config


def _setup_logging() -> None:
    """Give frozen (--noconsole) builds a file to leave tracebacks in.

    Without a handler, `--noconsole` crashes vanish silently. Mirrors the
    frozen/dev path split used in config.py/history.py.
    """
    try:
        logger = logging.getLogger("wisper")
        if logger.handlers:  # main() may run twice; don't stack handlers
            return
        if getattr(sys, "frozen", False):
            log_path = Path(sys.executable).parent / "wisper.log"
        else:
            log_path = Path(__file__).resolve().parent.parent / "wisper.log"
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    except Exception:
        pass  # logging setup must never crash startup


def main() -> None:
    _setup_logging()
    cfg = Config.load()
    app = WisperApp(cfg)

    classic = "--classic" in sys.argv or os.environ.get("WISPER_UI", "").lower() == "classic"
    if classic:
        try:
            app.run()  # existing path: starts the hotkey listener + tkinter mainloop
        except KeyboardInterrupt:
            pass
        print("[wisper] stopped")
        return

    # Native UI. Start the hotkey listener exactly as WisperApp.run() does, then
    # block on the webview loop instead of tkinter's mainloop.
    from wisper.hotkey import HotkeyListener
    from wisper import webui

    app._listener = HotkeyListener(app.config.hotkey, app.toggle)
    app._listener.start()
    msg = f"[wisper] ready — press {app.config.hotkey} to dictate"
    print(msg)
    try:
        webui.launch(app)  # blocks until the window is closed
    except KeyboardInterrupt:
        pass
    finally:
        try:
            app.audio.stop()  # release the mic if we tore down mid-recording
        except Exception:
            pass
        app._listener.stop()
    print("[wisper] stopped")


if __name__ == "__main__":
    main()
