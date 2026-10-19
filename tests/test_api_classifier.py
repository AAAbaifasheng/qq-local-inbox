import json
import unittest
from unittest.mock import patch
from src.api_classifier import classify_with_api, validate_api_endpoint, validate_local_api_endpoint

class FakeResponse:
    def __init__(self, payload): self.payload = payload
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self): return json.dumps(self.payload).encode()

def payload_with(**overrides):
    data = {
        "categories": ["比赛/竞赛"], "importance": 85, "priority": "P0",
        "needs_reply": True, "date_hint": "明天", "task_candidate": True,
        "confidence": 0.91, "reasons": ["截止临近"], "title": "检查比赛提交"
    }
    data.update(overrides)
    return {"choices": [{"message": {"content": json.dumps(data, ensure_ascii=False)}}]}

def response_payload():
    return payload_with()

class ApiClassifierTests(unittest.TestCase):
    @patch("src.api_classifier.urllib.request.urlopen")
    def test_json_classification(self, mocked):
        mocked.return_value = FakeResponse(response_payload())
        result = classify_with_api("比赛明天截止", "http://127.0.0.1:11434/v1/chat/completions", "test-model", "secret")
        self.assertEqual(result["priority"], "P0")
        self.assertTrue(result["task_candidate"])
        self.assertEqual(result["analysis_mode"], "api")
        self.assertEqual(result["title"], "检查比赛提交")

    def test_reject_insecure_remote_endpoint(self):
        with self.assertRaises(ValueError):
            classify_with_api("hi", "http://example.com/v1/chat/completions", "m", "k")

    def test_reject_remote_https_endpoint(self):
        with self.assertRaises(ValueError):
            classify_with_api("hi", "https://api.openai.com/v1/chat/completions", "m", "k")

    def test_reject_lan_ip_endpoint(self):
        with self.assertRaises(ValueError):
            classify_with_api("hi", "http://192.168.1.10:11434/v1/chat/completions", "m", "k")

    @patch("src.api_classifier.urllib.request.urlopen")
    def test_local_endpoint_key_optional(self, mocked):
        mocked.return_value = FakeResponse(response_payload())
        result = classify_with_api("比赛明天截止", "http://localhost:1234/v1/chat/completions", "local-model", "")
        self.assertEqual(result["priority"], "P0")
        request = mocked.call_args[0][0]
        self.assertIsNone(request.get_header("Authorization"))

    def test_validate_local_endpoint_accepts_loopback(self):
        for url in ("http://127.0.0.1:11434/v1/chat/completions",
                    "http://localhost:1234/v1/chat/completions",
                    "http://[::1]:8080/v1/chat/completions"):
            self.assertEqual(validate_local_api_endpoint(url), url)

    def test_validate_local_endpoint_rejects_remote(self):
        for url in ("https://api.openai.com/v1/chat/completions",
                    "http://10.0.0.5:11434/v1/chat/completions",
                    "ftp://127.0.0.1/file"):
            with self.assertRaises(ValueError):
                validate_local_api_endpoint(url)

    def test_remote_endpoint_rejected_without_consent(self):
        with self.assertRaises(ValueError):
            validate_api_endpoint("https://api.deepseek.com/v1/chat/completions")

    def test_remote_endpoint_accepted_with_consent(self):
        url = "https://api.deepseek.com/v1/chat/completions"
        self.assertEqual(validate_api_endpoint(url, allow_remote=True), url)

    def test_remote_http_rejected_even_with_consent(self):
        with self.assertRaises(ValueError):
            validate_api_endpoint("http://api.deepseek.com/v1/chat/completions", allow_remote=True)

    @patch("src.api_classifier.urllib.request.urlopen")
    def test_remote_classification_with_consent(self, mocked):
        mocked.return_value = FakeResponse(response_payload())
        result = classify_with_api("比赛明天截止", "https://api.deepseek.com/v1/chat/completions",
                                   "deepseek-chat", "sk-test", allow_remote=True)
        self.assertEqual(result["priority"], "P0")
        request = mocked.call_args[0][0]
        self.assertEqual(request.full_url, "https://api.deepseek.com/v1/chat/completions")
        self.assertEqual(request.get_header("Authorization"), "Bearer sk-test")

    def test_remote_classification_requires_key(self):
        with self.assertRaises(ValueError):
            classify_with_api("hi", "https://api.deepseek.com/v1/chat/completions",
                              "deepseek-chat", "", allow_remote=True)

    @patch("src.api_classifier.urllib.request.urlopen")
    def test_context_is_sent_to_model(self, mocked):
        mocked.return_value = FakeResponse(response_payload())
        classify_with_api("明天比赛截止", "http://127.0.0.1:11434/v1/chat/completions", "m", "",
                          context={"is_group": True, "at_me": True, "sender_role": "admin",
                                   "group_name": "比赛群", "message_type": "group"})
        body = json.loads(mocked.call_args[0][0].data.decode())
        user_payload = json.loads(body["messages"][1]["content"])
        self.assertEqual(user_payload["context"]["at_me"], True)
        self.assertEqual(user_payload["context"]["sender_role"], "admin")

    @patch("src.api_classifier.urllib.request.urlopen")
    def test_group_discussion_question_is_overridden(self, mocked):
        mocked.return_value = FakeResponse(payload_with(
            categories=["比赛/竞赛"], importance=85, priority="P0",
            needs_reply=True, task_candidate=True, confidence=0.9))
        result = classify_with_api("萌新赛能有开箱即用的vsc吗？",
                                   "http://127.0.0.1:11434/v1/chat/completions", "m", "",
                                   context={"is_group": True, "at_me": False,
                                            "sender_role": "member", "message_type": "group"})
        self.assertFalse(result["task_candidate"])
        self.assertFalse(result["needs_reply"])
        self.assertLessEqual(result["importance"], 35)
        self.assertEqual(result["priority"], "P3")

    @patch("src.api_classifier.urllib.request.urlopen")
    def test_plain_category_is_removed_when_other_categories_exist(self, mocked):
        mocked.return_value = FakeResponse(payload_with(
            categories=["普通消息", "比赛/竞赛"], task_candidate=True))
        result = classify_with_api("比赛通知", "http://127.0.0.1:11434/v1/chat/completions", "m", "")
        self.assertEqual(result["categories"], ["比赛/竞赛"])

if __name__ == "__main__":
    unittest.main()
