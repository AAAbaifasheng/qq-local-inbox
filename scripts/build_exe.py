from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "release"


def read_version() -> str:
    return (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def build_exe(version: str, name: str | None = None, console: bool = False) -> Path:
    name = name or f"QQLocalInbox-{version}-win64"
    build_dir = ROOT / "build" / "pyi"
    cmd = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--onefile", "--console" if console else "--windowed", "--name", name,
        "--add-data", f"{ROOT / 'assets'}{os.pathsep}assets",
        "--add-data", f"{ROOT / 'VERSION'}{os.pathsep}.",
        "--collect-all", "websocket", "--collect-all", "qrcode",
        "--hidden-import", "tkinter", "--hidden-import", "tkinter.ttk",
        "--distpath", str(OUT), "--workpath", str(build_dir),
        "--specpath", str(ROOT / "build"),
        str(ROOT / "launcher.py"),
    ]
    subprocess.run(cmd, check=True, cwd=ROOT)
    exe = OUT / f"{name}.exe"
    if not exe.is_file():
        raise SystemExit(f"missing exe: {exe}")
    return exe


def merge_manifest(exe: Path, version: str) -> None:
    manifest_path = OUT / "latest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["exe"] = exe.name
    manifest["exe_sha256"] = hashlib.sha256(exe.read_bytes()).hexdigest()
    manifest["exe_size"] = exe.stat().st_size
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                             encoding="utf-8")
    print(f"exe {exe.name} {manifest['exe_size']} bytes")
    print(f"exe sha256 {manifest['exe_sha256']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--console", action="store_true", help="build a console exe for debugging")
    parser.add_argument("--name", default="", help="override exe name")
    args = parser.parse_args()
    version = read_version()
    OUT.mkdir(parents=True, exist_ok=True)
    if not (OUT / "latest.json").is_file():
        raise SystemExit("run scripts/build_release.py first")
    exe = build_exe(version, name=args.name or None, console=args.console)
    if not args.console and not args.name:
        merge_manifest(exe, version)
    else:
        print(f"debug exe: {exe}")


if __name__ == "__main__":
    main()
