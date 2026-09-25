"""Model manager for Say It: list / check / download models.

Pure logic for the UI "Models" panel — NO tkinter, NO UI. faster-whisper pulls
models from the HuggingFace Hub on first use; this module lists the curated set,
reports which are already in the local HF cache (no network), and downloads one
on demand (blocking — the caller threads it).

`faster_whisper` / `huggingface_hub` imports are guarded like audio.py guards
sounddevice, so `import sayit.models` never hard-crashes headless: functions
degrade gracefully (empty status, clear error on download) if they're missing.
"""
from __future__ import annotations

import logging
import os
import threading

log = logging.getLogger("sayit")

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
    "large-v3-turbo",
    "large-v3",
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
    return str(_fw.download_model(_repo_id(name)))


# --- Non-blocking download with observable progress (UI spinner + %) ---------

# Approx on-disk model.bin sizes (MB) for a best-effort progress %. Rough on
# purpose: the bar is capped at 99% until the download thread reports done.
_APPROX_MB: dict[str, int] = {
    "tiny": 75,
    "base": 145,
    "small": 484,
    "medium": 1530,
    "large-v3-turbo": 1600,
    "large-v3": 3090,
}

_dl_lock = threading.Lock()
_dl: dict = {"active": False, "name": None, "done": False, "error": None, "pct": None}
_dl_thread: "threading.Thread | None" = None


def _model_dir(name: str) -> str:
    """HF Hub cache dir for `name`'s repo (``models--org--repo``)."""
    return os.path.join(cache_dir(), "models--" + _repo_id(name).replace("/", "--"))


def _dir_size(path: str) -> int:
    """Total bytes of files under `path` (0 if absent). Skips files that vanish
    mid-walk (HF renames blobs as it commits them)."""
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:  # pragma: no cover - file moved/removed during walk
                pass
    return total


def _measure_pct(name: str) -> "float | None":
    """Live best-effort % from bytes on disk vs the approx total. None if the
    model's cache dir isn't locatable yet (UI shows an indeterminate spinner)."""
    approx = _APPROX_MB.get(name)
    d = _model_dir(name)
    if not approx or not os.path.isdir(d):
        return None
    # Count only blobs/ (the real download); snapshots/ are symlinks, or copies
    # on Windows without symlink privilege -> would otherwise double-count.
    blobs = os.path.join(d, "blobs")
    downloaded = _dir_size(blobs if os.path.isdir(blobs) else d)
    return float(min(99.0, downloaded / (approx * 1024 * 1024) * 100.0))


def _run_download(name: str) -> None:
    try:
        download(name)  # blocking; reuses the existing download path
        with _dl_lock:
            _dl.update(active=False, done=True, error=None, pct=100.0)
    except Exception as e:  # any failure -> report it, don't kill the daemon
        log.warning("download of %r failed: %s", name, e)
        with _dl_lock:
            _dl.update(active=False, done=False, error=str(e), pct=None)


def start_download(name: str) -> None:
    """Kick off a background (daemon-thread) download of `name`. Idempotent: a
    no-op while a download is already running. Progress via download_progress()."""
    global _dl_thread
    with _dl_lock:
        if _dl["active"]:
            return  # already downloading -> ignore
        _dl.update(active=True, name=name, done=False, error=None, pct=_measure_pct(name))
        _dl_thread = threading.Thread(target=_run_download, args=(name,), daemon=True)
        _dl_thread.start()


def download_progress() -> dict:
    """Snapshot of the current/last download:
    ``{"active", "name", "done", "error", "pct"}``. While active, `pct` is a
    live byte-size estimate (or None if the cache dir isn't locatable yet)."""
    with _dl_lock:
        active, name = _dl["active"], _dl["name"]
    if active and name is not None:
        pct = _measure_pct(name)  # I/O outside the lock
        with _dl_lock:
            if _dl["active"]:  # still running -> publish the live estimate
                _dl["pct"] = pct
    with _dl_lock:
        return {k: _dl[k] for k in ("active", "name", "done", "error", "pct")}


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
    prog = download_progress()
    assert set(prog) == {"active", "name", "done", "error", "pct"}, prog
    assert prog["active"] is False and prog["done"] is False and prog["error"] is None
    print("models self-test PASSED")
