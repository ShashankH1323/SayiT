"""Whisper model manager for Wisper: list / check / download models.

Pure logic for the UI "Models" panel — NO tkinter, NO UI. faster-whisper pulls
models from the HuggingFace Hub on first use; this module lists the curated set,
reports which are already in the local HF cache (no network), and downloads one
on demand (blocking — the caller threads it).

`faster_whisper` / `huggingface_hub` imports are guarded like audio.py guards
sounddevice, so `import wisper.models` never hard-crashes headless: functions
degrade gracefully (empty status, clear error on download) if they're missing.
"""
from __future__ import annotations

import logging
import os

log = logging.getLogger("wisper")

try:
    import faster_whisper as _fw
except Exception:  # pragma: no cover - optional; download() explains if missing
    _fw = None

try:
    from huggingface_hub import constants as _hf_constants
    from huggingface_hub import try_to_load_from_cache as _try_cache
except Exception:  # pragma: no cover - optional; is_downloaded degrades to False
    _hf_constants = None
    _try_cache = None


# Curated local on-device faster-whisper models (no cloud dependencies).
AVAILABLE_MODELS: list[str] = [
    "tiny",
    "base",
    "small",
    "medium",
]


def _repo_id(name: str) -> str:
    """HuggingFace repo id faster-whisper uses for a size id (Systran mirrors).

    Systran has no faster-whisper-large-v3-turbo repo; use the mobiuslabsgmbh
    conversion (already in the local HF cache) so is_downloaded()/download work.
    """
    if name == "large-v3-turbo":
        return "mobiuslabsgmbh/faster-whisper-large-v3-turbo"
    if name.startswith("distil-"):
        return "Systran/faster-distil-whisper-" + name[len("distil-"):]
    return "Systran/faster-whisper-" + name


def cache_dir() -> str:
    """The HF Hub cache dir where models land, for display."""
    if _hf_constants is not None:
        try:
            return str(_hf_constants.HF_HUB_CACHE)
        except Exception:  # pragma: no cover - defensive
            pass
    return os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub")


def is_downloaded(name: str) -> bool:
    """True if `name`'s model is already in the local HF cache. NO network call.

    # ponytail: cache-dir presence check (model.bin cached), not a checksum
    verify — corrupt/partial downloads aren't detected; re-download fixes.
    """
    if _try_cache is None:
        return False
    try:
        path = _try_cache(_repo_id(name), "model.bin")
    except Exception:  # pragma: no cover - defensive
        return False
    return isinstance(path, str) and os.path.exists(path)


def model_status() -> list[tuple[str, bool]]:
    """[(name, downloaded?)] for AVAILABLE_MODELS. No network."""
    return [(name, is_downloaded(name)) for name in AVAILABLE_MODELS]


def download(name: str) -> str:
    """Download `name` if missing (idempotent — no-op if cached); return local path.

    Blocking; the caller should run it off the UI thread. Raises RuntimeError if
    faster-whisper isn't importable.
    """
    if _fw is None:
        raise RuntimeError(
            "faster-whisper is not installed; cannot download models "
            "(pip install faster-whisper)"
        )
    if name not in AVAILABLE_MODELS:
        log.warning("download: %r not in AVAILABLE_MODELS; passing through anyway", name)
    return str(_fw.download_model(name))


if __name__ == "__main__":
    assert AVAILABLE_MODELS, "AVAILABLE_MODELS must be non-empty"
    status = model_status()
    assert isinstance(status, list) and len(status) == len(AVAILABLE_MODELS)
    for entry in status:
        assert isinstance(entry, tuple) and len(entry) == 2
        n, ok = entry
        assert isinstance(n, str) and isinstance(ok, bool)
    cd = cache_dir()
    assert isinstance(cd, str) and cd, "cache_dir() must return a path string"
    print("models self-test PASSED")
