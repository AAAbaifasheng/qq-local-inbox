from __future__ import annotations
from urllib.parse import urlparse

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}

def is_local_hostname(host: str | None) -> bool:
    return (host or "").lower() in LOCAL_HOSTS

def is_remote_url(url: str) -> bool:
    return not is_local_hostname(urlparse(url or "").hostname)

def validate_local_url(url: str, schemes: tuple[str, ...], label: str) -> str:
    value = (url or "").strip()
    parsed = urlparse(value)
    if parsed.scheme not in schemes:
        allowed = " / ".join(f"{scheme}://" for scheme in schemes)
        raise ValueError(f"{label}必须以 {allowed} 开头。")
    if (parsed.hostname or "").lower() not in LOCAL_HOSTS:
        raise ValueError(f"{label}只允许连接本机地址（127.0.0.1 / localhost / ::1）。")
    if parsed.username or parsed.password:
        raise ValueError(f"{label}中不要嵌入用户名或密码。")
    return value
