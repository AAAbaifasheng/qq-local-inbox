import unittest
from datetime import datetime

import _env

from src.store import init_db, insert_event, list_todos, clear_all_data
from src.classifier import classify_message
from src.sync import needs_model_analysis, sync_today

NOW = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)
TODAY_TS = int(NOW.timestamp())
YESTERDAY_TS = TODAY_TS - 86400

def event(message_id, user_id=1001, timestamp=None):
    return {"time": timestamp if timestamp is not None else TODAY_TS - 120,
            "self_id": 999, "message_type": "private", "message_id": message_id,
            "user_id": user_id, "sender": {"user_id": user_id, "nickname": "同学"}}

def group_event(message_id, group_id=2001, timestamp=None):
    return {"time": timestamp if timestamp is not None else TODAY_TS - 120,
            "self_id": 999, "message_type": "group", "message_id": message_id,
            "group_id": group_id, "user_id": 1003,
            "sender": {"user_id": 1003, "nickname": "群友"}}

class FakeClient:
    def __init__(self, histories, groups=None):
        self.histories = histories
        self.groups = groups or {}
    def get_recent_contacts(self, count=10):
        contacts = [
            {"kind": "private", "id": "1001", "name": "同学", "message_time": TODAY_TS - 60},
            {"kind": "private", "id": "1002", "name": "昨天联系人", "message_time": YESTERDAY_TS},
        ]
        if self.groups:
            contacts.insert(0, {"kind": "group", "id": "2001", "name": "比赛群",
                                "message_time": TODAY_TS - 30})
        return contacts
    def fetch_friend_history(self, user_id, count=20):
        return self.histories.get(user_id, [])
    def fetch_group_history(self, group_id, count=20):
        return self.groups.get(group_id, [])

class SyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        clear_all_data()

    def test_sync_today_filters_and_deduplicates(self):
        duplicate = event(1, timestamp=TODAY_TS - 120)
        insert_event(duplicate, "明天交作业", classify_message("明天交作业"))
        model_calls = []
        def model_classify(text, context=None):
            model_calls.append(text)
            return classify_message(text, context)
        histories = {
            "1001": [
                {"event": duplicate, "text": "明天交作业"},
                {"event": event(2, timestamp=TODAY_TS - 60), "text": "今晚交实验报告"},
                {"event": event(3, timestamp=TODAY_TS - 30), "text": "今天食堂人挺多"},
                {"event": event(4, timestamp=YESTERDAY_TS), "text": "昨天的消息"},
            ],
            "1002": [],
        }
        summary = sync_today(FakeClient(histories), model_classify, prefilter=classify_message, now=NOW)
        self.assertEqual(summary["contacts"], 1)
        self.assertEqual(summary["inserted"], 2)
        self.assertEqual(summary["duplicates"], 1)
        self.assertEqual(summary["pending"], 1)
        self.assertEqual(summary["model_calls"], 1)
        self.assertEqual(summary["failed"], 0)
        self.assertEqual(len(list_todos("pending_review")), 2)
        due_dates = {row["title"]: row["due_date"] for row in list_todos("pending_review")}
        self.assertTrue(due_dates["明天交作业"])
        self.assertTrue(due_dates["今晚交实验报告"])

    def test_sync_skips_groups_when_disabled(self):
        groups = {"2001": [{"event": group_event(11), "text": "明天比赛报名截止"}]}
        summary = sync_today(FakeClient({"1001": []}, groups), classify_message,
                             prefilter=classify_message, now=NOW, include_groups=False)
        self.assertEqual(summary["contacts"], 1)
        self.assertEqual(summary["inserted"], 0)
        self.assertEqual(list_todos("pending_review"), [])

    def test_sync_includes_groups_when_enabled(self):
        groups = {"2001": [{"event": group_event(12), "text": "明天比赛报名截止"}]}
        summary = sync_today(FakeClient({"1001": []}, groups), classify_message,
                             prefilter=classify_message, now=NOW, include_groups=True)
        self.assertEqual(summary["contacts"], 2)
        self.assertEqual(summary["inserted"], 1)
        self.assertEqual(summary["pending"], 1)

    def test_needs_model_analysis(self):
        self.assertFalse(needs_model_analysis(classify_message("今天食堂人挺多")))
        self.assertTrue(needs_model_analysis(classify_message("明天交实验报告")))
        self.assertTrue(needs_model_analysis({"needs_reply": True}))
        self.assertFalse(needs_model_analysis(None))

    def test_default_sync_scans_fifty_recent_contacts(self):
        class CountingClient:
            def __init__(self):
                self.requested = None
            def get_recent_contacts(self, count=10):
                self.requested = count
                return []
        client = CountingClient()
        sync_today(client, classify_message, now=NOW)
        self.assertEqual(client.requested, 50)

    def test_message_failure_does_not_abort_remaining_contacts(self):
        def model_classify(text, context=None):
            if "坏消息" in text:
                raise RuntimeError("boom")
            return classify_message(text, context)
        histories = {
            "1001": [
                {"event": event(21, timestamp=TODAY_TS - 90), "text": "坏消息"},
                {"event": event(22, timestamp=TODAY_TS - 60), "text": "明天交实验报告"},
            ],
        }
        summary = sync_today(FakeClient(histories), model_classify, now=NOW)
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(summary["inserted"], 1)
        self.assertEqual(summary["pending"], 1)
        self.assertTrue(summary["errors"])

if __name__ == "__main__":
    unittest.main()
