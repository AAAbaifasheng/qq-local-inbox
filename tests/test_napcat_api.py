import json
import unittest
import urllib.error
from unittest.mock import patch
from src.napcat_api import NapCatApiError, NapCatClient

class FakeResponse:
    def __init__(self, payload): self.payload = payload
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self): return json.dumps(self.payload).encode()

def envelope(data):
    return {"status": "ok", "retcode": 0, "data": data, "message": "", "wording": "", "echo": None}

class NapCatClientTests(unittest.TestCase):
    def test_rejects_remote_base_url(self):
        with self.assertRaises(ValueError):
            NapCatClient("http://192.168.1.20:3000", "t")

    @patch("src.napcat_api.urllib.request.urlopen")
    def test_posts_action_with_bearer_token(self, mocked):
        mocked.return_value = FakeResponse(envelope([{"user_id": 1001, "nickname": "同学", "remark": "备注"}]))
        friends = NapCatClient("http://127.0.0.1:3000/", "secret").list_friends()
        self.assertEqual(friends[0]["user_id"], 1001)
        request = mocked.call_args[0][0]
        self.assertEqual(request.full_url, "http://127.0.0.1:3000/get_friend_list")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Authorization"), "Bearer secret")
        self.assertEqual(json.loads(request.data), {})

    @patch("src.napcat_api.urllib.request.urlopen")
    def test_omits_authorization_when_token_empty(self, mocked):
        mocked.return_value = FakeResponse(envelope([]))
        NapCatClient("http://localhost:3000", "").list_groups()
        request = mocked.call_args[0][0]
        self.assertIsNone(request.get_header("Authorization"))
        self.assertEqual(request.full_url, "http://localhost:3000/get_group_list")

    @patch("src.napcat_api.urllib.request.urlopen")
    def test_friend_history_normalizes_messages(self, mocked):
        mocked.return_value = FakeResponse(envelope({"messages": [
            {"time": 1792261800, "self_id": 999, "message_type": "private", "message_id": 1,
             "user_id": 1001, "sender": {"user_id": 1001, "nickname": "同学"},
             "message": [{"type": "text", "data": {"text": "作业今晚截止"}},
                          {"type": "image", "data": {"file": "x.jpg"}}]},
            {"time": 1792261801, "self_id": 999, "message_type": "private", "message_id": 2,
             "user_id": 999, "sender": {"user_id": 999, "nickname": "我"},
             "message": "这条是我发的"},
            {"time": 1792261802, "self_id": 999, "message_type": "private", "message_id": 3,
             "user_id": 1001, "sender": {"user_id": 1001, "nickname": "同学"},
             "message": [{"type": "image", "data": {"file": "y.jpg"}}]},
        ]}))
        messages = NapCatClient("http://127.0.0.1:3000", "secret").fetch_friend_history("1001", 20)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["text"], "作业今晚截止")
        self.assertEqual(messages[0]["event"]["user_id"], 1001)
        request = mocked.call_args[0][0]
        self.assertEqual(request.full_url, "http://127.0.0.1:3000/get_friend_msg_history")
        self.assertEqual(json.loads(request.data), {"user_id": "1001", "count": 20})

    @patch("src.napcat_api.urllib.request.urlopen")
    def test_group_history_uses_group_id(self, mocked):
        mocked.return_value = FakeResponse(envelope({"messages": [
            {"time": 1792261803, "self_id": 999, "message_type": "group", "message_id": 4,
             "group_id": 555, "user_id": 1001, "sender": {"user_id": 1001, "nickname": "同学", "card": "名片"},
             "message": "群作业明天交"},
        ]}))
        messages = NapCatClient("http://127.0.0.1:3000", "secret").fetch_group_history("555", 10)
        self.assertEqual(messages[0]["event"]["sender"]["card"], "名片")
        request = mocked.call_args[0][0]
        self.assertEqual(request.full_url, "http://127.0.0.1:3000/get_group_msg_history")
        self.assertEqual(json.loads(request.data), {"group_id": "555", "count": 10})

    @patch("src.napcat_api.urllib.request.urlopen")
    def test_recent_contacts_are_normalized(self, mocked):
        mocked.return_value = FakeResponse(envelope([
            {"peerUin": "1001", "peerName": "同学", "msgTime": "1792261800", "chatType": 1},
            {"peerUin": "555", "peerName": "课程群", "msgTime": "1792261900", "chatType": 2},
            {"peerUin": "999", "peerName": "其他", "msgTime": "1792262000", "chatType": 42},
            {"peerUin": "0", "peerName": "无效", "msgTime": "1792262100", "chatType": 1},
        ]))
        contacts = NapCatClient("http://127.0.0.1:3000", "").get_recent_contacts(10)
        self.assertEqual(contacts, [
            {"kind": "private", "id": "1001", "name": "同学", "message_time": 1792261800},
            {"kind": "group", "id": "555", "name": "课程群", "message_time": 1792261900},
        ])
        request = mocked.call_args[0][0]
        self.assertEqual(request.full_url, "http://127.0.0.1:3000/get_recent_contact")
        self.assertEqual(json.loads(request.data), {"count": 10})

    @patch("src.napcat_api.urllib.request.urlopen")
    def test_retcode_error_is_raised(self, mocked):
        mocked.return_value = FakeResponse({"status": "failed", "retcode": 1404, "data": None,
                                            "message": "不支持的API", "wording": "不支持的API"})
        with self.assertRaises(NapCatApiError) as ctx:
            NapCatClient("http://127.0.0.1:3000", "secret").list_friends()
        self.assertIn("get_friend_list", str(ctx.exception))

    @patch("src.napcat_api.urllib.request.urlopen")
    def test_http_error_message_does_not_leak_token(self, mocked):
        mocked.side_effect = urllib.error.HTTPError("http://127.0.0.1:3000/get_friend_list", 403,
                                                    "token verify failed", None, None)
        with self.assertRaises(NapCatApiError) as ctx:
            NapCatClient("http://127.0.0.1:3000", "super-secret-token").list_friends()
        self.assertNotIn("super-secret-token", str(ctx.exception))
        self.assertIn("403", str(ctx.exception))

if __name__ == "__main__":
    unittest.main()
