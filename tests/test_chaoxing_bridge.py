import http.client
import json
import unittest

import _env

from src.chaoxing_bridge import MAX_BODY_BYTES, ChaoxingBridge
from src.store import clear_all_data, init_db, list_course_assignments

TOKEN = "test-bridge-token"


def payload(**overrides):
    item = {
        "source": "chaoxing",
        "course_id": "course-1",
        "course_name": "数据结构",
        "assignment_id": "work-1",
        "title": "实验二 链表",
        "due_at": "2099-10-20 23:59",
        "status": "未交",
        "url": "https://mooc2-ans.chaoxing.com/mooc2/work/view?workId=1",
    }
    item.update(overrides)
    return {"source": "chaoxing", "assignments": [item]}


class ChaoxingBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        clear_all_data()
        self.imports = []
        self.bridge = ChaoxingBridge(TOKEN, self.imports.append, preferred_port=0)
        self.assertTrue(self.bridge.start(), self.bridge.error)

    def tearDown(self):
        self.bridge.stop()

    def request(self, method, path, body=None, token=TOKEN, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.bridge.port, timeout=5)
        request_headers = dict(headers or {})
        if token is not None:
            request_headers["X-QQLI-Token"] = token
        if body is not None and "Content-Type" not in request_headers:
            request_headers["Content-Type"] = "application/json"
        if isinstance(body, str):
            body = body.encode("utf-8")
        connection.request(method, path, body=body, headers=request_headers)
        response = connection.getresponse()
        raw = response.read()
        connection.close()
        parsed = json.loads(raw.decode("utf-8")) if raw else None
        return response.status, response.getheaders(), parsed

    def test_binds_loopback_only(self):
        self.assertEqual(self.bridge.server.server_address[0], "127.0.0.1")
        self.assertGreater(self.bridge.port, 0)

    def test_health_requires_token(self):
        status, _headers, data = self.request("GET", "/api/health", token=None)
        self.assertEqual(status, 401)
        self.assertFalse(data["ok"])
        status, _headers, data = self.request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(data["app"], "QQLocalInbox")
        self.assertEqual(data["port"], self.bridge.port)

    def test_import_assignments(self):
        body = json.dumps(payload(), ensure_ascii=False)
        status, _headers, data = self.request("POST", "/api/chaoxing/assignments", body)
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])
        self.assertEqual(data["inserted"], 1)
        rows = list_course_assignments()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "实验二 链表")
        self.assertEqual(self.imports, [{"inserted": 1, "updated": 0, "skipped": 0, "total": 1}])

    def test_wrong_token_is_rejected(self):
        body = json.dumps(payload(), ensure_ascii=False)
        status, _headers, data = self.request(
            "POST", "/api/chaoxing/assignments", body, token="wrong")
        self.assertEqual(status, 401)
        self.assertFalse(data["ok"])
        self.assertEqual(list_course_assignments(), [])

    def test_invalid_payloads_are_rejected(self):
        cases = [
            ("not json", 400),
            (json.dumps({"source": "other", "assignments": []}), 400),
            (json.dumps({"source": "chaoxing", "assignments": {}}), 400),
        ]
        for body, expected in cases:
            status, _headers, _data = self.request(
                "POST", "/api/chaoxing/assignments", body)
            self.assertEqual(status, expected, body)

    def test_oversized_body_is_rejected_before_reading(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.bridge.port, timeout=5)
        connection.putrequest("POST", "/api/chaoxing/assignments")
        connection.putheader("X-QQLI-Token", TOKEN)
        connection.putheader("Content-Type", "application/json")
        connection.putheader("Content-Length", str(MAX_BODY_BYTES + 1))
        connection.endheaders()
        response = connection.getresponse()
        self.assertEqual(response.status, 413)
        response.read()
        connection.close()

    def test_cors_preflight_for_chaoxing_origin(self):
        status, headers, _data = self.request(
            "OPTIONS", "/api/chaoxing/assignments", token=None,
            headers={"Origin": "https://mooc2-ans.chaoxing.com"})
        self.assertEqual(status, 204)
        self.assertEqual(dict(headers)["Access-Control-Allow-Origin"],
                         "https://mooc2-ans.chaoxing.com")

    def test_cors_is_not_granted_to_other_origins(self):
        status, headers, _data = self.request(
            "OPTIONS", "/api/chaoxing/assignments", token=None,
            headers={"Origin": "https://evil.example"})
        self.assertEqual(status, 204)
        self.assertNotIn("Access-Control-Allow-Origin", dict(headers))

    def test_stop_releases_port(self):
        port = self.bridge.port
        self.bridge.stop()
        self.assertFalse(self.bridge.running)
        replacement = ChaoxingBridge(TOKEN, preferred_port=port)
        self.assertTrue(replacement.start(), replacement.error)
        self.assertEqual(replacement.port, port)
        replacement.stop()


if __name__ == "__main__":
    unittest.main()
