from __future__ import annotations
import json
import os
from pathlib import Path
from .api_classifier import validate_api_endpoint
from .localnet import validate_local_url

APP_NAME = "QQLocalInbox"
LOCAL_API_DEFAULT = "http://127.0.0.1:11434/v1/chat/completions"
HISTORY_API_DEFAULT = "http://127.0.0.1:3000"

def _local_or_default(value, default: str) -> str:
    try:
        return validate_local_url(str(value), ("http", "https"), "API 地址")
    except ValueError:
        return default

def _endpoint_or_default(value, default: str) -> str:
    try:
        return validate_api_endpoint(str(value), allow_remote=True)
    except ValueError:
        return default

def _port_or_default(value, default: int = 8765) -> int:
    try:
        port = int(value)
    except (TypeError, ValueError):
        return default
    return port if 1 <= port <= 65535 else default

def data_dir() -> Path:
    override = os.environ.get("QQLI_DATA_DIR")
    if override:
        path = Path(override).expanduser().resolve()
    elif os.name == "nt":
        path = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / APP_NAME
    else:
        path = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path

def config_path() -> Path:
    return data_dir() / "settings.json"

def load_settings() -> dict:
    defaults = {
        "ws_url": "ws://127.0.0.1:3001",
        "include_group_messages": False,
        "analysis_mode": "rules",
        "api_endpoint": LOCAL_API_DEFAULT,
        "api_model": "",
        "history_api_url": HISTORY_API_DEFAULT,
        "auto_connect": True,
        "auto_sync_today": True,
        "allow_remote_api": False,
        "chaoxing_port": 8765,
        "auto_check_updates": True,
        "auto_download_updates": True,
        "auto_apply_updates": True,
    }
    path = config_path()
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(saved, dict):
            defaults.update({k: saved[k] for k in defaults if k in saved})
    except (OSError, json.JSONDecodeError):
        pass
    if defaults["analysis_mode"] not in {"rules", "api"}:
        defaults["analysis_mode"] = "rules"
    # Remote HTTPS endpoints are kept so the UI can require explicit consent at start.
    defaults["api_endpoint"] = _endpoint_or_default(defaults["api_endpoint"], LOCAL_API_DEFAULT)
    defaults["history_api_url"] = _local_or_default(defaults["history_api_url"], HISTORY_API_DEFAULT)
    for key in ("include_group_messages", "auto_connect", "auto_sync_today", "allow_remote_api",
                "auto_check_updates", "auto_download_updates", "auto_apply_updates"):
        defaults[key] = bool(defaults.get(key, False))
    defaults["chaoxing_port"] = _port_or_default(defaults.get("chaoxing_port", 8765))
    return defaults

def save_settings(settings: dict) -> None:
    # Never persist API keys or OneBot Access Tokens.
    clean = {
        "ws_url": str(settings.get("ws_url", "ws://127.0.0.1:3001")),
        "include_group_messages": bool(settings.get("include_group_messages", False)),
        "analysis_mode": settings.get("analysis_mode", "rules") if settings.get("analysis_mode") in {"rules", "api"} else "rules",
        "api_endpoint": _endpoint_or_default(settings.get("api_endpoint", LOCAL_API_DEFAULT), LOCAL_API_DEFAULT),
        "api_model": str(settings.get("api_model", "")),
        "history_api_url": _local_or_default(settings.get("history_api_url", HISTORY_API_DEFAULT), HISTORY_API_DEFAULT),
        "auto_connect": bool(settings.get("auto_connect", True)),
        "auto_sync_today": bool(settings.get("auto_sync_today", True)),
        "allow_remote_api": bool(settings.get("allow_remote_api", False)),
        "chaoxing_port": _port_or_default(settings.get("chaoxing_port", 8765)),
        "auto_check_updates": bool(settings.get("auto_check_updates", True)),
        "auto_download_updates": bool(settings.get("auto_download_updates", True)),
        "auto_apply_updates": bool(settings.get("auto_apply_updates", True)),
    }
    config_path().write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
