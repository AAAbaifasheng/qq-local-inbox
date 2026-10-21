from __future__ import annotations

import json
import socket
import subprocess
import time
from pathlib import Path

EXECUTABLE = "NapCatWinBootMain.exe"
CONFIG_GLOB = "versions/*/resources/app/napcat/config/webui.json"
CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008
DEFAULT_WEBUI_PORT = 6099


def candidate_roots() -> list[Path]:
    roots: list[Path] = []
    home = Path.home()
    bases = [home / "Desktop", home / "Downloads", home / "Documents"]
    for drive in ("C:/", "D:/", "E:/"):
        drive_path = Path(drive)
        if drive_path.exists():
            bases.append(drive_path)
    for base in bases:
        for pattern in ("NapCatQQ-OneKey/NapCat.*.Shell", "NapCat*.Shell", "NapCatQQ", "napcat*"):
            try:
                roots.extend(sorted(base.glob(pattern)))
            except OSError:
                continue
    unique: list[Path] = []
    for root in roots:
        if root not in unique:
            unique.append(root)
    return unique


def find_napcat_root(hint=None) -> Path | None:
    if hint:
        root = Path(hint).expanduser()
        return root if (root / EXECUTABLE).is_file() else None
    for root in candidate_roots():
        if (root / EXECUTABLE).is_file():
            return root
    return None


def _webui_config(root: Path) -> dict:
    for config in sorted(Path(root).glob(CONFIG_GLOB)):
        try:
            data = json.loads(config.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            return data
    return {}


def read_webui_token(root) -> str | None:
    token = str(_webui_config(root).get("token") or "").strip()
    return token or None


def read_webui_port(root, default: int = DEFAULT_WEBUI_PORT) -> int:
    try:
        port = int(_webui_config(root).get("port", default))
    except (TypeError, ValueError):
        return default
    return port if 1 <= port <= 65535 else default


def is_port_ready(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except OSError:
        return False


def wait_port(host: str, port: int, timeout: float = 20.0, interval: float = 0.5) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if is_port_ready(host, port, timeout=min(1.0, interval)):
            return True
        time.sleep(interval)
    return is_port_ready(host, port, timeout=1.0)


def start_hidden(command, cwd=None, hidden: bool = True):
    flags = (CREATE_NO_WINDOW | DETACHED_PROCESS) if hidden else 0
    return subprocess.Popen(
        [str(part) for part in command],
        cwd=str(cwd) if cwd else None,
        creationflags=flags,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def start_napcat(root, hidden: bool = True):
    root = Path(root)
    return start_hidden([root / EXECUTABLE], cwd=root, hidden=hidden)
