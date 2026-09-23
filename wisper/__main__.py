"""Entry point: `python -m wisper` runs the dictation orchestrator until Ctrl+C."""

from wisper.app import WisperApp
from wisper.config import Config


def main() -> None:
    cfg = Config.load()
    app = WisperApp(cfg)
    try:
        app.run()
    except KeyboardInterrupt:
        pass
    print("[wisper] stopped")


if __name__ == "__main__":
    main()
