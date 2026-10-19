import os
import unittest
from pathlib import Path
from src.secret_store import SECRET_API_KEY, clear_secret, load_secret, save_secret

@unittest.skipUnless(os.name == "nt", "DPAPI is Windows-only")
class SecretStoreTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._old = os.environ.get("QQLI_DATA_DIR")
        self._tmp = tempfile.mkdtemp(prefix="qqli-secret-")
        os.environ["QQLI_DATA_DIR"] = self._tmp
        clear_secret(SECRET_API_KEY)

    def tearDown(self):
        clear_secret(SECRET_API_KEY)
        if self._old is None:
            os.environ.pop("QQLI_DATA_DIR", None)
        else:
            os.environ["QQLI_DATA_DIR"] = self._old

    def test_roundtrip(self):
        self.assertTrue(save_secret(SECRET_API_KEY, "sk-test-secret"))
        self.assertEqual(load_secret(SECRET_API_KEY), "sk-test-secret")

    def test_plaintext_is_not_on_disk(self):
        save_secret(SECRET_API_KEY, "sk-test-secret")
        files = list(Path(self._tmp).glob("*"))
        self.assertTrue(files)
        for path in files:
            self.assertNotIn(b"sk-test-secret", path.read_bytes(), path.name)

    def test_clear(self):
        save_secret(SECRET_API_KEY, "sk-test-secret")
        clear_secret(SECRET_API_KEY)
        self.assertEqual(load_secret(SECRET_API_KEY), "")

if __name__ == "__main__":
    unittest.main()
