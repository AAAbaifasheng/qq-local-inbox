from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from src import api_probe
from src.api_probe import parse_models, probe_endpoint, probe_urls


class FakeResponse:
    def __init__(self, payload):
        self._data = json.dumps(payload).encode("utf-8")
        self.headers = {"Content-Type": "application/json"}

    def read(self, *_args):
        return self._data

    def geturl(self):
        return "https://example.invalid/"

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class ProbeUrlTests(unittest.TestCase):
    def test_ollama_tries_tags_then_openai_models(self):
        urls = probe_urls("http://127.0.0.1:11434/v1/chat/completions")
        self.assertEqual(urls[0], "http://127.0.0.1:11434/api/tags")
        self.assertIn("http://127.0.0.1:11434/v1/models", urls)

    def test_deepseek_tries_models_endpoints(self):
        urls = probe_urls("https://api.deepseek.com/v1/chat/completions")
        self.assertEqual(urls[0], "https://api.deepseek.com/models")
        self.assertIn("https://api.deepseek.com/v1/models", urls)

    def test_custom_openai_compatible_uses_v1_models(self):
        urls = probe_urls("http://127.0.0.1:1234/v1/chat/completions")
        self.assertEqual(urls, ["http://127.0.0.1:1234/v1/models"])


class ParseModelsTests(unittest.TestCase):
    def test_openai_shape(self):
        payload = {"data": [{"id": "deepseek-flash"}, {"id": "deepseek-v4-pro"}]}
        self.assertEqual(parse_models(payload), ["deepseek-flash", "deepseek-v4-pro"])

    def test_ollama_shape(self):
        payload = {"models": [{"name": "qwen3:8b"}, {"model": "llama3.2:3b"}]}
        self.assertEqual(parse_models(payload), ["llama3.2:3b", "qwen3:8b"])

    def test_plain_list_and_empty(self):
        self.assertEqual(parse_models(["b", "a", "b"]), ["a", "b"])
        self.assertEqual(parse_models({}), [])


class ProbeEndpointTests(unittest.TestCase):
    def test_probe_reads_openai_models_and_sends_bearer(self):
        calls = []

        def fake_open(request, timeout=0):
            calls.append(request)
            return FakeResponse({"data": [{"id": "deepseek-flash"}]})

        with patch.object(api_probe, "urlopen", side_effect=fake_open):
            result = probe_endpoint(
                "https://api.deepseek.com/v1/chat/completions",
                api_key="secret-key",
                allow_remote=True,
            )
        self.assertTrue(result.ok)
        self.assertEqual(result.models, ["deepseek-flash"])
        self.assertEqual(calls[0].get_header("Authorization"), "Bearer secret-key")

    def test_probe_reads_ollama_models_without_key(self):
        with patch.object(api_probe, "urlopen", return_value=FakeResponse(
                {"models": [{"name": "qwen3:8b"}]})):
            result = probe_endpoint("http://127.0.0.1:11434/v1/chat/completions")
        self.assertTrue(result.ok)
        self.assertEqual(result.models, ["qwen3:8b"])

    def test_probe_maps_401_to_readable_error(self):
        error = HTTPError("https://api.deepseek.com/models", 401, "Unauthorized", None, None)
        with patch.object(api_probe, "urlopen", side_effect=error):
            result = probe_endpoint(
                "https://api.deepseek.com/v1/chat/completions",
                api_key="bad",
                allow_remote=True,
            )
        self.assertFalse(result.ok)
        self.assertIn("Key", result.message)

    def test_probe_rejects_remote_without_consent_before_network(self):
        with patch.object(api_probe, "urlopen") as mocked:
            result = probe_endpoint("https://api.deepseek.com/v1/chat/completions")
        self.assertFalse(result.ok)
        self.assertIn("知情确认", result.message)
        mocked.assert_not_called()

    def test_probe_falls_back_on_404(self):
        error = HTTPError("https://api.deepseek.com/models", 404, "Not Found", None, None)
        with patch.object(api_probe, "urlopen", side_effect=[error, FakeResponse(
                {"data": [{"id": "deepseek-flash"}]})]):
            result = probe_endpoint(
                "https://api.deepseek.com/v1/chat/completions",
                api_key="key",
                allow_remote=True,
            )
        self.assertTrue(result.ok)
        self.assertEqual(result.models, ["deepseek-flash"])


if __name__ == "__main__":
    unittest.main()
