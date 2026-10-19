from __future__ import annotations
import json
import re
import threading
import time
from websocket import WebSocketApp
from .localnet import validate_local_url

def validate_local_ws_url(url: str) -> str:
    return validate_local_url(url, ("ws", "wss"), "WebSocket 地址")

def is_at_self(event: dict) -> bool:
    self_id = str(event.get("self_id") or "")
    raw = event.get("message")
    if not self_id or not isinstance(raw, list):
        return False
    for segment in raw:
        if not isinstance(segment, dict) or segment.get("type") != "at":
            continue
        data = segment.get("data") or {}
        if isinstance(data, dict) and str(data.get("qq") or "") == self_id:
            return True
    return False

def event_text(event: dict) -> str:
    raw = event.get("message")
    if isinstance(raw, str):
        text = raw
    elif isinstance(raw, list):
        pieces = []
        for item in raw:
            if not isinstance(item, dict) or item.get("type") != "text":
                continue
            data = item.get("data") or {}
            if isinstance(data, dict):
                pieces.append(str(data.get("text", "")))
        text = "".join(pieces)
    else:
        text = str(event.get("raw_message") or "")
    # Avoid persisting CQ segment payloads/attachment markers if only raw_message was available.
    text = re.sub(r"\[CQ:[^\]]*\]", " ", text)
    return re.sub(r"\s+", " ", text).strip()

class OneBotListener:
    def __init__(self, url: str, token: str, include_groups: bool, on_event, on_status):
        self.url = validate_local_ws_url(url)
        self.token = token.strip()
        self.include_groups = include_groups
        self.on_event = on_event
        self.on_status = on_status
        self.stop_event = threading.Event()
        self.thread = None
        self.ws = None
        self.started_at = None

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.started_at = time.time()
        self.thread = threading.Thread(target=self._run, name="OneBotListener", daemon=True)
        self.thread.start()

    def _headers(self) -> list[str]:
        return [f"Authorization: Bearer {self.token}"] if self.token else []

    def stop(self):
        self.stop_event.set()
        ws = self.ws
        if ws:
            try: ws.close()
            except Exception: pass
        self.on_status("已停止监听")

    def _run(self):
        while not self.stop_event.is_set():
            try:
                app = WebSocketApp(self.url, header=self._headers(),
                    on_open=self._on_open, on_message=self._on_message,
                    on_error=self._on_error, on_close=self._on_close)
                self.ws = app
                app.run_forever(ping_interval=20, ping_timeout=10, http_proxy_host=None, http_proxy_port=None, http_no_proxy=["localhost", "127.0.0.1", "::1"])
            except Exception as exc:
                self.on_status(f"连接异常：{type(exc).__name__}（详情请检查地址、Token 与 NapCat 日志）")
            if not self.stop_event.is_set():
                self.on_status("连接已断开，4 秒后重连…")
                self.stop_event.wait(4)
        self.ws = None

    def _on_open(self, ws):
        self.on_status("已连接；只接收启用后的实时事件，不自动拉取历史消息")

    def _on_message(self, ws, payload):
        if self.stop_event.is_set():
            return
        try:
            event = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            return
        if not isinstance(event, dict) or event.get("post_type") != "message":
            return
        message_type = event.get("message_type")
        if message_type not in {"private", "group"}:
            return
        if message_type == "group" and not self.include_groups:
            return
        # Incoming messages only. Do not classify this account's own sent messages.
        if event.get("user_id") is not None and str(event.get("user_id")) == str(event.get("self_id")):
            return
        # WS is a live event stream, not a history API. The timestamp check drops old queued events.
        try:
            event_time = float(event.get("time", 0))
            if event_time and self.started_at and event_time < int(self.started_at):
                return
        except (TypeError, ValueError):
            pass
        text = event_text(event)
        if not text:
            return
        # Pass a narrow allowlisted event; never pass/store the raw websocket payload.
        allowed = {k: event.get(k) for k in ("time", "self_id", "message_type", "message_id", "user_id", "group_id", "group_name")}
        allowed["at_me"] = is_at_self(event)
        sender = event.get("sender") if isinstance(event.get("sender"), dict) else {}
        allowed["sender"] = {k: sender.get(k) for k in ("user_id", "nickname", "card", "role") if sender.get(k) is not None}
        self.on_event(allowed, text)

    def _on_error(self, ws, error):
        self.on_status(f"连接错误：{type(error).__name__}（请检查 NapCat 监听端口和 Access Token）")

    def _on_close(self, ws, code, message):
        if not self.stop_event.is_set():
            self.on_status("WebSocket 已关闭，尝试重连…")
