from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
MAX_BODY_BYTES = 2_000_000


class NapCatWebUIError(Exception):
    pass


@dataclass(frozen=True)
class LoginStatus:
    is_login: bool
    phase: str
    error: str
    qrcode_url: str


class NapCatWebUI:
    """Loopback-only client for NapCat's management WebUI login API."""

    def __init__(self, base_url: str = "http://127.0.0.1:6099", timeout: float = 8.0):
        parsed = urlparse(str(base_url or "").strip())
        host = (parsed.hostname or "").lower()
        if parsed.scheme not in ("http", "https") or host not in LOCAL_HOSTS:
            raise NapCatWebUIError("NapCat WebUI 只允许连接本机地址（127.0.0.1 / localhost / ::1）。")
        if parsed.username or parsed.password:
            raise NapCatWebUIError("NapCat WebUI 地址中不要嵌入账号密码。")
        self.base = f"{parsed.scheme}://{parsed.netloc}"
        self.timeout = timeout
        self.session: str | None = None

    def _request(self, path: str, body: dict | None = None, auth: bool = True):
        url = f"{self.base}/api{path}"
        headers = {"Content-Type": "application/json", "User-Agent": "QQLocalInbox-NapCat/1"}
        if auth and self.session:
            headers["Authorization"] = f"Bearer {self.session}"
        request = Request(url, data=json.dumps(body or {}).encode("utf-8"),
                            headers=headers, method="POST")
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read(MAX_BODY_BYTES + 1)
        except HTTPError as exc:
            if exc.code in (401, 403):
                raise NapCatWebUIError("WebUI Token 无效或会话已过期。") from exc
            if exc.code == 404:
                raise NapCatWebUIError("NapCat WebUI 接口不存在：请确认 NapCat 版本与 WebUI 已开启。") from exc
            raise NapCatWebUIError(f"NapCat WebUI 返回 HTTP {exc.code}。") from exc
        except (URLError, OSError) as exc:
            raise NapCatWebUIError("无法连接 NapCat WebUI：NapCat 未启动或 WebUI 未开启。") from exc
        if len(raw) > MAX_BODY_BYTES:
            raise NapCatWebUIError("NapCat WebUI 响应过大。")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise NapCatWebUIError("NapCat WebUI 响应不是 JSON。") from exc
        if isinstance(payload, dict):
            if payload.get("status") == "failed":
                raise NapCatWebUIError(str(payload.get("message") or "NapCat WebUI 请求失败。"))
            return payload.get("data")
        return payload

    def login(self, token: str, totp_code: str = "") -> str:
        digest = hashlib.sha256(f"{token}.napcat".encode("utf-8")).hexdigest()
        data = self._request("/auth/login", {"hash": digest, "totpCode": totp_code}, auth=False)
        if isinstance(data, dict):
            session = str(data.get("Credential") or data.get("credential")
                          or data.get("token") or "")
        else:
            session = str(data or "")
        if not session:
            raise NapCatWebUIError("NapCat WebUI 登录未返回会话令牌。")
        self.session = session
        return session

    def get_qrcode(self) -> str:
        data = self._request("/QQLogin/GetQQLoginQrcode")
        if isinstance(data, dict):
            return str(data.get("qrcode") or data.get("qrcodeurl") or "")
        return str(data or "")

    def refresh_qrcode(self) -> tuple[str, bool]:
        data = self._request("/QQLogin/RefreshQRcode")
        if not isinstance(data, dict):
            return "", False
        return str(data.get("qrcodeurl") or data.get("qrcode") or ""), bool(data.get("restarting"))

    def check_status(self) -> LoginStatus:
        data = self._request("/QQLogin/CheckLoginStatus")
        if not isinstance(data, dict):
            return LoginStatus(False, "unknown", "", "")
        return LoginStatus(
            is_login=bool(data.get("isLogin")),
            phase=str(data.get("loginPhase") or ""),
            error=str(data.get("loginError") or ""),
            qrcode_url=str(data.get("qrcodeurl") or data.get("qrcode") or ""),
        )

    def quick_login_list(self) -> list[dict]:
        data = self._request("/QQLogin/GetQuickLoginList")
        accounts = []
        for item in data if isinstance(data, list) else []:
            if isinstance(item, dict) and item.get("uin"):
                accounts.append({"uin": str(item["uin"]), "nick": str(item.get("nick") or item["uin"])})
        return accounts

    def set_quick_login(self, uin: str) -> None:
        self._request("/QQLogin/SetQuickLogin", {"uin": str(uin)})
