from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from src import updater
from src.updater import (
    MAX_ARCHIVE_BYTES,
    UpdateError,
    UpdateInfo,
    apply_exe_pending,
    apply_pending,
    download_update,
    is_newer,
    parse_version,
    safe_extract,
    select_update,
)

BASE_URL = "https://github.com/AAAbaifasheng/qq-local-inbox/releases/latest/download/latest.json"


def manifest(**overrides):
    data = {
        "version": "0.4.0",
        "zip": "QQLocalInbox-0.4.0.zip",
        "sha256": "a" * 64,
        "size": 1000,
        "notes": "test release",
    }
    data.update(overrides)
    return data


class FakeResponse:
    def __init__(self, data: bytes, url: str = "https://github.com/AAAbaifasheng/qq-local-inbox/releases/download/v0.4.0/QQLocalInbox-0.4.0.zip"):
        self._stream = io.BytesIO(data)
        self._url = url
        self.headers = {"Content-Length": str(len(data))}

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)

    def geturl(self) -> str:
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class VersionTests(unittest.TestCase):
    def test_parse_version_accepts_v_prefix(self):
        self.assertEqual(parse_version("v0.4.1"), (0, 4, 1))
        self.assertEqual(parse_version("1.2.3"), (1, 2, 3))

    def test_parse_version_rejects_incomplete_or_garbage(self):
        for value in ("1.2", "1", "v1.2.3.4", "abc", ""):
            with self.assertRaises(ValueError):
                parse_version(value)

    def test_is_newer_compares_numeric_parts(self):
        self.assertTrue(is_newer("0.4.0", "0.3.9"))
        self.assertTrue(is_newer("1.0.0", "0.9.9"))
        self.assertFalse(is_newer("0.4.0", "0.4.0"))
        self.assertFalse(is_newer("0.3.9", "0.4.0"))


class ManifestTests(unittest.TestCase):
    def test_newer_manifest_returns_update_info(self):
        info = select_update(manifest(), "0.3.0", BASE_URL)
        self.assertIsInstance(info, UpdateInfo)
        self.assertEqual(info.version, "0.4.0")
        self.assertEqual(
            info.zip_url,
            "https://github.com/AAAbaifasheng/qq-local-inbox/releases/latest/download/QQLocalInbox-0.4.0.zip",
        )

    def test_same_or_older_manifest_is_ignored(self):
        self.assertIsNone(select_update(manifest(version="0.3.0"), "0.3.0", BASE_URL))
        self.assertIsNone(select_update(manifest(version="0.2.9"), "0.3.0", BASE_URL))

    def test_manifest_rejects_non_https_zip(self):
        with self.assertRaises(UpdateError):
            select_update(manifest(zip="http://example.com/x.zip"), "0.3.0", BASE_URL)

    def test_manifest_rejects_untrusted_zip_host(self):
        with self.assertRaises(UpdateError):
            select_update(manifest(zip="https://example.com/x.zip"), "0.3.0", BASE_URL)

    def test_manifest_rejects_bad_hash(self):
        with self.assertRaises(UpdateError):
            select_update(manifest(sha256="xyz"), "0.3.0", BASE_URL)

    def test_manifest_rejects_oversized_archive(self):
        with self.assertRaises(UpdateError):
            select_update(manifest(size=MAX_ARCHIVE_BYTES + 1), "0.3.0", BASE_URL)


class ExtractTests(unittest.TestCase):
    def _zip(self, path: Path, entries: dict[str, bytes], symlinks: set[str] | None = None):
        symlinks = symlinks or set()
        with zipfile.ZipFile(path, "w") as archive:
            for name, data in entries.items():
                info = zipfile.ZipInfo(name)
                if name in symlinks:
                    info.external_attr = (0o120777 << 16)
                archive.writestr(info, data)

    def test_extract_allows_runtime_paths(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            archive = root / "update.zip"
            self._zip(archive, {"src/app.py": b"new", "VERSION": b"0.4.0\n"})
            target = root / "out"
            files = safe_extract(archive, target)
            self.assertIn("src/app.py", files)
            self.assertEqual((target / "src" / "app.py").read_bytes(), b"new")

    def test_extract_blocks_path_traversal(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            archive = root / "update.zip"
            self._zip(archive, {"../evil.txt": b"bad"})
            with self.assertRaises(UpdateError):
                safe_extract(archive, root / "out")

    def test_extract_blocks_absolute_and_drive_paths(self):
        for name in ("/absolute.txt", "C:/windows/evil.txt"):
            with tempfile.TemporaryDirectory() as raw:
                root = Path(raw)
                archive = root / "update.zip"
                self._zip(archive, {name: b"bad"})
                with self.assertRaises(UpdateError):
                    safe_extract(archive, root / "out")

    def test_extract_blocks_symlink(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            archive = root / "update.zip"
            self._zip(archive, {"src/link": b"target"}, symlinks={"src/link"})
            with self.assertRaises(UpdateError):
                safe_extract(archive, root / "out")

    def test_extract_blocks_unexpected_top_level(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            archive = root / "update.zip"
            self._zip(archive, {"server.exe": b"bad"})
            with self.assertRaises(UpdateError):
                safe_extract(archive, root / "out")


class DownloadTests(unittest.TestCase):
    def test_download_verifies_sha256(self):
        payload = b"fake zip bytes"
        info = UpdateInfo(
            version="0.4.0",
            zip_url="https://github.com/AAAbaifasheng/qq-local-inbox/releases/download/v0.4.0/x.zip",
            sha256=hashlib.sha256(payload).hexdigest(),
            size=len(payload),
        )
        with tempfile.TemporaryDirectory() as raw:
            with patch.object(updater, "urlopen", return_value=FakeResponse(payload)):
                path = download_update(info, Path(raw))
            self.assertEqual(path.read_bytes(), payload)

    def test_download_rejects_hash_mismatch_and_removes_partial_file(self):
        payload = b"tampered"
        info = UpdateInfo(
            version="0.4.0",
            zip_url="https://github.com/AAAbaifasheng/qq-local-inbox/releases/download/v0.4.0/x.zip",
            sha256="b" * 64,
            size=len(payload),
        )
        with tempfile.TemporaryDirectory() as raw:
            with patch.object(updater, "urlopen", return_value=FakeResponse(payload)):
                with self.assertRaises(UpdateError):
                    download_update(info, Path(raw))
            self.assertEqual(list(Path(raw).glob("*.zip")), [])


class ApplyTests(unittest.TestCase):
    def _make_app(self, root: Path, with_git: bool = False):
        root.mkdir(parents=True, exist_ok=True)
        (root / "src").mkdir()
        (root / "src" / "app.py").write_text("old", encoding="utf-8")
        (root / "VERSION").write_text("0.3.0\n", encoding="utf-8")
        if with_git:
            (root / ".git").mkdir()

    def _make_staged(self, staging: Path, version: str = "0.4.0"):
        staged = staging / "versions" / f"v{version}"
        (staged / "src").mkdir(parents=True)
        (staged / "src" / "app.py").write_text("new", encoding="utf-8")
        (staged / "VERSION").write_text(f"{version}\n", encoding="utf-8")
        (staged / "manifest.json").write_text(
            json.dumps({"version": version, "zip_url": "https://github.com/x", "sha256": "a" * 64,
                        "size": 10}), encoding="utf-8")
        return staged

    def test_apply_skips_git_checkout_without_force(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self._make_app(root, with_git=True)
            staging = root / "updates"
            self._make_staged(staging)
            old = os.environ.pop("QQLI_FORCE_UPDATE", None)
            try:
                result = apply_pending(root, staging, "0.3.0", force=False)
            finally:
                if old is not None:
                    os.environ["QQLI_FORCE_UPDATE"] = old
            self.assertFalse(result.applied)
            self.assertEqual((root / "src" / "app.py").read_text(encoding="utf-8"), "old")

    def test_apply_replaces_files_backs_up_and_removes_staging(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self._make_app(root)
            staging = root / "updates"
            staged = self._make_staged(staging)
            result = apply_pending(root, staging, "0.3.0", force=True)
            self.assertTrue(result.applied)
            self.assertEqual(result.version, "0.4.0")
            self.assertEqual((root / "src" / "app.py").read_text(encoding="utf-8"), "new")
            self.assertEqual((root / "VERSION").read_text(encoding="utf-8").strip(), "0.4.0")
            backup = staging / "backups" / "v0.3.0" / "src" / "app.py"
            self.assertEqual(backup.read_text(encoding="utf-8"), "old")
            self.assertFalse(staged.exists())

    def test_apply_returns_not_applied_when_no_pending(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self._make_app(root)
            result = apply_pending(root, root / "updates", "0.3.0", force=True)
            self.assertFalse(result.applied)


class ExeApplyTests(unittest.TestCase):
    def _stage(self, staging: Path, version: str = "0.4.0"):
        ver = staging / "exe" / f"v{version}"
        ver.mkdir(parents=True)
        (ver / "QQLocalInbox.exe").write_bytes(b"new", )
        (ver / "manifest.json").write_text(
            json.dumps({"version": version, "exe_sha256": "a" * 64, "exe_size": 3}),
            encoding="utf-8")
        return ver

    def test_apply_exe_replaces_and_backs_up(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            exe = root / "QQLocalInbox.exe"
            exe.write_bytes(b"old")
            staging = root / "updates"
            ver = self._stage(staging)
            result = apply_exe_pending(exe, staging, "0.3.0")
            self.assertTrue(result.applied)
            self.assertEqual(exe.read_bytes(), b"new")
            self.assertEqual((staging / "backups" / "v0.3.0.exe").read_bytes(), b"old")
            self.assertFalse((ver / "QQLocalInbox.exe").exists())

    def test_apply_exe_no_pending(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            exe = root / "QQLocalInbox.exe"
            exe.write_bytes(b"old")
            result = apply_exe_pending(exe, root / "updates", "0.3.0")
            self.assertFalse(result.applied)
            self.assertEqual(exe.read_bytes(), b"old")


if __name__ == "__main__":
    unittest.main()
