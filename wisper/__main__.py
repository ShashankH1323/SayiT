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

        def _excepthook(exc_type, exc_value, exc_traceback):
            logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
            try:
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
            except Exception:
                pass

        sys.excepthook = _excepthook

        # sys.excepthook only fires for the MAIN thread; the hotkey listener and
        # audio callbacks run on background threads. Log their crashes too, so a
        # silently-dying listener (hotkey stops responding — reads as a freeze)
        # leaves a trace instead of nothing.
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
        pass  # logging setup must never crash startup


def main() -> None:
    _setup_logging()
    log = logging.getLogger("wisper")
    cfg = Config.load()
    app = WisperApp(cfg)

    classic = "--classic" in sys.argv or os.environ.get("WISPER_UI", "").lower() == "classic"
    if classic:
        try:
            app.run()  # existing path: starts the hotkey listener + tkinter mainloop
        except KeyboardInterrupt:
            pass
        log.info("[wisper] stopped")
        print("[wisper] stopped")
        return

    # Native UI. Start the hotkey listener exactly as WisperApp.run() does, then
    # block on the webview loop instead of tkinter's mainloop.
    from wisper import webui

    # Bail out before touching the global hotkey hook if another instance owns it,
    # so a rejected second process doesn't briefly grab the system-wide hotkey.
    if not webui._acquire_single_instance():
        log.warning("[wisper] another instance is already running; exiting")
        return

    from wisper.hotkey import HotkeyListener

    try:
        app._listener = HotkeyListener(app.config.hotkey, app.toggle)
        app._listener.start()
        msg = f"[wisper] ready — press {app.config.hotkey} to dictate"
        log.info(msg)
        print(msg)
    except Exception as exc:
        log.warning("[wisper] hotkey listener failed to start: %s", exc)

    try:
        webui.launch(app)  # blocks until the window is closed
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        log.exception("[wisper] unhandled error in webui.launch: %s", exc)
    finally:
        try:
            app.audio.stop()  # release the mic if we tore down mid-recording
        except Exception:
            pass
        if getattr(app, "_listener", None) is not None:
            try:
                app._listener.stop()
            except Exception:
                pass
    log.info("[wisper] stopped")
    print("[wisper] stopped")


if __name__ == "__main__":
    main()
