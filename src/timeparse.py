from __future__ import annotations
import re
from datetime import date, datetime, timedelta

WEEKDAY_CHARS = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
WEEKDAY_NAMES = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")

def resolve_due(text: str, date_hint: str | None = None, reference: datetime | None = None) -> tuple[str | None, str]:
    """Resolve relative Chinese date hints against the message time, not wall-clock now."""
    source = (text or "").strip()
    hint = (date_hint or "").strip()
    ref = reference or datetime.now()
    ref_date = ref.date()

    due = _parse_explicit_date(hint, ref_date) if hint else None
    if due is None:
        due = _parse_explicit_date(source, ref_date)
    if due is None:
        due = _parse_relative_date(source, ref_date)
    if due is None and hint:
        due = _parse_relative_date(hint, ref_date)
    if due is None:
        return None, hint

    time_str = _parse_time(source)
    daypart = _parse_daypart(source)
    label = _relative_label(due, ref_date)
    suffix = f"{label} {daypart}" if daypart and not time_str else label
    display = f"{due.isoformat()}{' ' + time_str if time_str else ''}（{suffix}）"
    return due.isoformat(), display

_RELATIVE_LABEL_PREFIX = re.compile(
    r"^(今天|明天|后天|大后天|下周[一二三四五六日天]|(?:周|星期|礼拜)[一二三四五六日天])\s*"
)


def format_due_display(due_date: str | None, due_display: str | None = None,
                       due_hint: str | None = None, today: date | None = None) -> str:
    """Re-render a stored due value so relative labels follow the current day.

    due_display is written relative to the message time at insert time. Rendering
    it later unchanged makes the same due date show 今天 for one message and
    明天 for another; only the absolute date in due_date is authoritative.
    """
    if not due_date:
        return due_display or due_hint or "待核对"
    try:
        due = date.fromisoformat(str(due_date)[:10])
    except ValueError:
        return due_display or due_hint or str(due_date)

    label = _relative_label(due, today or date.today())
    stored = due_display or ""
    time_match = re.search(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)", stored)
    time_str = (f"{int(time_match.group(1)):02d}:{time_match.group(2)}"
                if time_match else "")
    daypart = ""
    parenthetical = re.search(r"（([^）]*)）", stored)
    if parenthetical:
        daypart = _RELATIVE_LABEL_PREFIX.sub("", parenthetical.group(1)).strip()
    suffix = f"{label} {daypart}" if daypart else label
    return f"{due.isoformat()}{' ' + time_str if time_str else ''}（{suffix}）"


def _parse_explicit_date(source: str, ref_date: date) -> date | None:
    match = re.search(r"(\d{4})\s*[-/年]\s*(\d{1,2})\s*[-/月]\s*(\d{1,2})\s*日?", source)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            return None
    match = re.search(r"(?<!\d)(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]?", source)
    if match:
        month, day = int(match.group(1)), int(match.group(2))
        try:
            due = date(ref_date.year, month, day)
        except ValueError:
            return None
        if (ref_date - due).days > 30:
            try:
                due = date(ref_date.year + 1, month, day)
            except ValueError:
                return None
        return due
    return None

def _monday_of(ref_date: date) -> date:
    return ref_date - timedelta(days=ref_date.weekday())

def _next_saturday(ref_date: date) -> date:
    if ref_date.weekday() == 5:
        return ref_date
    offset = (5 - ref_date.weekday()) % 7
    return ref_date + timedelta(days=offset or 7)

def _parse_relative_date(source: str, ref_date: date) -> date | None:
    if "大后天" in source:
        return ref_date + timedelta(days=3)
    if "后天" in source:
        return ref_date + timedelta(days=2)
    if any(word in source for word in ("明天", "明日", "明晚")):
        return ref_date + timedelta(days=1)
    if any(word in source for word in ("今天", "今日", "今晚", "今夜", "本日")):
        return ref_date

    if any(word in source for word in ("这个周末", "这周末", "本周末")):
        if ref_date.weekday() >= 5:
            return ref_date
        return ref_date + timedelta(days=5 - ref_date.weekday())
    if "周末" in source or "双休" in source:
        return _next_saturday(ref_date)

    match = re.search(r"(下下周|下下星期|下下礼拜|下周|下星期|下礼拜|本周|这周|本星期|这星期|本礼拜|这礼拜|周|星期|礼拜)\s*([一二三四五六日天])", source)
    if match:
        prefix, char = match.group(1), match.group(2)
        target = WEEKDAY_CHARS[char]
        monday = _monday_of(ref_date)
        if prefix in {"下下周", "下下星期", "下下礼拜"}:
            return monday + timedelta(days=14 + target)
        if prefix in {"下周", "下星期", "下礼拜"}:
            return monday + timedelta(days=7 + target)
        if prefix in {"本周", "这周", "本星期", "这星期", "本礼拜", "这礼拜"}:
            return monday + timedelta(days=target)
        candidate = monday + timedelta(days=target)
        if candidate < ref_date:
            candidate += timedelta(days=7)
        return candidate

    if re.search(r"下(?:周|星期|礼拜)(?!\s*[一二三四五六日天])", source):
        return _monday_of(ref_date) + timedelta(days=7)
    return None

def _parse_time(source: str) -> str | None:
    match = re.search(r"(?<!\d)([01]?\d|2[0-3])[:：]([0-5]\d)(?!\d)", source)
    if match:
        return f"{int(match.group(1)):02d}:{match.group(2)}"

    match = re.search(r"(上午|中午|下午|晚上|傍晚|凌晨|早上)?\s*([0-2]?\d)\s*(?:点|时)(?:([0-5]?\d)\s*分?)?", source)
    if not match:
        return None
    period = match.group(1) or ""
    hour, minute = int(match.group(2)), int(match.group(3) or 0)
    evening = any(word in source for word in ("今晚", "今夜", "明晚", "明晚", "后天晚上"))
    if (period in {"下午", "晚上", "傍晚"} or evening) and hour < 12:
        hour += 12
    elif period == "中午" and hour < 11:
        hour += 12
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return f"{hour:02d}:{minute:02d}"
    return None

def _parse_daypart(source: str) -> str:
    for word in ("今晚", "今夜", "明晚", "后天晚上", "上午", "早上", "下午", "晚上", "傍晚", "中午", "凌晨"):
        if word in source:
            return word
    return ""

def _relative_label(due: date, ref_date: date) -> str:
    delta = (due - ref_date).days
    if delta == 0:
        return "今天"
    if delta == 1:
        return "明天"
    if delta == 2:
        return "后天"
    if delta == 3:
        return "大后天"
    next_monday = _monday_of(ref_date) + timedelta(days=7)
    if next_monday <= due < next_monday + timedelta(days=7):
        return "下" + WEEKDAY_NAMES[due.weekday()]
    return WEEKDAY_NAMES[due.weekday()]
