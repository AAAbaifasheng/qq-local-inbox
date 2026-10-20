from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .updater import UpdateError, apply_pending
from .version import __version__


def data_root() -> Path:
    override = os.environ.get("QQLI_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        return Path(base) / "QQLocalInbox"
    return Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))) / "QQLocalInbox"


def _auto_apply_enabled(root: Path) -> bool:
    try:
        settings = json.loads((root / "settings.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True
    return bool(settings.get("auto_apply_updates", True))


def apply_pending_at_startup() -> bool:
    if getattr(sys, "frozen", False):
        return False
    root = data_root()
    if not _auto_apply_enabled(root):
        return False
    app_root = Path(__file__).resolve().parent.parent
    try:
        result = apply_pending(app_root, root / "updates", __version__)
    except UpdateError:
        return False
    if not result.applied:
        return False
    try:
        os.execv(sys.executable, [sys.executable, "-m", "src.main", *sys.argv[1:]])
    except OSError:
        return False
    return True
