from __future__ import annotations

import hashlib
import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from src import napcat_webui
from src.napcat_webui import NapCatWebUI, NapCatWebUIError


class FakeResponse:
    def __init__(self, payload, url="http://127.0.0.1:6099/api/auth/login"):
        self._data = json.dumps(payload).encode("utf-8")
        self._url = url
        self.headers = {"Content-Type": "application/json"}

    def read(self, *_args):
        return self._data

    def geturl(self):
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class WebUiClientTests(unittest.TestCase):
    def setUp(self):
        self.client = NapCatWebUI("http://127.0.0.1:6099")

    def test_rejects_remote_base_url(self):
        with self.assertRaises(NapCatWebUIError):
            NapCatWebUI("https://example.com:6099")

    def test_login_sends_sha256_hash_and_returns_session(self):
        calls = []

        def fake_open(request, timeout=0):
            calls.append(request)
            return FakeResponse({"data": "session-token"})

        with patch.object(napcat_webui, "urlopen", side_effect=fake_open):
            session = self.client.login("webui-token")
        body = json.loads(calls[0].data.decode("utf-8"))
        self.assertEqual(body["hash"], hashlib.sha256(b"webui-token.napcat").hexdigest())
        self.assertEqual(calls[0].full_url, "http://127.0.0.1:6099/api/auth/login")
        self.assertEqual(session, "session-token")

    def test_login_accepts_credential_envelope(self):
        with patch.object(napcat_webui, "urlopen",
                          return_value=FakeResponse({"code": 0, "data": {"Credential": "abc"}})):
            self.assertEqual(self.client.login("token"), "abc")

    def test_login_maps_401_to_token_error(self):
        error = HTTPError("http://127.0.0.1:6099/api/auth/login", 401, "Unauthorized", None, None)
        with patch.object(napcat_webui, "urlopen", side_effect=error):
            with self.assertRaises(NapCatWebUIError) as ctx:
                self.client.login("bad")
        self.assertIn("Token", str(ctx.exception))

    def test_get_qrcode_returns_content(self):
        def fake_open(request, timeout=0):
            self.assertEqual(request.get_header("Authorization"), "Bearer session-token")
            return FakeResponse({"data": {"qrcode": "https://ssl.ptlogin2.qq.com/ptqrshow?x=1"}})

        self.client.session = "session-token"
        with patch.object(napcat_webui, "urlopen", side_effect=fake_open):
            value = self.client.get_qrcode()
        self.assertEqual(value, "https://ssl.ptlogin2.qq.com/ptqrshow?x=1")

    def test_check_status_maps_fields(self):
        with patch.object(napcat_webui, "urlopen", return_value=FakeResponse({
            "data": {"isLogin": False, "loginPhase": "qrcode_scanned",
                     "loginError": "", "qrcodeurl": "https://x/qr"}})):
            status = self.client.check_status()
        self.assertFalse(status.is_login)
        self.assertEqual(status.phase, "qrcode_scanned")
        self.assertEqual(status.qrcode_url, "https://x/qr")

    def test_quick_login_list_parses_accounts(self):
        with patch.object(napcat_webui, "urlopen", return_value=FakeResponse({
            "data": [{"uin": "123", "nick": "cq"}, {"uin": "456", "nick": "alt"}]})):
            accounts = self.client.quick_login_list()
        self.assertEqual([a["uin"] for a in accounts], ["123", "456"])

    def test_set_quick_login_posts_uin(self):
        calls = []

        def fake_open(request, timeout=0):
            calls.append(request)
            return FakeResponse({"data": True})

        with patch.object(napcat_webui, "urlopen", side_effect=fake_open):
            self.client.set_quick_login("123")
        self.assertEqual(json.loads(calls[0].data.decode("utf-8")), {"uin": "123"})

    def test_connection_refused_message(self):
        with patch.object(napcat_webui, "urlopen", side_effect=OSError("refused")):
            with self.assertRaises(NapCatWebUIError) as ctx:
                self.client.login("token")
        self.assertIn("未启动", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
