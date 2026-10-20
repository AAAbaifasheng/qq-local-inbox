from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "release"
FILES = (
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


def read_version() -> str:
    value = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", value):
        raise SystemExit(f"VERSION is not semver: {value!r}")
    return value


def changelog_section(version: str) -> str:
    try:
        text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    except OSError:
        return ""
    match = re.search(
        rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|\Z)",
        text, re.MULTILINE | re.DOTALL)
    return match.group(1).strip()[:4000] if match else ""


def build_zip(version: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / f"QQLocalInbox-{version}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in FILES:
            path = ROOT / name
            if path.is_dir():
                for file_path in sorted(path.rglob("*")):
                    if not file_path.is_file():
                        continue
                    if "__pycache__" in file_path.parts or file_path.suffix == ".pyc":
                        continue
                    archive.write(file_path, file_path.relative_to(ROOT).as_posix())
            elif path.is_file():
                archive.write(path, path.relative_to(ROOT).as_posix())
            else:
                raise SystemExit(f"missing release file: {name}")
    return target


def main() -> None:
    version = read_version()
    tag = os.environ.get("GITHUB_REF_NAME", f"v{version}")
    if tag != f"v{version}":
        raise SystemExit(f"tag {tag!r} does not match VERSION {version!r}")
    archive = build_zip(version)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    manifest = {
        "version": version,
        "zip": archive.name,
        "sha256": digest,
        "size": archive.stat().st_size,
        "published_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "notes": changelog_section(version),
        "mandatory": False,
    }
    (OUT / "latest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"built {archive} ({manifest['size']} bytes)")
    print(f"sha256 {digest}")
    if not manifest["notes"]:
        print("warning: no CHANGELOG section for this version", file=sys.stderr)


if __name__ == "__main__":
    main()
