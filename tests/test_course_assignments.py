import unittest

import _env

from src.store import (clear_all_data, dashboard_counts, get_course_assignment,
                       init_db, list_course_assignments, review_course_assignment,
                       safe_chaoxing_url, upsert_course_assignments)


def assignment(**overrides):
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
    return item


class CourseAssignmentStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        clear_all_data()

    def test_open_assignment_is_stored_and_parsed(self):
        summary = upsert_course_assignments([assignment()])
        self.assertEqual(summary, {"inserted": 1, "updated": 0, "skipped": 0, "total": 1})
        rows = list_course_assignments()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["course_name"], "数据结构")
        self.assertEqual(row["state"], "open")
        self.assertEqual(row["status"], "pending_review")
        self.assertEqual(row["due_date"], "2099-10-20")
        self.assertEqual(row["due_time"], "23:59")
        self.assertIn("10月20日 23:59", row["due_display"])
        self.assertEqual(dashboard_counts()["course_pending"], 1)

    def test_reimport_updates_without_duplicate(self):
        upsert_course_assignments([assignment()])
        summary = upsert_course_assignments([
            assignment(title="实验二 链表（修订版）", due_at="2099-10-21 12:00")
        ])
        self.assertEqual(summary["inserted"], 0)
        self.assertEqual(summary["updated"], 1)
        rows = list_course_assignments()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "实验二 链表（修订版）")
        self.assertEqual(rows[0]["due_date"], "2099-10-21")
        self.assertEqual(rows[0]["due_time"], "12:00")

    def test_submitted_assignment_is_done_automatically(self):
        upsert_course_assignments([assignment()])
        upsert_course_assignments([assignment(status="已提交")])
        row = list_course_assignments()[0]
        self.assertEqual(row["state"], "submitted")
        self.assertEqual(row["status"], "done")
        self.assertEqual(dashboard_counts()["course_pending"], 0)

    def test_ended_assignment_stays_pending_not_done(self):
        upsert_course_assignments([assignment(status="已结束")])
        row = list_course_assignments()[0]
        self.assertEqual(row["state"], "closed")
        self.assertEqual(row["status"], "pending_review")
        self.assertEqual(dashboard_counts()["course_pending"], 1)

    def test_user_decisions_stay_sticky(self):
        upsert_course_assignments([assignment()])
        row = list_course_assignments()[0]
        self.assertTrue(review_course_assignment(row["assignment_key"], "confirmed"))
        upsert_course_assignments([assignment(status="未交")])
        self.assertEqual(list_course_assignments()[0]["status"], "confirmed")

        self.assertTrue(review_course_assignment(row["assignment_key"], "dismissed"))
        upsert_course_assignments([assignment(status="已交")])
        self.assertEqual(list_course_assignments(), [])
        hidden = list_course_assignments(include_dismissed=True)
        self.assertEqual(hidden[0]["status"], "dismissed")

    def test_invalid_items_are_skipped(self):
        summary = upsert_course_assignments([
            "not a dict",
            assignment(title=""),
            assignment(source="other"),
            assignment(url="https://chaoxing.com.evil.example/work"),
        ])
        self.assertEqual(summary["skipped"], 3)
        self.assertEqual(summary["total"], 1)
        self.assertEqual(list_course_assignments()[0]["detail_url"], "")

    def test_non_chaoxing_url_is_dropped(self):
        upsert_course_assignments([assignment(url="javascript:alert(1)")])
        self.assertEqual(list_course_assignments()[0]["detail_url"], "")

    def test_due_formats(self):
        cases = {
            "2099/10/20 23:59": ("2099-10-20", "23:59"),
            "2099年10月20日 23:59": ("2099-10-20", "23:59"),
            "2099-10-20": ("2099-10-20", ""),
            "2099-10-20T23:59:00+08:00": ("2099-10-20", "23:59"),
        }
        for index, (raw, expected) in enumerate(cases.items()):
            upsert_course_assignments([assignment(assignment_id=f"due-{index}", due_at=raw)])
        rows = {row["assignment_id"]: row for row in list_course_assignments()}
        for index, (raw, expected) in enumerate(cases.items()):
            row = rows[f"due-{index}"]
            self.assertEqual((row["due_date"], row["due_time"]), expected, raw)
        month_day = next(row for row in rows.values() if row["due_date"] == "2099-10-20")
        self.assertTrue(month_day["due_display"])

    def test_review_transitions(self):
        upsert_course_assignments([assignment()])
        key = get_course_assignment(list_course_assignments()[0]["assignment_key"])["assignment_key"]
        self.assertTrue(review_course_assignment(key, "confirmed"))
        self.assertTrue(review_course_assignment(key, "done"))
        self.assertFalse(review_course_assignment(key, "done"))
        with self.assertRaises(ValueError):
            review_course_assignment(key, "unknown")

    def test_clear_all_data_removes_course_assignments(self):
        upsert_course_assignments([assignment()])
        clear_all_data()
        self.assertEqual(list_course_assignments(), [])
        self.assertEqual(dashboard_counts()["course_pending"], 0)

    def test_safe_chaoxing_url(self):
        self.assertTrue(safe_chaoxing_url("https://mooc2-ans.chaoxing.com/work?x=1"))
        self.assertTrue(safe_chaoxing_url("http://i.chaoxing.com/base"))
        self.assertEqual(safe_chaoxing_url("https://evil.example/work"), "")
        self.assertEqual(safe_chaoxing_url("https://chaoxing.com.evil.example/work"), "")
        self.assertEqual(safe_chaoxing_url("javascript:alert(1)"), "")


if __name__ == "__main__":
    unittest.main()
