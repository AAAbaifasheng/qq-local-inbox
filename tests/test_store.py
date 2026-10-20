import os
import unittest
from datetime import datetime, timedelta
from pathlib import Path

# Must point at a test-only directory before importing src.store: DB_PATH is
# resolved at import time, and setUp clears the database.
import _env
_TEST_DATA_DIR = os.environ["QQLI_DATA_DIR"]

from src.store import (DB_PATH, init_db, insert_event, list_todos, list_messages, review_todo,
                       list_contacts, clear_all_data, dashboard_counts, list_priority_items,
                       list_competition_items, build_message_key, message_exists)
from src.classifier import classify_message

_TODAY_NOON = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)

def make_event(message_id, user_id=1001, nickname="测试同学", message_type="private"):
    return {"time": int(_TODAY_NOON.timestamp()) + message_id, "self_id": 999,
            "message_type": message_type, "message_id": message_id, "user_id": user_id,
            "sender": {"user_id": user_id, "nickname": nickname}}

class StoreWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        clear_all_data()

    def test_database_is_isolated_under_test_dir(self):
        self.assertEqual(Path(DB_PATH).parent, Path(_TEST_DATA_DIR))

    def test_manual_review_then_confirm_then_done(self):
        text = "机器学习作业今晚截止，记得提交实验报告"
        self.assertTrue(insert_event(make_event(12), text, classify_message(text)))
        self.assertEqual(len(list_todos("pending_review")), 1)
        self.assertEqual(len(list_todos("confirmed")), 0)
        todo_id = list_todos("pending_review")[0]["id"]
        self.assertTrue(review_todo(todo_id, "confirmed"))
        self.assertEqual(len(list_todos("confirmed")), 1)
        self.assertTrue(review_todo(todo_id, "done"))
        self.assertEqual(len(list_todos("confirmed")), 0)

    def test_duplicate_message_is_ignored(self):
        text = "周末有空吗？想约你一起吃饭"
        event = make_event(99, user_id=1002, nickname="邀约测试")
        self.assertTrue(insert_event(event, text, classify_message(text)))
        self.assertFalse(insert_event(event, text, classify_message(text)))
        self.assertEqual(len(list_messages()), 1)

    def test_same_text_same_chat_keeps_one_active_todo(self):
        text = "请修改群昵称为 年级-专业-昵称"
        analysis = classify_message(text)
        insert_event(make_event(201), text, analysis)
        insert_event(make_event(202), text, analysis)
        self.assertEqual(len(list_messages()), 2)
        self.assertEqual(len(list_todos("pending_review")), 1)

    def test_same_text_different_chats_keeps_two_todos(self):
        text = "明天交实验报告"
        analysis = classify_message(text)
        insert_event(make_event(211, user_id=1001), text, analysis)
        insert_event(make_event(212, user_id=1002), text, analysis)
        self.assertEqual(len(list_todos("pending_review")), 2)

    def test_duplicate_todo_keeps_highest_priority_and_due(self):
        text = "明天交实验报告"
        low = classify_message(text)
        low.update({"importance": 30, "priority": "P3", "date_hint": None})
        high = classify_message(text)
        high.update({"importance": 80, "priority": "P0", "date_hint": "明天"})
        insert_event(make_event(221), text, low)
        insert_event(make_event(222), text, high)
        rows = list_todos("pending_review")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["importance"], 80)
        self.assertEqual(rows[0]["priority"], "P0")
        self.assertTrue(rows[0]["due_date"])

    def test_contact_ranking_populated(self):
        text = "方便回我吗，有个比赛提交问题需要你"
        insert_event(make_event(199, user_id=1003, nickname="队友"), text, classify_message(text))
        contacts = list_contacts()
        self.assertEqual(len(contacts), 1)
        self.assertGreaterEqual(contacts[0]["pending_count"], 1)
        self.assertGreater(contacts[0]["rank_score"], 0)
        self.assertTrue(contacts[0]["last_message_at"])
        self.assertGreaterEqual(contacts[0]["today_count"], 1)

    def test_dashboard_counts(self):
        assignment = "机器学习作业今晚截止，记得提交实验报告"
        insert_event(make_event(300, nickname="同学"), assignment, classify_message(assignment))
        assignment_id = list_todos("pending_review")[0]["id"]
        review_todo(assignment_id, "confirmed")

        competition = "Kaggle比赛明天截止，今晚提交结果"
        insert_event(make_event(301, user_id=1002, nickname="队友"), competition, classify_message(competition))

        invitation = "周末有空吗？想约你一起吃饭"
        insert_event(make_event(302, user_id=1004, nickname="朋友"), invitation, classify_message(invitation))

        help_text = "急事，方便回我一下"
        insert_event(make_event(303, user_id=1005, nickname="同学B"), help_text, classify_message(help_text))

        self.assertEqual(dashboard_counts(), {
            "today_todos": 1,
            "pending_replies": 2,
            "competitions_projects": 1,
            "pending_invites": 1,
            "today_messages": 4,
            "course_pending": 0,
            "course_today": 0,
        })

    def test_priority_items_are_ordered_and_include_pending(self):
        competition = "Kaggle比赛明天截止，今晚提交结果，尽快完成"
        insert_event(make_event(400, user_id=1002, nickname="队友"), competition, classify_message(competition))
        assignment = "机器学习作业今晚截止，记得提交实验报告"
        insert_event(make_event(401, nickname="同学"), assignment, classify_message(assignment))

        items = list_priority_items()
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["priority"], "P0")
        self.assertIn(items[0]["status"], {"pending_review", "confirmed"})
        self.assertTrue(items[0]["title"])

    def test_due_date_is_resolved_from_message_time(self):
        text = "明天交作业"
        insert_event(make_event(500), text, classify_message(text))
        row = list_todos("pending_review")[0]
        expected = (datetime.now() + timedelta(days=1)).date().isoformat()
        self.assertEqual(row["due_date"], expected)
        self.assertIn("明天", row["due_display"])

    def test_message_exists_checks_without_api_call(self):
        event = make_event(600)
        key = build_message_key(event)
        self.assertFalse(message_exists(key))
        insert_event(event, "明天交作业", classify_message("明天交作业"))
        self.assertTrue(message_exists(key))

    def test_group_name_is_kept_in_chat_label(self):
        event = make_event(700, user_id=1006, nickname="群友", message_type="group")
        event["group_id"] = 555
        event["group_name"] = "机器学习群"
        insert_event(event, "群作业明天交", classify_message("群作业明天交"))
        self.assertIn("机器学习群", list_messages()[0]["chat_label"])

    def test_competition_list_only_includes_competitions(self):
        cases = (
            (800, 1002, "队友", "Kaggle比赛明天截止，今晚提交结果，尽快完成"),
            (801, 1003, "同学", "项目代码有个bug，尽快合并请求"),
            (802, 1004, "同学B", "机器学习作业今晚截止，记得提交实验报告"),
        )
        for message_id, user_id, nickname, text in cases:
            insert_event(make_event(message_id, user_id=user_id, nickname=nickname), text, classify_message(text))
        items = list_competition_items()
        self.assertEqual(len(items), 1)
        self.assertIn("Kaggle", items[0]["title"])
        self.assertIn("比赛/竞赛", items[0]["category"])
        todo_id = items[0]["id"]
        self.assertTrue(review_todo(todo_id, "confirmed"))
        confirmed = list_competition_items()
        self.assertEqual(len(confirmed), 1)
        self.assertEqual(confirmed[0]["status"], "confirmed")

    def test_api_title_is_used_for_todo(self):
        text = "Kaggle 比赛明天截止，今晚提交结果"
        analysis = classify_message(text)
        analysis["title"] = "检查比赛提交"
        insert_event(make_event(200), text, analysis)
        self.assertEqual(list_todos("pending_review")[0]["title"], "检查比赛提交")

    def test_newlines_are_replaced_in_todo_title(self):
        text = "第一行\n第二行"
        analysis = {"categories": ["作业/课程"], "importance": 60, "priority": "P1",
                    "needs_reply": False, "date_hint": None, "task_candidate": True,
                    "confidence": 0.7, "reasons": ["包含行动/提交词语"]}
        insert_event(make_event(201), text, analysis)
        title = list_todos("pending_review")[0]["title"]
        self.assertNotIn("\n", title)
        self.assertEqual(title, "第一行 第二行")

if __name__ == "__main__":
    unittest.main()
