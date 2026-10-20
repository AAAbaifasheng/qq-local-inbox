from __future__ import annotations

import json
import time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlunparse
from urllib.request import Request, urlopen

from .api_classifier import validate_api_endpoint

MAX_PROBE_BYTES = 1_000_000


@dataclass(frozen=True)
class ProbeResult:
    ok: bool
    models: list[str]
    latency_ms: int
    message: str
    url: str = ""


def probe_urls(endpoint: str) -> list[str]:
    parsed = urlparse(endpoint)
    origin = urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))
    host = (parsed.hostname or "").lower()
    port = parsed.port
    urls: list[str] = []
    if host in {"127.0.0.1", "localhost", "::1"} and port == 11434:
        urls.extend([origin + "/api/tags", origin + "/v1/models"])
    elif host == "api.deepseek.com":
        urls.extend([origin + "/models", origin + "/v1/models"])
    else:
        path = parsed.path.rstrip("/")
        if path.endswith("/chat/completions"):
            base = path[:-len("/chat/completions")]
            if base:
                urls.append(origin + base + "/models")
        if not urls:
            urls.extend([origin + "/v1/models", origin + "/models"])
    result: list[str] = []
    for url in urls:
        if url not in result:
            result.append(url)
    return result


def parse_models(payload) -> list[str]:
    if isinstance(payload, dict):
        items = payload.get("data")
        if items is None:
            items = payload.get("models")
    elif isinstance(payload, list):
        items = payload
    else:
        items = None
    models: set[str] = set()
    for item in items if isinstance(items, list) else []:
        if isinstance(item, str):
            value = item.strip()
        elif isinstance(item, dict):
            value = ""
            for key in ("id", "name", "model"):
                candidate = item.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    value = candidate.strip()
                    break
        else:
            value = ""
        if value:
            models.add(value)
    return sorted(models)


def probe_endpoint(endpoint: str, api_key: str = "", allow_remote: bool = False,
                   timeout: float = 5.0) -> ProbeResult:
    try:
        endpoint = validate_api_endpoint(endpoint, allow_remote=allow_remote)
    except ValueError as exc:
        parsed = urlparse(endpoint)
        host = (parsed.hostname or "").lower()
        if (not allow_remote and parsed.scheme == "https" and host
                and host not in {"127.0.0.1", "localhost", "::1"}):
            return ProbeResult(False, [], 0, "远程端点需要先勾选知情确认。")
        return ProbeResult(False, [], 0, str(exc))
    urls = probe_urls(endpoint)
    headers = {"Accept": "application/json", "User-Agent": "QQLocalInbox-Probe/1"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    last_url = urls[-1] if urls else endpoint
    for url in urls:
        started = time.perf_counter()
        request = Request(url, headers=headers, method="GET")
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read(MAX_PROBE_BYTES + 1)
        except HTTPError as exc:
            if exc.code in (401, 403):
                return ProbeResult(False, [], 0, "API Key 无效或没有访问权限。", url)
            if exc.code == 404:
                last_url = url
                continue
            return ProbeResult(False, [], 0, f"端点返回 HTTP {exc.code}。", url)
        except (URLError, OSError) as exc:
            reason = str(getattr(exc, "reason", exc))
            lower = reason.lower()
            if "refused" in lower or "10061" in lower:
                message = "连接被拒绝：服务未启动或端口未监听。"
            elif "timed out" in lower or "timeout" in lower:
                message = "连接超时：请检查地址、端口和防火墙。"
            else:
                message = f"无法连接端点：{reason}"
            return ProbeResult(False, [], 0, message, url)
        latency = int((time.perf_counter() - started) * 1000)
        if len(raw) > MAX_PROBE_BYTES:
            return ProbeResult(False, [], latency, "端点返回内容过大。", url)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return ProbeResult(False, [], latency, "端点返回的不是 JSON。", url)
        models = parse_models(payload)
        message = (f"连接成功，发现 {len(models)} 个模型。" if models
                   else "连接成功，但服务没有返回模型列表。")
        return ProbeResult(True, models, latency, message, url)
    return ProbeResult(False, [], 0, "端点可达，但没有找到模型列表接口。", last_url)
