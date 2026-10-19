import unittest
from src.onebot import OneBotListener, validate_local_ws_url, event_text, is_at_self

class OneBotTests(unittest.TestCase):
    def test_local_url_accepted(self):
        self.assertEqual(validate_local_ws_url("ws://127.0.0.1:3001"), "ws://127.0.0.1:3001")
    def test_remote_url_rejected(self):
        with self.assertRaises(ValueError): validate_local_ws_url("ws://example.com:3001")
    def test_segments_only_extract_text(self):
        value = event_text({"message": [
            {"type":"text", "data":{"text":"请交作业"}},
            {"type":"image", "data":{"file":"secret.jpg"}},
            {"type":"text", "data":{"text":"今晚截止"}},
        ]})
        self.assertEqual(value, "请交作业今晚截止")
    def test_empty_token_omits_authorization(self):
        listener = OneBotListener("ws://127.0.0.1:3001", "", False, lambda *args: None, lambda *args: None)
        self.assertEqual(listener._headers(), [])
    def test_token_is_sent_as_bearer(self):
        listener = OneBotListener("ws://127.0.0.1:3001", "secret", False, lambda *args: None, lambda *args: None)
        self.assertEqual(listener._headers(), ["Authorization: Bearer secret"])
    def test_at_self_detection(self):
        event = {"self_id": 999, "message": [
            {"type": "at", "data": {"qq": "999"}},
            {"type": "text", "data": {"text": " 看一下"}},
        ]}
        self.assertTrue(is_at_self(event))
    def test_at_other_is_not_at_self(self):
        event = {"self_id": 999, "message": [
            {"type": "at", "data": {"qq": "1001"}},
            {"type": "text", "data": {"text": " 看一下"}},
        ]}
        self.assertFalse(is_at_self(event))

if __name__ == "__main__": unittest.main()
