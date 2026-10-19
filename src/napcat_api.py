from __future__ import annotations
import json
import urllib.error
import urllib.request
from urllib.parse import urlparse
from .localnet import validate_local_url
from .onebot import event_text, is_at_self

MAX_HISTORY_COUNT = 200

class NapCatApiError(RuntimeError):
    pass

def validate_local_http_url(url: str) -> str:
    return validate_local_url(url, ("http", "https"), "NapCat HTTP 地址")

class NapCatClient:
    """Minimal client for NapCat's local OneBot 11 HTTP API."""

    def __init__(self, base_url: str, token: str = "", timeout: float = 15.0):
        base = validate_local_http_url(base_url).rstrip("/")
        parsed = urlparse(base)
        if parsed.path not in ("", "/"):
            raise ValueError("NapCat HTTP 地址只填协议、主机和端口，例如 http://127.0.0.1:3000。")
        self.base_url = base
        self.token = (token or "").strip()
        self.timeout = timeout

    def _call(self, action: str, params: dict | None = None):
        url = f"{self.base_url}/{action}"
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(
            url,
            data=json.dumps(params or {}, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            hint = "请检查 HTTP Server 的 Access Token。" if exc.code in (401, 403) else "请检查 NapCat HTTP Server 配置。"
            raise NapCatApiError(f"NapCat HTTP 请求失败（HTTP {exc.code}）。{hint}") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise NapCatApiError("无法连接 NapCat HTTP 服务，请确认已在 NapCat 开启 HTTP Server 并填写正确端口。") from None
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise NapCatApiError("NapCat 返回了无法识别的内容。") from None
        if not isinstance(payload, dict):
            raise NapCatApiError("NapCat 返回了无法识别的内容。")
        if payload.get("retcode") != 0:
            message = str(payload.get("message") or payload.get("wording") or "未知错误")[:160]
            raise NapCatApiError(f"NapCat 接口 {action} 返回错误：{message}")
        return payload.get("data")

    def list_friends(self) -> list:
        data = self._call("get_friend_list")
        return data if isinstance(data, list) else []

    def list_groups(self) -> list:
        data = self._call("get_group_list")
        return data if isinstance(data, list) else []

    def get_recent_contacts(self, count: int = 10) -> list[dict]:
        data = self._call("get_recent_contact", {"count": _clamp_recent(count)})
        if not isinstance(data, list):
            return []
        contacts = []
        for item in data:
            if not isinstance(item, dict):
                continue
            try:
                chat_type = int(item.get("chatType") or 0)
            except (TypeError, ValueError):
                continue
            kind = {1: "private", 2: "group"}.get(chat_type)
            peer = str(item.get("peerUin") or "").strip()
            if not kind or not peer or peer == "0":
                continue
            try:
                message_time = int(float(item.get("msgTime") or 0))
            except (TypeError, ValueError):
                message_time = 0
            contacts.append({"kind": kind, "id": peer,
                             "name": str(item.get("peerName") or "").strip(),
                             "message_time": message_time})
        return contacts

    def fetch_friend_history(self, user_id: str, count: int = 20) -> list[dict]:
        payload = self._call("get_friend_msg_history", {"user_id": str(user_id), "count": _clamp_count(count)})
        return self._normalize_history(payload, "private", str(user_id))

    def fetch_group_history(self, group_id: str, count: int = 20) -> list[dict]:
        payload = self._call("get_group_msg_history", {"group_id": str(group_id), "count": _clamp_count(count)})
        return self._normalize_history(payload, "group", str(group_id))

    @staticmethod
    def _normalize_history(payload, fallback_type: str, chat_id: str) -> list[dict]:
        raw_messages = payload.get("messages") if isinstance(payload, dict) else None
        if not isinstance(raw_messages, list):
            return []
        messages = []
        for raw in raw_messages:
            if not isinstance(raw, dict):
                continue
            text = event_text(raw)
            if not text:
                continue
            message_type = raw.get("message_type")
            if message_type not in {"private", "group"}:
                message_type = fallback_type
            sender = raw.get("sender") if isinstance(raw.get("sender"), dict) else {}
            user_id = raw.get("user_id") or sender.get("user_id")
            if raw.get("self_id") is not None and user_id is not None and str(user_id) == str(raw.get("self_id")):
                continue
            event = {key: raw.get(key) for key in ("time", "self_id", "message_type", "message_id", "user_id", "group_id", "group_name")}
            event["message_type"] = message_type
            event["at_me"] = is_at_self(raw)
            if message_type == "group" and not event.get("group_id"):
                event["group_id"] = chat_id
            if message_type == "private" and not event.get("user_id"):
                event["user_id"] = chat_id
            event["sender"] = {key: sender.get(key) for key in ("user_id", "nickname", "card", "role") if sender.get(key) is not None}
            messages.append({"event": event, "text": text})
        return messages

def _clamp_count(count) -> int:
    try:
        value = int(count)
    except (TypeError, ValueError):
        value = 20
    return max(1, min(value, MAX_HISTORY_COUNT))

def _clamp_recent(count) -> int:
    try:
        value = int(count)
    except (TypeError, ValueError):
        value = 10
    return max(1, min(value, 50))
