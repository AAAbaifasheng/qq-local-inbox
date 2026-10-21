from __future__ import annotations

import json
import socket
import sys
import tempfile
import unittest
from pathlib import Path

from src.napcat_launcher import (
    EXECUTABLE,
    find_napcat_root,
    is_port_ready,
    read_webui_token,
    start_hidden,
    wait_port,
)


def make_napcat_dir(root: Path, token: str = "webui-token") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / EXECUTABLE).write_bytes(b"MZ")
    config = root / "versions" / "9.9.33-52230" / "resources" / "app" / "napcat" / "config"
    config.mkdir(parents=True, exist_ok=True)
    (config / "webui.json").write_text(
        json.dumps({"host": "127.0.0.1", "port": 6099, "token": token}), encoding="utf-8")
    return root


class LauncherTests(unittest.TestCase):
    def test_find_root_from_hint(self):
        with tempfile.TemporaryDirectory() as raw:
            root = make_napcat_dir(Path(raw) / "NapCat.Shell")
            self.assertEqual(find_napcat_root(hint=root), root)

    def test_find_root_returns_none_when_missing(self):
        with tempfile.TemporaryDirectory() as raw:
            self.assertIsNone(find_napcat_root(hint=Path(raw) / "nope"))

    def test_read_webui_token(self):
        with tempfile.TemporaryDirectory() as raw:
            root = make_napcat_dir(Path(raw) / "NapCat.Shell", token="secret-token")
            self.assertEqual(read_webui_token(root), "secret-token")

    def test_read_webui_token_missing(self):
        with tempfile.TemporaryDirectory() as raw:
            self.assertIsNone(read_webui_token(Path(raw)))

    def test_is_port_ready(self):
        server = socket.socket()
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]
        try:
            self.assertTrue(is_port_ready("127.0.0.1", port))
        finally:
            server.close()
        self.assertFalse(is_port_ready("127.0.0.1", 59999, timeout=0.2))

    def test_wait_port_returns_true_for_listener(self):
        server = socket.socket()
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]
        try:
            self.assertTrue(wait_port("127.0.0.1", port, timeout=1.0))
        finally:
            server.close()

    def test_wait_port_times_out(self):
        self.assertFalse(wait_port("127.0.0.1", 59998, timeout=0.3, interval=0.1))

    def test_start_hidden_runs_without_console(self):
        proc = start_hidden([sys.executable, "-c", "pass"])
        self.assertEqual(proc.wait(timeout=10), 0)


if __name__ == "__main__":
    unittest.main()
