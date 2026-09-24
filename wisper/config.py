"""Shared configuration contract for Wisper (stdlib-only, no pydantic)."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, fields
from pathlib import Path

log = logging.getLogger("wisper")

import os
import sys

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
    hotkey: str = "ctrl+alt+space"      # `keyboard` lib format
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
    show_minibar: bool = True           # floating recording mini-bar

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
        return cls(**overrides)

    def save(self, path: str | Path = _DEFAULT_PATH) -> None:
        Path(path).write_text(json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8")
