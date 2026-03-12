"""
io_safety.py — Shared atomic I/O primitives
Guinea Pig Trench LLC — DaShawn McLaughlin

Extracted from:
  - erdos_straus.py (atomic CSV checkpoint, csv_safe integer wrapping)
  - gpt-mastering-pipeline/io_handler.py (directory creation, format routing)

Used by any project that needs crash-safe file writes,
checkpoint naming, or large-integer CSV safety.
"""

import csv
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Atomic file writes — crash-safe via tempfile + os.replace()
# ---------------------------------------------------------------------------


def atomic_write_text(path: str, content: str, encoding: str = "utf-8") -> None:
    """Write text to a file atomically.

    Writes to a temp file in the same directory, then replaces the target.
    If the process crashes mid-write, the original file is untouched.
    """
    dir_name = os.path.dirname(os.path.abspath(path))
    os.makedirs(dir_name, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def atomic_write_json(path: str, data: Any, indent: int = 2) -> None:
    """Write JSON atomically."""
    atomic_write_text(path, json.dumps(data, indent=indent, ensure_ascii=False))


def atomic_write_csv(
    path: str,
    rows: list[dict],
    fieldnames: list[str],
    sort_key: str | None = None,
) -> None:
    """Write a list of dicts to CSV atomically.

    Optionally sorts rows by sort_key before writing.
    """
    if sort_key and rows:
        rows = sorted(rows, key=lambda r: r.get(sort_key, 0))

    dir_name = os.path.dirname(os.path.abspath(path))
    os.makedirs(dir_name, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# CSV safety — large integer firewall
# ---------------------------------------------------------------------------


def csv_safe(value: int) -> str:
    """Wrap integers >15 digits in ="" to prevent Excel/Sheets truncation.

    Excel silently rounds integers beyond 15 significant digits.
    This wraps them as ="12345678901234567" which forces text mode.
    """
    s = str(value)
    if len(s) > 15:
        return f'="{s}"'
    return s


def csv_unsafe(value: str) -> int:
    """Reverse csv_safe — strip ="" wrapper and return int."""
    s = str(value).strip()
    if s.startswith('="') and s.endswith('"'):
        s = s[2:-1]
    return int(s) if s else 0


# ---------------------------------------------------------------------------
# Checkpoint helpers
# ---------------------------------------------------------------------------


def load_checkpoint_csv(path: str, key_field: str = "n") -> dict[Any, dict]:
    """Load a CSV checkpoint file into a dict keyed by key_field."""
    results: dict[Any, dict] = {}
    if not os.path.exists(path):
        return results
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = row[key_field]
            try:
                key = int(key)
            except (ValueError, TypeError):
                pass
            results[key] = row
    return results


def save_checkpoint_csv(
    path: str,
    results: dict[Any, dict],
    fieldnames: list[str],
    sort_key: str | None = None,
) -> None:
    """Atomically save a checkpoint dict to CSV."""
    rows = list(results.values())
    if sort_key:
        try:
            rows = sorted(rows, key=lambda r: int(r.get(sort_key, 0)))
        except (ValueError, TypeError):
            rows = sorted(rows, key=lambda r: r.get(sort_key, ""))
    atomic_write_csv(path, rows, fieldnames, sort_key=None)


# ---------------------------------------------------------------------------
# Timestamped naming
# ---------------------------------------------------------------------------


def timestamp_name(prefix: str = "", suffix: str = "") -> str:
    """Generate a timestamped filename component.

    Example: timestamp_name("backup", ".tar.gz") → "backup_2026-03-10_143022.tar.gz"
    """
    ts = time.strftime("%Y-%m-%d_%H%M%S")
    parts = [p for p in [prefix, ts] if p]
    return "_".join(parts) + suffix


def ensure_dir(path: str) -> str:
    """Create directory (and parents) if it doesn't exist. Returns the path."""
    os.makedirs(path, exist_ok=True)
    return path
