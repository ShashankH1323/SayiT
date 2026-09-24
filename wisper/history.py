"""Append-only transcript history: one JSON line per final transcript.

Lives next to config.json at the project root (history.jsonl) and is capped to
the last `max_items` (config.history_size) on every write. stdlib-only.

# ponytail: rewrite-whole-file per record; O(n) but n<=history_size (~50). Writes
# are serialized by a module lock and land via os.replace, so concurrent worker
# threads can't torn-write; a load() during a write still sees the old whole file.
"""

from __future__ import annotations

import json
import logging
import tempfile
import threading
from datetime import datetime
from pathlib import Path

log = logging.getLogger("wisper")

import os
import sys

_write_lock = threading.Lock()  # serializes read-modify-write across worker threads


def _atomic_write(p: Path, content: str) -> None:
    """Write via a temp file in the SAME dir, then os.replace onto the target.
    os.replace is atomic on the same volume (Windows + POSIX), so a reader
    never sees a half-written file. Caller holds _write_lock."""
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

def get_history_path() -> Path:
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        portable_hist = exe_dir / "history.jsonl"
        if portable_hist.exists():
            return portable_hist
        try:
            test = exe_dir / ".test_write"
            test.touch()
            test.unlink()
            return portable_hist
        except Exception:
            appdata = os.environ.get("APPDATA")
            if appdata:
                d = Path(appdata) / "SayIt"
                d.mkdir(parents=True, exist_ok=True)
                return d / "history.jsonl"
    return Path(__file__).resolve().parent.parent / "history.jsonl"

_DEFAULT_PATH = get_history_path()


def _read_records(path: Path) -> list[dict]:
    """Every valid record in file order (oldest first); [] if missing/unreadable.
    Blank and corrupt lines are skipped, not fatal."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return []
    out: list[dict] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue  # skip a corrupt line, keep the rest
        if isinstance(rec, dict) and rec.get("text"):
            out.append(rec)
    return out


def record(text: str, max_items: int, path: str | Path = _DEFAULT_PATH) -> None:
    """Append one transcript, then trim the file to the last `max_items`.
    Empty/whitespace-only text is ignored. Best-effort: never raises."""
    text = (text or "").strip()
    if not text:
        return
    p = Path(path)
    try:
        with _write_lock:
            recs = _read_records(p)
            recs.append({"ts": datetime.now().isoformat(timespec="seconds"), "text": text})
            if max_items and max_items > 0:
                recs = recs[-max_items:]
            _atomic_write(p, "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs))
    except OSError:
        log.exception("[wisper] history.record failed; transcript not saved")


def load(max_items: int | None = None, path: str | Path = _DEFAULT_PATH) -> list[dict]:
    """Past transcripts, newest first. Missing/corrupt file -> []."""
    recs = _read_records(Path(path))
    recs.reverse()  # newest first
    if max_items and max_items > 0:
        recs = recs[:max_items]
    return recs


def delete_record(ts: str, text: str, path: str | Path = _DEFAULT_PATH) -> bool:
    """Delete a specific record matching timestamp and text. Returns True if removed."""
    p = Path(path)
    try:
        with _write_lock:
            recs = _read_records(p)
            new_recs = [r for r in recs if not (r.get("ts") == ts and r.get("text") == text)]
            if len(new_recs) != len(recs):
                _atomic_write(p, "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in new_recs))
                return True
    except OSError:
        log.exception("[wisper] history.delete_record failed")
    return False


def clear_all(path: str | Path = _DEFAULT_PATH) -> None:
    """Clear all history records."""
    p = Path(path)
    try:
        with _write_lock:
            if p.exists():
                _atomic_write(p, "")
    except OSError:
        log.exception("[wisper] history.clear_all failed")


def demo() -> None:
    """Self-check: record past the cap, assert newest-first order, the cap, empty
    skipping, and corrupt/missing tolerance; clean up the temp file."""
    import tempfile

    tmp = Path(tempfile.gettempdir()) / "wisper_history_selfcheck.jsonl"
    tmp.unlink(missing_ok=True)
    try:
        cap = 3
        for t in ["first", "   ", "second", "third", "fourth"]:
            record(t, cap, tmp)            # "   " is whitespace -> skipped

        rows = load(path=tmp)
        assert [r["text"] for r in rows] == ["fourth", "third", "second"], rows  # newest first + cap
        assert len(rows) == cap, len(rows)
        assert all("ts" in r and r["text"] for r in rows), rows                  # record shape
        assert load(max_items=1, path=tmp)[0]["text"] == "fourth", "max_items"

        tmp.write_text('{"ts":"x","text":"ok"}\nGARBAGE\n\n', encoding="utf-8")  # corrupt tolerance
        assert [r["text"] for r in load(path=tmp)] == ["ok"], load(path=tmp)
        missing = Path(tempfile.gettempdir()) / "wisper_history_nope.jsonl"
        missing.unlink(missing_ok=True)
        assert load(path=missing) == [], "missing file -> []"
        print("history self-check: PASS")
    finally:
        tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    demo()
