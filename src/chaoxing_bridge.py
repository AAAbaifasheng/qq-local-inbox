from __future__ import annotations
import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from .store import upsert_course_assignments

HOST = "127.0.0.1"
DEFAULT_PORT = 8765
PORT_ATTEMPTS = 10
MAX_BODY_BYTES = 1_000_000
MAX_ASSIGNMENTS = 1000


class _BridgeServer(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        pass


def _is_chaoxing_origin(origin: str) -> bool:
    if not origin:
        return False
    try:
        host = (urlparse(origin).hostname or "").lower()
    except ValueError:
        return False
    return host == "chaoxing.com" or host.endswith(".chaoxing.com")


class ChaoxingBridge:
    """Loopback-only receiver for assignment metadata sent by the userscript."""

    def __init__(self, token: str, on_import=None, preferred_port: int = DEFAULT_PORT):
        self.token = (token or "").strip()
        self.on_import = on_import
        self.preferred_port = int(preferred_port or DEFAULT_PORT)
        self.port = 0
        self.error = ""
        self.server = None
        self.thread = None

    @property
    def running(self) -> bool:
        return self.server is not None

    def start(self) -> bool:
        if self.server is not None:
            return True
        if not self.token:
            self.error = "本机接收服务缺少访问令牌"
            return False
        if self.preferred_port != 0 and not 1 <= self.preferred_port <= 65535:
            self.preferred_port = DEFAULT_PORT
        ports = ([0] if self.preferred_port == 0 else
                 range(self.preferred_port, min(self.preferred_port + PORT_ATTEMPTS, 65536)))
        last_error = None
        handler = self._handler_class()
        for port in ports:
            try:
                server = _BridgeServer((HOST, port), handler)
            except OSError as exc:
                last_error = exc
                continue
            self.port = int(server.server_address[1])
            self.server = server
            self.thread = threading.Thread(
                target=server.serve_forever, name="chaoxing-bridge", daemon=True)
            self.thread.start()
            self.error = ""
            return True
        self.error = f"无法监听 {HOST} 端口：{last_error}" if last_error else "无法启动本机接收服务"
        return False

    def stop(self) -> None:
        server, thread = self.server, self.thread
        self.server = self.thread = None
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None and thread.is_alive():
            thread.join(timeout=2)

    def _handler_class(self):
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "QQLocalInboxBridge/1"
            sys_version = ""

            def log_message(self, *_args):
                # Never log request bodies or assignment metadata.
                pass

            def _send(self, status: int, payload: dict) -> None:
                body = (json.dumps(payload, ensure_ascii=False).encode("utf-8")
                        if status != 204 else b"")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                origin = self.headers.get("Origin", "")
                if _is_chaoxing_origin(origin):
                    self.send_header("Access-Control-Allow-Origin", origin)
                    self.send_header("Vary", "Origin")
                    self.send_header("Access-Control-Allow-Headers",
                                     "Content-Type, X-QQLI-Token")
                    self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.end_headers()
                try:
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def _authorized(self) -> bool:
                supplied = self.headers.get("X-QQLI-Token", "")
                return bool(bridge.token) and secrets.compare_digest(supplied, bridge.token)

            def do_OPTIONS(self):
                self._send(204, {})

            def do_GET(self):
                if not self._authorized():
                    self._send(401, {"ok": False, "error": "访问令牌无效"})
                    return
                if urlparse(self.path).path == "/api/health":
                    self._send(200, {"ok": True, "app": "QQLocalInbox",
                                     "port": bridge.port, "version": 1})
                    return
                self._send(404, {"ok": False, "error": "接口不存在"})

            def do_POST(self):
                if not self._authorized():
                    self._send(401, {"ok": False, "error": "访问令牌无效"})
                    return
                if urlparse(self.path).path != "/api/chaoxing/assignments":
                    self._send(404, {"ok": False, "error": "接口不存在"})
                    return
                try:
                    length = int(self.headers.get("Content-Length", ""))
                except (TypeError, ValueError):
                    self._send(400, {"ok": False, "error": "缺少有效的 Content-Length"})
                    return
                if length <= 0:
                    self._send(400, {"ok": False, "error": "请求体为空"})
                    return
                if length > MAX_BODY_BYTES:
                    self._send(413, {"ok": False, "error": "请求体过大"})
                    return
                try:
                    payload = json.loads(self.rfile.read(length).decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    self._send(400, {"ok": False, "error": "请求体不是有效的 UTF-8 JSON"})
                    return
                if not isinstance(payload, dict):
                    self._send(400, {"ok": False, "error": "请求体必须是 JSON 对象"})
                    return
                if str(payload.get("source") or "").lower() != "chaoxing":
                    self._send(400, {"ok": False, "error": "来源必须是 chaoxing"})
                    return
                assignments = payload.get("assignments")
                if not isinstance(assignments, list):
                    self._send(400, {"ok": False, "error": "assignments 必须是数组"})
                    return
                if len(assignments) > MAX_ASSIGNMENTS:
                    self._send(413, {"ok": False, "error": "单次同步的作业数量过多"})
                    return
                try:
                    summary = upsert_course_assignments(assignments)
                except Exception:
                    self._send(500, {"ok": False, "error": "本地写入失败，请检查数据目录权限"})
                    return
                if bridge.on_import:
                    try:
                        bridge.on_import(summary)
                    except Exception:
                        pass
                self._send(200, {"ok": True, **summary})

        return Handler
