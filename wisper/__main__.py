"""Entry point.

Default: `python -m wisper` launches the native pywebview UI.
Fallback: `python -m wisper --classic` (or env WISPER_UI=classic) runs the old
tkinter UI via the existing WisperApp.run() path, so nothing is lost.

Composition root only -- it wires Config -> WisperApp -> a UI. It never touches
the functional core; for the native path it mirrors just the hotkey startup
that run() does, then hands off to webui.launch().
"""

import os
import sys

from wisper.app import WisperApp
from wisper.config import Config


def main() -> None:
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
