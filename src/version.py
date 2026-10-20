from __future__ import annotations

from pathlib import Path


def _read_version() -> str:
    path = Path(__file__).resolve().parent.parent / "VERSION"
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError:
        return "0.0.0"
    return value or "0.0.0"


__version__ = _read_version()
