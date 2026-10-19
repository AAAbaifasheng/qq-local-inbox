import unittest
from src.classifier import classify_message

class ClassifierTests(unittest.TestCase):
    def test_assignment_candidate(self):
        a = classify_message("机器学习作业今晚截止，记得提交实验报告")
        self.assertTrue(a["task_candidate"])
        self.assertIn("作业/课程", a["categories"])
        self.assertIn(a["priority"], {"P0", "P1", "P2", "P3"})
        self.assertEqual(a["date_hint"], "今晚")
    def test_invitation_needs_reply(self):
        a = classify_message("周末有空吗？想约你一起吃饭")
        self.assertTrue(a["needs_reply"])
        self.assertIn("邀约/见面", a["categories"])
    def test_plain_message_not_todo(self):
        a = classify_message("今天食堂人挺多")
        self.assertFalse(a["task_candidate"])
    def test_competition_candidate(self):
        a = classify_message("Kaggle比赛明天截止，今晚提交结果")
        self.assertTrue(a["task_candidate"])
        self.assertIn("比赛/竞赛", a["categories"])
    def test_admin_material_candidate(self):
        a = classify_message("明天之前把报名材料交给辅导员")
        self.assertTrue(a["task_candidate"])
        self.assertIn("行政/材料", a["categories"])
    def test_finance_candidate(self):
        a = classify_message("记得今晚交班费")
        self.assertTrue(a["task_candidate"])
        self.assertIn("财务/缴费", a["categories"])
    def test_travel_candidate(self):
        a = classify_message("明天下午的高铁，记得改签")
        self.assertTrue(a["task_candidate"])
        self.assertIn("出行/行程", a["categories"])
    def test_health_candidate(self):
        a = classify_message("下周三去医院复诊")
        self.assertTrue(a["task_candidate"])
        self.assertIn("健康/就医", a["categories"])
    def test_ping_is_reply_candidate(self):
        a = classify_message("在吗")
        self.assertTrue(a["task_candidate"])
        self.assertTrue(a["needs_reply"])
        self.assertIn("求助/待回复", a["categories"])
    def test_question_mark_requires_reply(self):
        a = classify_message("这个作业什么时候交？")
        self.assertTrue(a["needs_reply"])
        self.assertIn("作业/课程", a["categories"])

    def test_group_discussion_question_is_not_candidate(self):
        a = classify_message("萌新赛能有开箱即用的vsc吗？",
                             {"is_group": True, "at_me": False, "sender_role": "member"})
        self.assertFalse(a["task_candidate"])
        self.assertFalse(a["needs_reply"])
        self.assertEqual(a["priority"], "P3")

    def test_group_question_at_me_is_candidate(self):
        a = classify_message("这个作业什么时候交？",
                             {"is_group": True, "at_me": True, "sender_role": "member"})
        self.assertTrue(a["task_candidate"])
        self.assertTrue(a["needs_reply"])

    def test_group_admin_broadcast_is_candidate(self):
        a = classify_message("请修改群昵称为 年级-专业-昵称",
                             {"is_group": True, "at_me": False, "sender_role": "admin"})
        self.assertTrue(a["task_candidate"])
        self.assertIn("行政/材料", a["categories"])

    def test_group_deadline_notice_is_candidate(self):
        a = classify_message("明天交实验报告",
                             {"is_group": True, "at_me": False, "sender_role": "member"})
        self.assertTrue(a["task_candidate"])

    def test_group_competition_status_is_info_candidate(self):
        a = classify_message("CACC 报名貌似满了",
                             {"is_group": True, "at_me": False, "sender_role": "member"})
        self.assertTrue(a["task_candidate"])
        self.assertFalse(a["needs_reply"])
        self.assertIn(a["priority"], {"P2", "P3"})

    def test_group_ad_is_not_candidate(self):
        a = classify_message("周一晚上7点到9点半，需要一个男生代课。代价私聊",
                             {"is_group": True, "at_me": False, "sender_role": "member"})
        self.assertFalse(a["task_candidate"])

    def test_group_joke_with_remember_is_not_candidate(self):
        a = classify_message("对不起导员，记得给我算志愿时长，这是我们大足人的传统。",
                             {"is_group": True, "at_me": False, "sender_role": "member"})
        self.assertFalse(a["task_candidate"])

    def test_group_question_to_others_is_not_candidate(self):
        a = classify_message("我们班的寝室长是哪些，麻烦发一下姓名+学号",
                             {"is_group": True, "at_me": False, "sender_role": "member"})
        self.assertFalse(a["task_candidate"])
        self.assertFalse(a["needs_reply"])

    def test_private_play_invitation_is_candidate(self):
        a = classify_message("明天一起打游戏去不")
        self.assertTrue(a["task_candidate"])
        self.assertTrue(a["needs_reply"])
        self.assertIn("邀约/见面", a["categories"])

    def test_scholarship_application_is_admin_task(self):
        a = classify_message("今天内完成智慧学工系统助学金申请")
        self.assertTrue(a["task_candidate"])
        self.assertIn("行政/材料", a["categories"])

if __name__ == "__main__": unittest.main()
