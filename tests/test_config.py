import json
import os
import tempfile
import unittest

from src.config import config_path, load_settings, save_settings

class ConfigTests(unittest.TestCase):
    def setUp(self):
        self._old = os.environ.get("QQLI_DATA_DIR")
        self._tmp = tempfile.mkdtemp(prefix="qqli-config-")
        os.environ["QQLI_DATA_DIR"] = self._tmp

    def tearDown(self):
        if self._old is None:
            os.environ.pop("QQLI_DATA_DIR", None)
        else:
            os.environ["QQLI_DATA_DIR"] = self._old

    def test_remote_saved_endpoint_is_loaded(self):
        endpoint = "https://api.deepseek.com/v1/chat/completions"
        config_path().write_text(json.dumps({
            "api_endpoint": endpoint,
            "analysis_mode": "api",
        }), encoding="utf-8")
        settings = load_settings()
        self.assertEqual(settings["api_endpoint"], endpoint)
        self.assertEqual(settings["analysis_mode"], "api")

    def test_insecure_remote_endpoint_falls_back_to_local(self):
        config_path().write_text(json.dumps({
            "api_endpoint": "http://example.com/v1/chat/completions",
        }), encoding="utf-8")
        self.assertEqual(load_settings()["api_endpoint"], "http://127.0.0.1:11434/v1/chat/completions")

    def test_remote_https_endpoint_is_persisted(self):
        endpoint = "https://api.deepseek.com/v1/chat/completions"
        save_settings({"api_endpoint": endpoint, "ws_url": "ws://127.0.0.1:3001"})
        saved = json.loads(config_path().read_text(encoding="utf-8"))
        self.assertEqual(saved["api_endpoint"], endpoint)

    def test_insecure_remote_endpoint_is_not_persisted(self):
        save_settings({"api_endpoint": "http://example.com/v1/chat/completions",
                       "ws_url": "ws://127.0.0.1:3001"})
        saved = json.loads(config_path().read_text(encoding="utf-8"))
        self.assertEqual(saved["api_endpoint"], "http://127.0.0.1:11434/v1/chat/completions")

    def test_auto_and_remote_flags_persist(self):
        save_settings({"auto_connect": False, "auto_sync_today": False, "allow_remote_api": True})
        settings = load_settings()
        self.assertFalse(settings["auto_connect"])
        self.assertFalse(settings["auto_sync_today"])
        self.assertTrue(settings["allow_remote_api"])

    def test_update_flags_default_on_and_persist(self):
        self.assertTrue(load_settings()["auto_check_updates"])
        self.assertTrue(load_settings()["auto_download_updates"])
        self.assertTrue(load_settings()["auto_apply_updates"])
        save_settings({"auto_check_updates": False, "auto_download_updates": False,
                       "auto_apply_updates": False})
        settings = load_settings()
        self.assertFalse(settings["auto_check_updates"])
        self.assertFalse(settings["auto_download_updates"])
        self.assertFalse(settings["auto_apply_updates"])

    def test_napcat_settings_defaults_and_persist(self):
        settings = load_settings()
        self.assertTrue(settings["auto_launch_napcat"])
        self.assertTrue(settings["auto_quick_login"])
        self.assertEqual(settings["napcat_webui_url"], "http://127.0.0.1:6099")
        save_settings({"napcat_root": "C:/NapCat", "auto_launch_napcat": False,
                       "auto_quick_login": False})
        settings = load_settings()
        self.assertEqual(settings["napcat_root"], "C:/NapCat")
        self.assertFalse(settings["auto_launch_napcat"])
        self.assertFalse(settings["auto_quick_login"])

    def test_version_file_matches_module(self):
        from pathlib import Path
        from src.version import __version__
        value = (Path(__file__).resolve().parents[1] / "VERSION").read_text(
            encoding="utf-8").strip()
        self.assertEqual(__version__, value)
        self.assertRegex(value, r"^\d+\.\d+\.\d+$")

    def test_secrets_and_legacy_consent_are_not_written(self):
        save_settings({"ws_url": "ws://127.0.0.1:3001", "api_key": "sk-secret",
                       "access_token": "token-secret", "api_consent": True})
        text = config_path().read_text(encoding="utf-8")
        self.assertNotIn("sk-secret", text)
        self.assertNotIn("token-secret", text)
        self.assertNotIn("api_consent", text)
        self.assertIn("history_api_url", text)

if __name__ == "__main__":
    unittest.main()
