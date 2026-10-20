from __future__ import annotations
import base64
import ctypes
import json
import os
from ctypes import wintypes
from .config import data_dir

SECRET_API_KEY = "api_key"
SECRET_WS_TOKEN = "ws_token"
SECRET_HTTP_TOKEN = "http_token"
SECRET_CHAOXING_TOKEN = "chaoxing_token"
_ENTROPY = b"QQLocalInbox.DPAPI.v1"

class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

def _secret_path():
    return data_dir() / "secrets.dat"

def _blob(data: bytes):
    buffer = ctypes.create_string_buffer(data)
    blob = _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    return blob, buffer

def _protect(data: bytes) -> bytes:
    if os.name != "nt":
        raise OSError("DPAPI 仅在 Windows 上可用")
    in_blob, in_buf = _blob(data)
    entropy_blob, entropy_buf = _blob(_ENTROPY)
    out_blob = _DataBlob()
    if not ctypes.windll.crypt32.CryptProtectData(
            ctypes.byref(in_blob), "QQLocalInbox", ctypes.byref(entropy_blob),
            None, None, 0, ctypes.byref(out_blob)):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)

def _unprotect(data: bytes) -> bytes:
    if os.name != "nt":
        raise OSError("DPAPI 仅在 Windows 上可用")
    in_blob, in_buf = _blob(data)
    entropy_blob, entropy_buf = _blob(_ENTROPY)
    out_blob = _DataBlob()
    if not ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(in_blob), None, ctypes.byref(entropy_blob),
            None, None, 0, ctypes.byref(out_blob)):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)

def _load_all() -> dict:
    path = _secret_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}

def _write_all(data: dict) -> None:
    path = _secret_path()
    if not data:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)

def save_secret(name: str, value: str) -> bool:
    if os.name != "nt":
        return False
    value = value or ""
    if not value:
        clear_secret(name)
        return True
    try:
        encrypted = _protect(value.encode("utf-8"))
    except OSError:
        return False
    data = _load_all()
    data[name] = base64.b64encode(encrypted).decode("ascii")
    _write_all(data)
    return True

def load_secret(name: str) -> str:
    if os.name != "nt":
        return ""
    data = _load_all()
    encoded = data.get(name)
    if not isinstance(encoded, str):
        return ""
    try:
        return _unprotect(base64.b64decode(encoded)).decode("utf-8")
    except (OSError, ValueError, UnicodeDecodeError):
        return ""

def clear_secret(name: str) -> None:
    data = _load_all()
    if name in data:
        data.pop(name, None)
        _write_all(data)

def clear_all_secrets() -> None:
    try:
        _secret_path().unlink()
    except FileNotFoundError:
        pass
