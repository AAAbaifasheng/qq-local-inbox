from __future__ import annotations
import re

CATEGORY_RULES = {
    "作业/课程": ["作业", "实验报告", "课程报告", "课后题", "交作业", "课堂展示", "课程设计", "实验截止",
                "期末考试", "期中考试", "复习", "预习", "网课", "签到", "课堂作业"],
    "比赛/竞赛": ["比赛", "竞赛", "kaggle", "cacc", "acm", "csp", "icpc", "ccpc", "蓝桥", "天梯赛",
                "挑战赛", "萌新赛", "报名截止", "初赛", "复赛", "决赛", "提交结果", "冲牌", "赛题", "排行榜",
                "校赛", "省赛", "国赛", "参赛", "组队", "报名参赛", "赛区"],
    "项目/开发": ["项目", "代码", "bug", "开发", "复现", "训练模型", "合并请求", "pull request", "pr ", "部署", "仓库",
                "接口", "测试", "上线", "需求", "评审", "版本"],
    "邀约/见面": ["约我", "约你", "有空吗", "一起吃饭", "见一面", "出来玩吗", "一起去", "周末见", "要不要来", "请你吃饭",
                "聚一下", "聚餐", "吃饭吗", "出来吗", "见面吗", "要不要一起", "有空聚", "打游戏", "一起打",
                "开黑", "去不", "来不", "出去玩", "一起玩", "看电影", "唱歌"],
    "求助/待回复": ["找你有事", "有件事", "方便回我", "尽快回复", "急事", "帮个忙", "需要你", "麻烦你", "回复我", "回我一下",
                  "有空回复", "在吗", "在不在", "在么", "忙吗", "方便说话吗", "帮我看看", "帮我看一下", "麻烦看一下",
                  "能帮我", "求助", "问一下", "请问"],
    "行政/材料": ["报名", "申请表", "申请", "材料", "盖章", "证明", "证件", "表格", "签字", "审核", "填表", "材料提交",
                "群昵称", "修改昵称", "备注名", "登记", "接龙", "助学金", "奖学金", "核对"],
    "财务/缴费": ["缴费", "交费", "付款", "转账", "报销", "账单", "续费", "押金", "退款", "收款", "收费", "班费"],
    "出行/行程": ["车票", "机票", "高铁", "航班", "酒店", "出发", "接站", "行程", "改签", "登机", "打车"],
    "健康/就医": ["挂号", "复诊", "体检", "吃药", "医院", "预约医生", "疫苗", "门诊"],
}
URGENT = ["立刻", "马上", "紧急", "尽快", "今天截止", "今晚截止", "明天截止", "最后一天", "逾期", "deadline", "截止今晚", "截止今天"]
ACTION = ["记得", "需要", "请", "要交", "交", "提交", "帮我", "麻烦", "确认一下", "回复我", "完成", "截止",
          "之前交", "之前完成", "安排一下", "报名", "填写", "填表", "修改", "处理", "准备", "领取", "参加"]
DATE_PATTERNS = [
    (r"今天|今日", "今天"), (r"今晚|今夜", "今晚"), (r"明天|明日", "明天"),
    (r"后天", "后天"), (r"周末|星期六|星期日|周六|周日", "周末/周末日期待确认"),
    (r"下周", "下周"), (r"\b20\d{2}[-年/]\d{1,2}[-月/]\d{1,2}日?\b", "明确日期待核对"),
]
DATE_BOOST = {"今天": 30, "今晚": 30, "明天": 20, "后天": 14,
              "周末/周末日期待确认": 8, "下周": 6, "明确日期待核对": 8}
GROUP_QUESTION = re.compile(
    r"[?？]|哪些|哪个|哪里|谁|什么|怎么|为什么|为啥|多少|哪[个些里]|"
    r"可不可以|能不能|行不行|有没有|是不是|对不对|吗|呢|嘛")
GROUP_ACTION_CUES = ("截止", "提交", "交", "报名", "填写", "填表", "完成", "修改", "材料",
                     "签到", "缴费", "付款", "确认", "登记", "领取", "参加", "准备", "作业", "考试")
BROADCAST_CUES = ("大家", "各位", "所有人", "全体", "同学", "请", "务必", "通知",
                  "群公告", "接龙", "统一", "统一回复")
AD_CUES = ("招聘", "招募", "招人", "招新", "家教", "代课", "兼职", "私聊", "价格",
           "费用", "报酬", "有意者", "联系我", "岗位", "有偿", "中介")
COMPETITION_INFO_CUES = ("报名", "截止", "参赛", "赛区", "初赛", "复赛", "决赛",
                         "提交", "组队", "比赛", "竞赛")
REPLY_REQUEST_CUES = ("回复", "回我", "告诉我", "私聊我", "确认一下", "联系我")


def message_context(event: dict) -> dict:
    sender = event.get("sender") if isinstance(event.get("sender"), dict) else {}
    message_type = str(event.get("message_type") or "private")
    return {
        "message_type": message_type,
        "is_group": message_type == "group",
        "group_name": str(event.get("group_name") or "")[:80],
        "sender_role": str(sender.get("role") or "")[:20],
        "at_me": bool(event.get("at_me")),
    }


def is_group_question(text: str) -> bool:
    return bool(GROUP_QUESTION.search(text or ""))


def is_group_ad(text: str) -> bool:
    low = (text or "").lower()
    return any(word in low for word in AD_CUES)


def has_reply_request(text: str) -> bool:
    low = (text or "").lower()
    return any(word in low for word in REPLY_REQUEST_CUES)


def group_message_is_actionable(text: str, categories: list[str], context: dict | None) -> bool:
    """Whether a group message not addressed to the user should become a todo."""
    if not context or not context.get("is_group") or context.get("at_me"):
        return True
    low = (text or "").lower()
    role = str(context.get("sender_role") or "").lower()
    if is_group_ad(text):
        return False
    task_cue = any(word in low for word in GROUP_ACTION_CUES)
    broadcast = any(word in low for word in BROADCAST_CUES) or role in {"owner", "admin"}
    if broadcast and task_cue:
        return True
    if is_group_question(text):
        return False
    has_date = any(re.search(pattern, text or "", re.I) for pattern, _label in DATE_PATTERNS)
    if has_date and task_cue:
        return True
    if "比赛/竞赛" in categories and any(word in low for word in COMPETITION_INFO_CUES):
        return True
    return False


def classify_message(text: str, context: dict | None = None) -> dict:
    text = (text or "").strip()
    low = text.lower()
    context = context or {}
    is_group = bool(context.get("is_group"))
    at_me = bool(context.get("at_me"))
    role = str(context.get("sender_role") or "").lower()

    categories = [category for category, words in CATEGORY_RULES.items() if any(word in low for word in words)]
    if not categories:
        categories = ["普通消息"]
    date_hint = next((label for pattern, label in DATE_PATTERNS if re.search(pattern, text, re.I)), None)
    urgent_hits = sum(1 for word in URGENT if word in low)
    action_hits = sum(1 for word in ACTION if word in low)
    score = 16 + min(urgent_hits * 24, 48) + min(action_hits * 8, 24)
    score += DATE_BOOST.get(date_hint, 0)
    if any(c in categories for c in ("作业/课程", "比赛/竞赛")):
        score += 16
    if any(c in categories for c in ("邀约/见面", "求助/待回复")):
        score += 12
    if "健康/就医" in categories:
        score += 12
    if any(c in categories for c in ("行政/材料", "财务/缴费", "出行/行程")):
        score += 8
    if categories == ["普通消息"]:
        score -= 10

    needs_reply = (any(c in categories for c in ("邀约/见面", "求助/待回复"))
                   or text.rstrip().endswith(("?", "？"))
                   or any(x in low for x in ("回复我", "回我", "告诉我", "你觉得呢", "能不能来",
                                              "可以吗", "行吗", "好不好", "能否", "怎么样",
                                              "去不", "来不", "玩不")))
    task_candidate = categories != ["普通消息"] or action_hits > 0
    reasons = []
    noise = False

    if is_group and not at_me:
        actionable = group_message_is_actionable(text, categories, context)
        if not actionable:
            task_candidate = False
            needs_reply = False
            noise = True
            score = min(score, 30)
            reasons.append("群聊讨论/广告，未直接指向你")
        else:
            needs_reply = bool(needs_reply and has_reply_request(text))
            reasons.append("群内公开通知，未直接指向你")
    elif is_group and at_me:
        score += 15
        reasons.append("群聊中直接 @ 你")

    if needs_reply:
        score += 8
        reasons.append("可能需要回复或确认")
    score = max(0, min(score, 100))
    if noise:
        priority = "P3"
    else:
        priority = "P0" if score >= 80 else "P1" if score >= 60 else "P2" if score >= 40 else "P3"

    if urgent_hits:
        reasons.append("包含紧迫性词语")
    if action_hits:
        reasons.append("包含行动/提交词语")
    if any(c in categories for c in ("作业/课程", "比赛/竞赛")):
        reasons.append("涉及课程任务或竞赛")
    if "行政/材料" in categories:
        reasons.append("涉及报名/材料/审核")
    if "财务/缴费" in categories:
        reasons.append("涉及缴费/财务")
    if "出行/行程" in categories:
        reasons.append("涉及出行/行程")
    if "健康/就医" in categories:
        reasons.append("涉及就医/健康")
    if date_hint:
        reasons.append("存在日期提示，需人工核对")
    if not reasons:
        reasons.append("未命中明显行动规则")

    if noise:
        confidence = min(0.6, 0.75 if categories != ["普通消息"] else 0.42)
    else:
        confidence = 0.84 if len(categories) > 1 else (0.75 if categories != ["普通消息"] else 0.42)
    if is_group and not at_me and not noise:
        confidence = min(confidence, 0.8)
    return {
        "categories": categories, "importance": score, "priority": priority,
        "needs_reply": bool(needs_reply), "date_hint": date_hint,
        "task_candidate": bool(task_candidate), "confidence": confidence,
        "reasons": reasons, "directed": bool((not is_group) or at_me), "noise": noise,
    }
