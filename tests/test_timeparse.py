import unittest
from datetime import date, datetime
from src.timeparse import format_due_display, resolve_due

SUNDAY = datetime(2026, 10, 18, 12, 0)
MONDAY = datetime(2026, 10, 19, 12, 0)

class DueDateTests(unittest.TestCase):
    def check(self, text, expected_date, hint=None, reference=SUNDAY):
        due, display = resolve_due(text, hint, reference)
        self.assertEqual(due, expected_date, f"{text!r} -> {due!r} ({display!r})")
        self.assertIn(expected_date, display)
        return display

    def test_today_tonight(self):
        display = self.check("机器学习作业今晚截止", "2026-10-18")
        self.assertIn("今晚", display)

    def test_tomorrow(self):
        self.check("明天交作业", "2026-10-19")

    def test_day_after_tomorrow(self):
        self.check("后天提交", "2026-10-20")

    def test_weekend_is_next_saturday_from_sunday(self):
        display = self.check("周末一起吃饭", "2026-10-24")
        self.assertIn("周六", display)

    def test_this_weekend_on_sunday_is_today(self):
        self.check("这个周末有空吗", "2026-10-18")

    def test_next_week_wednesday(self):
        self.check("下周三交材料", "2026-10-21")

    def test_bare_wednesday_is_upcoming(self):
        self.check("周三前给我", "2026-10-21")

    def test_friday_upcoming_from_sunday(self):
        self.check("周五之前完成", "2026-10-23")

    def test_this_week_friday_from_monday(self):
        self.check("本周五前提交", "2026-10-23", reference=MONDAY)

    def test_next_week_without_day_is_monday(self):
        self.check("下周再说", "2026-10-19")

    def test_explicit_month_day(self):
        self.check("10月20日截止", "2026-10-20")

    def test_explicit_month_day_rolls_to_next_year(self):
        self.check("10月20日截止", "2027-10-20", reference=datetime(2026, 12, 1, 12, 0))

    def test_explicit_full_date(self):
        self.check("2026-10-20 18:00 前提交", "2026-10-20")

    def test_time_of_day_is_concrete(self):
        display = self.check("明天下午3点开会", "2026-10-19")
        self.assertIn("15:00", display)

    def test_tonight_time(self):
        display = self.check("今晚8点前发我", "2026-10-18")
        self.assertIn("20:00", display)

    def test_uses_reference_date_not_now(self):
        self.check("明天交", "2026-10-11", reference=datetime(2026, 10, 10, 9, 0))

    def test_hint_fallback(self):
        self.check("记得交作业", "2026-10-19", hint="明天")

    def test_explicit_hint_wins_over_ambiguous_source(self):
        text = ("今天是2026年10月19日，学校安排如下：每日早晨5：00前到校；"
                "这周四收取50元资料费")
        self.check(text, "2026-10-22", hint="2026-10-22", reference=MONDAY)

    def test_no_date(self):
        due, display = resolve_due("记得看一下消息", "明确日期待核对", SUNDAY)
        self.assertIsNone(due)
        self.assertIn("待核对", display)

class StoredDueDisplayTests(unittest.TestCase):
    TODAY = date(2026, 10, 19)

    def test_stale_relative_label_is_recomputed(self):
        self.assertEqual(
            format_due_display("2026-10-19", "2026-10-19（明天）", None, today=self.TODAY),
            "2026-10-19（今天）")

    def test_explicit_time_is_preserved(self):
        self.assertEqual(
            format_due_display("2026-10-19", "2026-10-19 16:00（明天）", None,
                               today=self.TODAY),
            "2026-10-19 16:00（今天）")

    def test_daypart_is_preserved(self):
        self.assertEqual(
            format_due_display("2026-10-19", "2026-10-19（明天 晚上）", None,
                               today=self.TODAY),
            "2026-10-19（今天 晚上）")

    def test_same_due_date_never_mixes_today_and_tomorrow(self):
        values = {
            format_due_display("2026-10-19", stored, None, today=self.TODAY)
            for stored in ("2026-10-19（今天）", "2026-10-19（明天）",
                           "2026-10-19 16:00（明天）")
        }
        self.assertEqual(values, {"2026-10-19（今天）", "2026-10-19 16:00（今天）"})

    def test_future_date_uses_fresh_label(self):
        self.assertEqual(
            format_due_display("2026-10-20", "2026-10-20（今天）", None, today=self.TODAY),
            "2026-10-20（明天）")

    def test_missing_date_falls_back_to_hint(self):
        self.assertEqual(format_due_display(None, None, "周五前", today=self.TODAY), "周五前")


if __name__ == "__main__":
    unittest.main()
