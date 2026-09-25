"""Shared configuration contract for Say It (stdlib-only, no pydantic)."""

from __future__ import annotations

import json
import logging
import tempfile
import threading
from dataclasses import asdict, dataclass, fields
from pathlib import Path

log = logging.getLogger("sayit")

import os
import sys

_save_lock = threading.Lock()  # serializes config writes across worker threads

def get_config_path() -> Path:
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        portable_cfg = exe_dir / "config.json"
        # If config exists next to exe or directory is writable, use it
        if portable_cfg.exists():
            return portable_cfg
        try:
            test = exe_dir / ".test_write"
            test.touch()
            test.unlink()
            return portable_cfg
        except Exception:
            appdata = os.environ.get("APPDATA")
            if appdata:
                d = Path(appdata) / "SayIt"
                d.mkdir(parents=True, exist_ok=True)
                return d / "config.json"
    return Path(__file__).resolve().parent.parent / "config.json"

_DEFAULT_PATH = get_config_path()


@dataclass
class Config:
    hotkey: str = "ctrl+space"          # `keyboard` lib format (matches shipped config.json + UI default)
    input_device: int | str | None = None  # mic name substring (stable) or legacy index; None = auto
    samplerate: int = 16000             # target rate fed to STT
    model: str = "large-v3-turbo"       # faster-whisper model name
    device: str = "cuda"                # cuda | cpu
    compute_type: str = "float16"       # float16 | int8_float16 | int8
    language: str | None = "en"         # spoken language; None = auto-detect
    output_language: str = "en"         # desired output language
    cleanup_mode: str = "light"         # light | casual | formal | structured | raw
    stt_provider: str = "groq"          # groq | local
    groq_model: str = "whisper-large-v3-turbo" # whisper-large-v3-turbo | whisper-large-v3
    sound_effects: bool = True          # warm audio cues on start/stop/paste
    history_size: int = 50
    paste_mode: str = "auto"            # auto | ctrl_v | ctrl_shift_v
    noise_suppression: bool = False     # pre-STT denoise (off = identical to today)
    input_threshold: float = 0.0        # 0..1 silence-gate floor (0 = no gating)
    launch_at_login: bool = False       # start with the OS session
    show_minibar: bool = False          # floating recording mini-bar
    config_version: int = 2             # schema version

    @classmethod
    def load(cls, path: str | Path = _DEFAULT_PATH) -> "Config":
        """Load config, writing defaults on first run.

        Missing file -> return defaults and persist them to `path`.
        Present file -> merge over defaults: unknown keys ignored,
        missing keys keep their defaults. Corrupt JSON -> warn, use defaults.
        """
        p = Path(path)
        if not p.exists():
            cfg = cls()
            try:
                cfg.save(p)
            except OSError as e:
                log.warning("config %s unwritable (%s); using in-memory defaults", p, e)
            return cfg
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            log.warning("config %s unreadable (%s); using defaults", p, e)
            return cls()
        if not isinstance(data, dict):
            return cls()
        known = {f.name for f in fields(cls)}
        overrides = {k: v for k, v in data.items() if k in known}
        iv = overrides.get("input_device")
        if isinstance(iv, int) and not isinstance(iv, bool):
            overrides["input_device"] = str(iv)  # legacy int index -> string contract
        cfg = cls(**overrides)
        # one-time opt-in migration: pre-v2 configs auto-ran an engine; force an explicit choice
        ver = data.get("config_version")
        if not isinstance(ver, int) or ver < 2:
            cfg.stt_provider = "none"        # only field flipped; all other saved keys kept
            cfg.config_version = 2
            try:
                cfg.save(p)                  # persist so the migration never re-runs
            except OSError as e:
                log.warning("config %s unwritable (%s); migration not persisted", p, e)
        return cfg

    def save(self, path: str | Path = _DEFAULT_PATH) -> None:
        """Write atomically: serialized by a module lock, then temp file in the
        SAME dir + os.replace, so a concurrent read/write never sees a torn file."""
        p = Path(path)
        content = json.dumps(asdict(self), indent=2) + "\n"
        with _save_lock:
            fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=p.name + ".", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(content)
                os.replace(tmp, p)
            except OSError:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise


if __name__ == "__main__":  # migration self-check (stdlib only, no framework)
    import tempfile

    with tempfile.TemporaryDirectory() as _d:
        _p = Path(_d) / "config.json"
        # v1-style on-disk config: no config_version, engine was auto-on (groq)
        _p.write_text(json.dumps({
            "stt_provider": "groq", "hotkey": "ctrl+alt+x",
            "input_device": 3, "model": "small", "history_size": 7,
        }), encoding="utf-8")
        _c = Config.load(_p)
        assert _c.stt_provider == "none", _c.stt_provider          # flipped to opt-in
        assert _c.config_version == 2, _c.config_version           # version bumped
        assert _c.hotkey == "ctrl+alt+x"                           # other keys preserved
        assert _c.input_device == "3"                              # legacy int coerced, kept
        assert _c.model == "small"
        assert _c.history_size == 7
        _again = Config.load(_p)                                   # v2 on disk now
        assert _again.config_version == 2 and _again.stt_provider == "none"  # no re-run
        print("config migration self-check PASSED")
