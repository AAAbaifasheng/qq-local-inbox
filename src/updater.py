from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

REPO = "AAAbaifasheng/qq-local-inbox"
MANIFEST_URL = (
    f"https://github.com/{REPO}/releases/latest/download/latest.json"
)
ALLOWED_HOSTS = {
    "github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
}
MAX_MANIFEST_BYTES = 64 * 1024
MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
MAX_EXTRACTED_BYTES = 200 * 1024 * 1024
MAX_ARCHIVE_FILES = 5000
UPDATE_PATHS = (
    "src",
    "assets",
    "docs",
    "README.md",
    "LICENSE",
    "CHANGELOG.md",
    "VERSION",
    "requirements.txt",
    "install.ps1",
    "run.bat",
    "launcher.py",
)
_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class UpdateError(Exception):
    pass


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    zip_url: str
    sha256: str
    size: int
    notes: str = ""
    published_at: str = ""
    mandatory: bool = False
    exe_url: str = ""
    exe_sha256: str = ""
    exe_size: int = 0


@dataclass(frozen=True)
class StagedUpdate:
    info: UpdateInfo
    path: Path


@dataclass(frozen=True)
class ApplyResult:
    applied: bool
    version: str = ""
    backup: Path | None = None
    reason: str = ""


def parse_version(value: str) -> tuple[int, int, int]:
    match = _VERSION_RE.fullmatch(str(value or "").strip())
    if not match:
        raise ValueError(f"invalid version: {value!r}")
    return tuple(int(part) for part in match.groups())


def is_newer(candidate: str, current: str) -> bool:
    return parse_version(candidate) > parse_version(current)


def _validate_url(url: str, allow_http: bool = False) -> str:
    parsed = urlparse(str(url or "").strip())
    if parsed.username or parsed.password:
        raise UpdateError("更新地址不能包含账号密码")
    host = (parsed.hostname or "").lower()
    if parsed.scheme == "https":
        if host not in ALLOWED_HOSTS:
            raise UpdateError("更新地址不是受信任的 GitHub 域名")
        return parsed.geturl()
    if allow_http and parsed.scheme == "http" and host in {"127.0.0.1", "localhost", "::1"}:
        return parsed.geturl()
    raise UpdateError("更新地址必须使用 HTTPS")


def fetch_manifest(url: str = MANIFEST_URL, timeout: float = 8.0) -> dict:
    _validate_url(url)
    request = Request(url, headers={"User-Agent": "QQLocalInbox-Updater/1"})
    try:
        with urlopen(request, timeout=timeout) as response:
            final_url = response.geturl()
            _validate_url(final_url)
            raw = response.read(MAX_MANIFEST_BYTES + 1)
    except UpdateError:
        raise
    except Exception as exc:
        raise UpdateError(f"无法读取更新清单：{exc}") from exc
    if len(raw) > MAX_MANIFEST_BYTES:
        raise UpdateError("更新清单过大")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UpdateError("更新清单格式不正确") from exc
    if not isinstance(data, dict):
        raise UpdateError("更新清单格式不正确")
    return data


def select_update(manifest: dict, current_version: str, base_url: str = MANIFEST_URL) -> UpdateInfo | None:
    if not isinstance(manifest, dict):
        raise UpdateError("更新清单格式不正确")
    try:
        version = str(manifest.get("version", "")).strip()
        if not is_newer(version, current_version):
            return None
        zip_value = str(manifest.get("zip", "")).strip()
        if not zip_value:
            raise UpdateError("更新包地址缺失")
        zip_url = _validate_url(urljoin(base_url, zip_value))
        sha256 = str(manifest.get("sha256", "")).strip().lower()
        if not _SHA256_RE.fullmatch(sha256):
            raise UpdateError("更新包哈希格式不正确")
        size = int(manifest.get("size", 0))
    except UpdateError:
        raise
    except (TypeError, ValueError) as exc:
        raise UpdateError("更新清单字段不正确") from exc
    if not 0 < size <= MAX_ARCHIVE_BYTES:
        raise UpdateError("更新包大小超出允许范围")
    notes = str(manifest.get("notes", ""))[:2000]
    published_at = str(manifest.get("published_at", ""))[:80]
    exe_url = ""
    exe_sha256 = ""
    exe_size = 0
    raw_exe = str(manifest.get("exe", "") or "").strip()
    if raw_exe:
        exe_url = _validate_url(urljoin(base_url, raw_exe))
        exe_sha256 = str(manifest.get("exe_sha256", "")).strip().lower()
        if not _SHA256_RE.fullmatch(exe_sha256):
            raise UpdateError("可执行更新包哈希格式不正确")
        exe_size = int(manifest.get("exe_size", 0))
        if not 0 < exe_size <= MAX_ARCHIVE_BYTES:
            raise UpdateError("可执行更新包大小超出允许范围")
    return UpdateInfo(
        version=version,
        zip_url=zip_url,
        sha256=sha256,
        size=size,
        notes=notes,
        published_at=published_at,
        mandatory=bool(manifest.get("mandatory", False)),
        exe_url=exe_url,
        exe_sha256=exe_sha256,
        exe_size=exe_size,
    )


def check_for_update(current_version: str, url: str = MANIFEST_URL, timeout: float = 8.0) -> UpdateInfo | None:
    return select_update(fetch_manifest(url, timeout), current_version, url)


def safe_extract(archive_path: Path, dest_dir: Path) -> list[str]:
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    root = dest_dir.resolve()
    extracted: list[str] = []
    total = 0
    try:
        with zipfile.ZipFile(archive_path) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_ARCHIVE_FILES:
                raise UpdateError("更新包文件数量过多")
            for info in infos:
                name = info.filename
                if info.is_dir():
                    continue
                if not name or "\\" in name:
                    raise UpdateError("更新包包含非法路径")
                pure = PurePosixPath(name)
                if pure.is_absolute() or ".." in pure.parts or pure.parts[0] not in UPDATE_PATHS:
                    raise UpdateError(f"更新包包含不允许的路径：{name}")
                mode = (info.external_attr >> 16) & 0o170000
                if mode == 0o120000:
                    raise UpdateError("更新包包含符号链接")
                if "__pycache__" in pure.parts or pure.suffix == ".pyc":
                    continue
                total += info.file_size
                if total > MAX_EXTRACTED_BYTES:
                    raise UpdateError("更新包解压后过大")
                target = (dest_dir / pure).resolve()
                if root != target and root not in target.parents:
                    raise UpdateError("更新包路径越界")
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, target.open("wb") as handle:
                    shutil.copyfileobj(source, handle)
                extracted.append(str(pure))
    except zipfile.BadZipFile as exc:
        raise UpdateError("更新包不是有效的 zip 文件") from exc
    return extracted


def stage_update(info: UpdateInfo, staging_root: Path, timeout: float = 30.0) -> Path:
    staging_root = Path(staging_root)
    version_dir = staging_root / "versions" / f"v{info.version}"
    if version_dir.exists():
        shutil.rmtree(version_dir)
    archive = download_update(info, staging_root / "downloads", timeout=timeout)
    try:
        safe_extract(archive, version_dir)
    finally:
        archive.unlink(missing_ok=True)
    (version_dir / "manifest.json").write_text(
        json.dumps({
            "version": info.version,
            "zip_url": info.zip_url,
            "sha256": info.sha256,
            "size": info.size,
            "notes": info.notes,
            "published_at": info.published_at,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return version_dir


def find_pending(staging_root: Path, current_version: str) -> StagedUpdate | None:
    versions = Path(staging_root) / "versions"
    if not versions.is_dir():
        return None
    best: StagedUpdate | None = None
    for version_dir in versions.iterdir():
        if not version_dir.is_dir():
            continue
        manifest_path = version_dir / "manifest.json"
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            version = str(data.get("version", "")).strip()
            if not is_newer(version, current_version):
                continue
            info = UpdateInfo(
                version=version,
                zip_url=str(data.get("zip_url", "")),
                sha256=str(data.get("sha256", "")),
                size=int(data.get("size", 0)),
                notes=str(data.get("notes", "")),
                published_at=str(data.get("published_at", "")),
            )
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue
        if best is None or parse_version(info.version) > parse_version(best.info.version):
            best = StagedUpdate(info=info, path=version_dir)
    return best


def _backup(app_root: Path, backup_dir: Path) -> None:
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    backup_dir.mkdir(parents=True)
    for name in UPDATE_PATHS:
        source = app_root / name
        if not source.exists():
            continue
        target = backup_dir / name
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)


def _copy_tree(source_root: Path, target_root: Path) -> None:
    for name in UPDATE_PATHS:
        source = source_root / name
        if not source.exists():
            continue
        target = target_root / name
        if source.is_dir():
            shutil.copytree(source, target, dirs_exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def _restore(app_root: Path, backup_dir: Path) -> None:
    for name in UPDATE_PATHS:
        source = backup_dir / name
        target = app_root / name
        if not source.exists():
            continue
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)


def _log(staging_root: Path, message: str) -> None:
    try:
        staging_root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with (staging_root / "update.log").open("a", encoding="utf-8") as handle:
            handle.write(f"{stamp} {message}\n")
    except OSError:
        pass


def apply_pending(
    app_root: Path,
    staging_root: Path,
    current_version: str,
    force: bool = False,
) -> ApplyResult:
    app_root = Path(app_root)
    staging_root = Path(staging_root)
    staged = find_pending(staging_root, current_version)
    if staged is None:
        return ApplyResult(False, reason="no-pending")
    if (app_root / ".git").exists() and not force and os.environ.get("QQLI_FORCE_UPDATE") != "1":
        _log(staging_root, f"skip {staged.info.version}: git checkout")
        return ApplyResult(False, staged.info.version, reason="git-checkout")
    backup_dir = staging_root / "backups" / f"v{current_version}"
    try:
        _backup(app_root, backup_dir)
        _copy_tree(staged.path, app_root)
    except Exception as exc:
        try:
            _restore(app_root, backup_dir)
        except Exception as restore_exc:
            _log(staging_root, f"restore failed: {restore_exc}")
        _log(staging_root, f"apply {staged.info.version} failed: {exc}")
        raise UpdateError(f"应用更新失败，已尝试回滚：{exc}") from exc
    shutil.rmtree(staged.path, ignore_errors=True)
    _log(staging_root, f"applied {staged.info.version} from {current_version}")
    return ApplyResult(True, staged.info.version, backup_dir)


def _download_to(url: str, sha256: str, size: int, target: Path, timeout: float = 60.0) -> Path:
    _validate_url(url)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    digest = hashlib.sha256()
    received = 0
    request = Request(url, headers={"User-Agent": "QQLocalInbox-Updater/1"})
    try:
        with urlopen(request, timeout=timeout) as response:
            _validate_url(response.geturl())
            with target.open("wb") as handle:
                while True:
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    received += len(chunk)
                    if received > MAX_ARCHIVE_BYTES:
                        raise UpdateError("更新包超过大小上限")
                    handle.write(chunk)
                    digest.update(chunk)
    except UpdateError:
        target.unlink(missing_ok=True)
        raise
    except Exception as exc:
        target.unlink(missing_ok=True)
        raise UpdateError(f"下载更新失败：{exc}") from exc
    if received != size:
        target.unlink(missing_ok=True)
        raise UpdateError("更新包大小与清单不一致")
    if digest.hexdigest() != sha256:
        target.unlink(missing_ok=True)
        raise UpdateError("更新包 SHA256 校验失败")
    return target


def download_update(info: UpdateInfo, dest_dir: Path, timeout: float = 30.0) -> Path:
    return _download_to(info.zip_url, info.sha256, info.size,
                        Path(dest_dir) / (PurePosixPath(urlparse(info.zip_url).path).name
                                          or f"QQLocalInbox-{info.version}.zip"),
                        timeout=timeout)


def stage_exe_update(info: UpdateInfo, staging_root: Path, timeout: float = 60.0) -> Path:
    if not info.exe_url:
        raise UpdateError("该版本没有提供可执行更新包")
    staging_root = Path(staging_root)
    version_dir = staging_root / "exe" / f"v{info.version}"
    if version_dir.exists():
        shutil.rmtree(version_dir)
    target = _download_to(info.exe_url, info.exe_sha256, info.exe_size,
                          version_dir / "QQLocalInbox.exe", timeout=timeout)
    (version_dir / "manifest.json").write_text(
        json.dumps({"version": info.version, "exe_sha256": info.exe_sha256,
                    "exe_size": info.exe_size}, indent=2), encoding="utf-8")
    return target


def find_pending_exe(staging_root: Path, current_version: str) -> StagedUpdate | None:
    exe_root = Path(staging_root) / "exe"
    if not exe_root.is_dir():
        return None
    best: StagedUpdate | None = None
    for version_dir in exe_root.iterdir():
        if not version_dir.is_dir():
            continue
        exe = version_dir / "QQLocalInbox.exe"
        manifest_path = version_dir / "manifest.json"
        if not exe.is_file() or not manifest_path.is_file():
            continue
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            version = str(data.get("version", "")).strip()
            if not is_newer(version, current_version):
                continue
            info = UpdateInfo(version=version, zip_url="", sha256="", size=0,
                              exe_url=str(exe), exe_sha256=str(data.get("exe_sha256", "")),
                              exe_size=int(data.get("exe_size", 0)))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue
        if best is None or parse_version(info.version) > parse_version(best.info.version):
            best = StagedUpdate(info=info, path=exe)
    return best


def apply_exe_pending(current_exe: Path, staging_root: Path, current_version: str) -> ApplyResult:
    current_exe = Path(current_exe)
    staged = find_pending_exe(staging_root, current_version)
    if staged is None:
        return ApplyResult(False, reason="no-pending")
    backup = Path(staging_root) / "backups" / f"v{current_version}.exe"
    try:
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(current_exe, backup)
        old = current_exe.with_suffix(current_exe.suffix + ".old")
        old.unlink(missing_ok=True)
        current_exe.rename(old)
        shutil.copy2(staged.path, current_exe)
        old.unlink(missing_ok=True)
    except Exception as exc:
        try:
            if backup.is_file():
                old = current_exe.with_suffix(current_exe.suffix + ".old")
                old.unlink(missing_ok=True)
                if not current_exe.exists():
                    shutil.copy2(backup, current_exe)
        except Exception as restore_exc:
            _log(Path(staging_root), f"exe restore failed: {restore_exc}")
        _log(Path(staging_root), f"exe apply {staged.info.version} failed: {exc}")
        raise UpdateError(f"应用可执行更新失败，已尝试回滚：{exc}") from exc
    shutil.rmtree(staged.path.parent, ignore_errors=True)
    _log(Path(staging_root), f"exe applied {staged.info.version} from {current_version}")
    return ApplyResult(True, staged.info.version, backup)
