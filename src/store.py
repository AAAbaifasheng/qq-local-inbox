from __future__ import annotations
import hashlib
import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from .config import data_dir
from .timeparse import resolve_due

DB_PATH = data_dir() / "inbox.sqlite3"

@contextmanager
def connect():
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.row_factory = sqlite3.Row
    try:
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA busy_timeout=10000")
        c.execute("PRAGMA secure_delete=ON")
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()

def init_db():
    with connect() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS messages (
          message_key TEXT PRIMARY KEY,
          message_id TEXT NOT NULL,
          message_type TEXT NOT NULL,
          chat_id TEXT NOT NULL,
          sender_id TEXT NOT NULL,
          sender_name TEXT NOT NULL,
          chat_label TEXT NOT NULL,
          timestamp TEXT NOT NULL,
          text TEXT NOT NULL,
          analysis_json TEXT NOT NULL,
          received_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS todos (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          message_key TEXT NOT NULL UNIQUE REFERENCES messages(message_key) ON DELETE CASCADE,
          title TEXT NOT NULL,
          category TEXT NOT NULL,
          priority TEXT NOT NULL,
          importance INTEGER NOT NULL,
          due_hint TEXT,
          needs_reply INTEGER NOT NULL DEFAULT 0,
          confidence REAL NOT NULL,
          reasons_json TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'pending_review',
          created_at TEXT NOT NULL,
          reviewed_at TEXT,
          dedupe_key TEXT
        );
        CREATE TABLE IF NOT EXISTS course_assignments (
          assignment_key TEXT PRIMARY KEY,
          source TEXT NOT NULL,
          course_id TEXT NOT NULL,
          course_name TEXT NOT NULL,
          assignment_id TEXT NOT NULL,
          title TEXT NOT NULL,
          due_date TEXT,
          due_time TEXT,
          due_display TEXT,
          state TEXT NOT NULL,
          state_text TEXT NOT NULL DEFAULT '',
          detail_url TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'pending_review',
          first_seen_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          reviewed_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_messages_received ON messages(received_at DESC);
        CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender_id, timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_todos_status_priority ON todos(status, importance DESC);
        CREATE INDEX IF NOT EXISTS idx_course_status_due
          ON course_assignments(status, state, due_date);
        """)
        columns = {row["name"] for row in c.execute("PRAGMA table_info(todos)").fetchall()}
        if "due_date" not in columns:
            c.execute("ALTER TABLE todos ADD COLUMN due_date TEXT")
        if "due_display" not in columns:
            c.execute("ALTER TABLE todos ADD COLUMN due_display TEXT")
        if "dedupe_key" not in columns:
            c.execute("ALTER TABLE todos ADD COLUMN dedupe_key TEXT")
        c.execute("CREATE INDEX IF NOT EXISTS idx_todos_dedupe ON todos(dedupe_key, status)")
        _backfill_due_dates(c)
        _backfill_dedupe_keys(c)
        _merge_duplicate_todos(c)

def _backfill_due_dates(c):
    rows = c.execute("""SELECT t.id,t.due_hint,t.due_date,m.timestamp,m.text
      FROM todos t JOIN messages m ON m.message_key=t.message_key
      WHERE t.due_date IS NULL""").fetchall()
    for row in rows:
        try:
            reference = datetime.fromisoformat(row["timestamp"])
        except (TypeError, ValueError):
            reference = datetime.now().astimezone()
        due_date, due_display = resolve_due(row["text"], row["due_hint"], reference)
        c.execute("UPDATE todos SET due_date=?,due_display=? WHERE id=?",
                  (due_date, due_display or row["due_hint"], row["id"]))

def _normalize_source_text(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "")).lower()[:500]

def _todo_dedupe_key(chat_id: str, source_text: str, due_date: str | None) -> str:
    raw = f"{chat_id}|{_normalize_source_text(source_text)}|{due_date or ''}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()

def _backfill_dedupe_keys(c):
    rows = c.execute("""SELECT t.id,t.due_date,m.chat_id,m.text
      FROM todos t JOIN messages m ON m.message_key=t.message_key
      WHERE t.dedupe_key IS NULL""").fetchall()
    for row in rows:
        key = _todo_dedupe_key(row["chat_id"], row["text"], row["due_date"])
        c.execute("UPDATE todos SET dedupe_key=? WHERE id=?", (key, row["id"]))

def _priority_rank(priority: str) -> int:
    return {"P0": 0, "P1": 1, "P2": 2, "P3": 3}.get(priority, 3)

def _merge_duplicate_todos(c):
    rows = c.execute("""SELECT t.id,t.dedupe_key,t.status,t.importance,t.priority,t.due_hint,
      t.due_date,t.due_display,t.needs_reply
      FROM todos t JOIN messages m ON m.message_key=t.message_key
      WHERE t.status IN ('pending_review','confirmed') AND t.dedupe_key IS NOT NULL
      ORDER BY t.id""").fetchall()
    groups = {}
    for row in rows:
        groups.setdefault(row["dedupe_key"], []).append(row)
    for entries in groups.values():
        if len(entries) < 2:
            continue
        confirmed = [entry for entry in entries if entry["status"] == "confirmed"]
        if confirmed:
            keep = max(confirmed, key=lambda entry: (entry["importance"], -entry["id"]))
            remove = [entry for entry in entries if entry["status"] == "pending_review"]
        else:
            keep = max(entries, key=lambda entry: (entry["importance"], -entry["id"]))
            remove = [entry for entry in entries if entry["id"] != keep["id"]]
        best_importance = max(entry["importance"] for entry in entries)
        best_priority = min((entry["priority"] for entry in entries), key=_priority_rank)
        due_hint = next((entry["due_hint"] for entry in entries if entry["due_hint"]), None)
        due_date = next((entry["due_date"] for entry in entries if entry["due_date"]), None)
        due_display = next((entry["due_display"] for entry in entries if entry["due_display"]), None)
        needs_reply = max(entry["needs_reply"] for entry in entries)
        c.execute("""UPDATE todos SET importance=?,priority=?,due_hint=COALESCE(due_hint,?),
          due_date=COALESCE(due_date,?),due_display=COALESCE(due_display,?),needs_reply=?
          WHERE id=?""", (best_importance, best_priority, due_hint, due_date, due_display,
                           needs_reply, keep["id"]))
        for entry in remove:
            c.execute("DELETE FROM todos WHERE id=? AND status='pending_review'", (entry["id"],))

def build_message_key(event: dict) -> str:
    msg_type = str(event.get("message_type", "private"))
    sender = event.get("sender") if isinstance(event.get("sender"), dict) else {}
    sender_id = str(event.get("user_id") or sender.get("user_id") or "unknown")
    chat_id = str(event.get("group_id") if msg_type == "group" else sender_id)
    message_id = str(event.get("message_id") or "")
    self_id = str(event.get("self_id") or "unknown")
    return f"{self_id}:{msg_type}:{chat_id}:{message_id or event.get('time', '')}:{sender_id}"

def message_exists(message_key: str) -> bool:
    with connect() as c:
        return c.execute("SELECT 1 FROM messages WHERE message_key=?", (message_key,)).fetchone() is not None

def insert_event(event: dict, text: str, analysis: dict) -> bool:
    """Store only live event fields; no raw payload, media, cookies, or credentials."""
    msg_type = str(event.get("message_type", "private"))
    sender = event.get("sender") if isinstance(event.get("sender"), dict) else {}
    sender_id = str(event.get("user_id") or sender.get("user_id") or "unknown")
    sender_name = str(sender.get("card") or sender.get("nickname") or sender_id)[:100]
    chat_id = str(event.get("group_id") if msg_type == "group" else sender_id)
    if msg_type == "group":
        group_name = str(event.get("group_name") or "").strip()
        group_label = f"{group_name}({chat_id})" if group_name else chat_id
        chat_label = f"群 {group_label} · {sender_name}"[:150]
    else:
        chat_label = sender_name
    message_id = str(event.get("message_id") or "")
    message_key = build_message_key(event)
    timestamp_value = event.get("time")
    try:
        reference = datetime.fromtimestamp(float(timestamp_value), tz=timezone.utc).astimezone()
    except (TypeError, ValueError, OSError):
        reference = datetime.now().astimezone()
    timestamp = reference.isoformat(timespec="seconds")
    due_date, due_display = resolve_due(text, analysis.get("date_hint"), reference)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    analysis_json = json.dumps(analysis, ensure_ascii=False)
    with connect() as c:
        cur = c.execute("""INSERT OR IGNORE INTO messages
          (message_key,message_id,message_type,chat_id,sender_id,sender_name,chat_label,timestamp,text,analysis_json,received_at)
          VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (message_key,message_id,msg_type,chat_id,sender_id,sender_name,chat_label,timestamp,text,analysis_json,now))
        if cur.rowcount == 0:
            return False
        if analysis.get("task_candidate"):
            category = "、".join(analysis.get("categories", []))
            title = str(analysis.get("title") or text).replace("\r", " ").replace("\n", " ").strip()[:180] or "（无文字内容）"
            dedupe_key = _todo_dedupe_key(chat_id, text, due_date)
            existing = c.execute("""SELECT id,importance,priority,due_hint,due_date,due_display,needs_reply
              FROM todos WHERE dedupe_key=? AND status IN ('pending_review','confirmed')
              ORDER BY CASE status WHEN 'confirmed' THEN 0 ELSE 1 END, importance DESC, id
              LIMIT 1""", (dedupe_key,)).fetchone()
            if existing:
                importance = max(existing["importance"], int(analysis["importance"]))
                priority = (analysis["priority"]
                            if _priority_rank(analysis["priority"]) <= _priority_rank(existing["priority"])
                            else existing["priority"])
                due_hint = existing["due_hint"] or analysis.get("date_hint")
                merged_due_date = existing["due_date"] or due_date
                due_display = existing["due_display"] or due_display or due_hint
                needs_reply = max(existing["needs_reply"], int(bool(analysis.get("needs_reply"))))
                c.execute("""UPDATE todos SET importance=?,priority=?,due_hint=?,due_date=?,
                  due_display=?,needs_reply=? WHERE id=?""",
                          (importance, priority, due_hint, merged_due_date, due_display,
                           needs_reply, existing["id"]))
            else:
                c.execute("""INSERT OR IGNORE INTO todos
                  (message_key,title,category,priority,importance,due_hint,due_date,due_display,needs_reply,
                   confidence,reasons_json,status,created_at,dedupe_key)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?, 'pending_review',?,?)""", (
                    message_key, title, category,
                    analysis["priority"], int(analysis["importance"]), analysis.get("date_hint"),
                    due_date, due_display, int(bool(analysis.get("needs_reply"))),
                    float(analysis.get("confidence", 0.4)),
                    json.dumps(analysis.get("reasons", []), ensure_ascii=False), now, dedupe_key))
    return True

def list_messages(limit=200):
    with connect() as c:
        return c.execute("SELECT * FROM messages ORDER BY timestamp DESC, received_at DESC LIMIT ?", (limit,)).fetchall()

def list_todos(status: str, limit=500):
    with connect() as c:
        return c.execute("""SELECT t.*,m.chat_label,m.sender_id,m.timestamp,m.text AS source_text
          FROM todos t JOIN messages m ON m.message_key=t.message_key
          WHERE t.status=? ORDER BY CASE t.priority WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 ELSE 3 END,
          t.importance DESC,t.created_at DESC LIMIT ?""", (status,limit)).fetchall()

def review_todo(todo_id: int, decision: str) -> bool:
    if decision not in {"confirmed", "dismissed", "done"}:
        raise ValueError("invalid decision")
    with connect() as c:
        cur = c.execute("UPDATE todos SET status=?,reviewed_at=? WHERE id=? AND status IN ('pending_review','confirmed')",
                         (decision, datetime.now(timezone.utc).isoformat(timespec="seconds"), todo_id))
        return cur.rowcount > 0

def list_contacts(limit=500):
    """Rank conversation participants by open workload and urgency; not by personal worth."""
    with connect() as c:
        rows = c.execute("""SELECT m.chat_label,
          COUNT(DISTINCT m.message_key) AS message_count,
          COUNT(DISTINCT CASE WHEN t.status='pending_review' THEN t.id END) AS pending_count,
          COUNT(DISTINCT CASE WHEN t.status='confirmed' THEN t.id END) AS confirmed_count,
          COUNT(DISTINCT CASE WHEN t.needs_reply=1 AND t.status IN ('pending_review','confirmed') THEN t.id END) AS reply_count,
          COALESCE(MAX(CASE WHEN t.status IN ('pending_review','confirmed') THEN t.importance ELSE 0 END),0) AS max_importance,
          COALESCE(MAX(CASE WHEN t.status IN ('pending_review','confirmed') THEN CASE t.priority WHEN 'P0' THEN 4 WHEN 'P1' THEN 3 WHEN 'P2' THEN 2 WHEN 'P3' THEN 1 ELSE 0 END ELSE 0 END),0) AS priority_rank,
          MAX(m.timestamp) AS last_message_at,
          COUNT(DISTINCT CASE WHEN substr(m.timestamp,1,10)=date('now','localtime') THEN m.message_key END) AS today_count,
          (COALESCE(MAX(CASE WHEN t.status IN ('pending_review','confirmed') THEN t.importance ELSE 0 END),0) +
            COUNT(DISTINCT CASE WHEN t.status='pending_review' THEN t.id END)*8 +
            COUNT(DISTINCT CASE WHEN t.status='confirmed' THEN t.id END)*4 +
            COUNT(DISTINCT CASE WHEN t.needs_reply=1 AND t.status IN ('pending_review','confirmed') THEN t.id END)*12) AS rank_score
          FROM messages m LEFT JOIN todos t ON t.message_key=m.message_key
          GROUP BY m.chat_label
          ORDER BY rank_score DESC, last_message_at DESC, message_count DESC LIMIT ?""", (limit,)).fetchall()
        return rows

def dashboard_counts() -> dict:
    with connect() as c:
        row = c.execute("""SELECT
          COALESCE(SUM(CASE WHEN status='confirmed' AND due_date=date('now','localtime') THEN 1 ELSE 0 END),0) AS today_todos,
          COALESCE(SUM(CASE WHEN needs_reply=1 AND status IN ('pending_review','confirmed') THEN 1 ELSE 0 END),0) AS pending_replies,
          COALESCE(SUM(CASE WHEN status IN ('pending_review','confirmed') AND (category LIKE '%比赛/竞赛%' OR category LIKE '%项目/开发%') THEN 1 ELSE 0 END),0) AS competitions_projects,
          COALESCE(SUM(CASE WHEN status='pending_review' AND category LIKE '%邀约/见面%' THEN 1 ELSE 0 END),0) AS pending_invites,
          (SELECT COUNT(*) FROM messages WHERE substr(timestamp,1,10)=date('now','localtime')) AS today_messages,
          (SELECT COUNT(*) FROM course_assignments
            WHERE status IN ('pending_review','confirmed')
              AND state IN ('open','unknown','closed')) AS course_pending,
          (SELECT COUNT(*) FROM course_assignments
            WHERE status IN ('pending_review','confirmed')
              AND state IN ('open','unknown','closed')
              AND due_date=date('now','localtime')) AS course_today
          FROM todos""").fetchone()
        return {key: int(row[key]) for key in
                ("today_todos", "pending_replies", "competitions_projects", "pending_invites",
                 "today_messages", "course_pending", "course_today")}

def list_priority_items(limit=12):
    with connect() as c:
        return c.execute("""SELECT t.*, m.chat_label, m.timestamp, m.text AS source_text
          FROM todos t JOIN messages m ON m.message_key=t.message_key
          WHERE t.status IN ('pending_review','confirmed')
          ORDER BY CASE t.priority WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 ELSE 3 END,
          t.importance DESC, t.created_at DESC LIMIT ?""", (limit,)).fetchall()

def list_competition_items(limit=500):
    with connect() as c:
        return c.execute("""SELECT t.*, m.chat_label, m.timestamp, m.text AS source_text
          FROM todos t JOIN messages m ON m.message_key=t.message_key
          WHERE t.category LIKE '%比赛/竞赛%'
            AND t.status IN ('pending_review','confirmed','done')
          ORDER BY CASE t.status WHEN 'pending_review' THEN 0 WHEN 'confirmed' THEN 1 ELSE 2 END,
          CASE t.priority WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 ELSE 3 END,
          t.importance DESC, t.due_date IS NULL, t.due_date, t.created_at DESC LIMIT ?""", (limit,)).fetchall()

COURSE_DECISIONS = {"confirmed", "done", "dismissed"}

def _clean_course_text(value, limit: int) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]

def safe_chaoxing_url(value: str) -> str:
    """Only keep http(s) links that point at chaoxing.com or a subdomain."""
    url = str(value or "").strip()
    if not url or len(url) > 1000:
        return ""
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
    except ValueError:
        return ""
    if parsed.scheme not in ("http", "https") or not host:
        return ""
    if host != "chaoxing.com" and not host.endswith(".chaoxing.com"):
        return ""
    return url

def _normalize_course_state(state_text: str) -> str:
    text = _clean_course_text(state_text, 60)
    if not text:
        return "unknown"
    if any(word in text for word in ("已批阅", "已评分", "已完成")):
        return "graded"
    if any(word in text for word in ("已截止", "已过期", "已结束")):
        return "closed"
    if any(word in text for word in ("已交", "已提交", "已上传", "待批阅")):
        return "submitted"
    if any(word in text for word in ("未交", "未提交", "待做", "待完成", "未开始",
                                     "进行中", "待提交", "未完成")):
        return "open"
    return "unknown"

def _format_course_due(due: date, time_text: str) -> str:
    today = datetime.now().astimezone().date()
    year = f"{due.year}年" if due.year != today.year else ""
    return f"{year}{due.month}月{due.day}日{(' ' + time_text) if time_text else ''}"

def _parse_course_due(value) -> tuple[str | None, str, str]:
    """Return (YYYY-MM-DD, HH:MM, display). Accepts 学习通-style deadline text."""
    raw = _clean_course_text(value, 120)
    if not raw:
        return None, "", ""

    if re.fullmatch(r"\d{10,13}", raw):
        try:
            stamp = int(raw[:10] if len(raw) == 13 else raw)
            moment = datetime.fromtimestamp(stamp).astimezone()
        except (OverflowError, OSError, ValueError):
            return None, "", raw
        return moment.date().isoformat(), moment.strftime("%H:%M"), _format_course_due(
            moment.date(), moment.strftime("%H:%M"))

    if re.search(r"\d{1,2}[:：]\d{2}", raw) or "T" in raw:
        try:
            moment = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            moment = None
        if moment is not None:
            if moment.tzinfo is not None:
                moment = moment.astimezone()
            return moment.date().isoformat(), moment.strftime("%H:%M"), _format_course_due(
                moment.date(), moment.strftime("%H:%M"))

    match = re.search(
        r"(\d{4})\s*[-/年.]\s*(\d{1,2})\s*[-/月.]\s*(\d{1,2})\s*日?\s*"
        r"(?:T?\s*(\d{1,2})[:：](\d{2}))?", raw)
    if match:
        year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
        hour, minute = match.group(4), match.group(5)
    else:
        match = re.search(
            r"(?<!\d)(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]?\s*"
            r"(?:T?\s*(\d{1,2})[:：](\d{2}))?", raw)
        if not match:
            return None, "", raw
        month, day = int(match.group(1)), int(match.group(2))
        hour, minute = match.group(3), match.group(4)
        today = datetime.now().astimezone().date()
        year = today.year
        try:
            candidate = date(year, month, day)
        except ValueError:
            return None, "", raw
        if (today - candidate).days > 30:
            year += 1

    try:
        due = date(year, month, day)
    except ValueError:
        return None, "", raw
    time_text = ""
    if hour is not None and minute is not None:
        h, m = int(hour), int(minute)
        if 0 <= h <= 23 and 0 <= m <= 59:
            time_text = f"{h:02d}:{m:02d}"
    return due.isoformat(), time_text, _format_course_due(due, time_text)

def course_assignment_key(source: str, course_id: str, assignment_id: str) -> str:
    raw = f"{source}|{course_id}|{assignment_id}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()

def _normalize_course_item(item) -> dict | None:
    if not isinstance(item, dict):
        return None
    source = _clean_course_text(item.get("source") or "chaoxing", 30).lower() or "chaoxing"
    if source != "chaoxing":
        return None
    course_name = _clean_course_text(
        item.get("course_name") or item.get("courseName"), 200) or "学习通课程"
    title = _clean_course_text(item.get("title") or item.get("name"), 300)
    if not title:
        return None
    course_id = _clean_course_text(item.get("course_id") or item.get("courseId"), 100)
    if not course_id:
        course_id = hashlib.sha1(course_name.encode("utf-8")).hexdigest()[:16]
    due_date, due_time, due_display = _parse_course_due(
        item.get("due_at") or item.get("due") or item.get("deadline") or item.get("due_text"))
    assignment_id = _clean_course_text(
        item.get("assignment_id") or item.get("assignmentId") or item.get("id"), 200)
    if not assignment_id:
        raw = f"{course_name}|{title}|{due_date or ''}|{due_time}"
        assignment_id = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]
    state_text = _clean_course_text(
        item.get("state_text") or item.get("status_text") or item.get("status"), 60)
    return {
        "source": source,
        "course_id": course_id,
        "course_name": course_name,
        "assignment_id": assignment_id,
        "title": title,
        "due_date": due_date,
        "due_time": due_time,
        "due_display": due_display,
        "state": _normalize_course_state(state_text),
        "state_text": state_text,
        "detail_url": safe_chaoxing_url(item.get("url") or item.get("detail_url")),
    }

def upsert_course_assignments(items) -> dict:
    """Insert/update assignment metadata; user review decisions stay sticky."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    summary = {"inserted": 0, "updated": 0, "skipped": 0, "total": 0}
    with connect() as c:
        for item in items if isinstance(items, list) else []:
            normalized = _normalize_course_item(item)
            if normalized is None:
                summary["skipped"] += 1
                continue
            summary["total"] += 1
            key = course_assignment_key(
                normalized["source"], normalized["course_id"], normalized["assignment_id"])
            existing = c.execute(
                "SELECT status FROM course_assignments WHERE assignment_key=?", (key,)).fetchone()
            imported_status = "done" if normalized["state"] in {"submitted", "graded"} else "pending_review"
            if existing is None:
                c.execute("""INSERT INTO course_assignments
                  (assignment_key,source,course_id,course_name,assignment_id,title,
                   due_date,due_time,due_display,state,state_text,detail_url,status,
                   first_seen_at,updated_at)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                    key, normalized["source"], normalized["course_id"], normalized["course_name"],
                    normalized["assignment_id"], normalized["title"], normalized["due_date"],
                    normalized["due_time"], normalized["due_display"], normalized["state"],
                    normalized["state_text"], normalized["detail_url"], imported_status, now, now))
                summary["inserted"] += 1
            else:
                status = existing["status"]
                if imported_status == "done" and status in {"pending_review", "confirmed"}:
                    status = "done"
                c.execute("""UPDATE course_assignments SET
                  course_name=?,title=?,due_date=?,due_time=?,due_display=?,state=?,
                  state_text=?,detail_url=?,status=?,updated_at=?
                  WHERE assignment_key=?""", (
                    normalized["course_name"], normalized["title"], normalized["due_date"],
                    normalized["due_time"], normalized["due_display"], normalized["state"],
                    normalized["state_text"], normalized["detail_url"], status, now, key))
                summary["updated"] += 1
    return summary

def list_course_assignments(limit=500, include_dismissed=False):
    where = "" if include_dismissed else "WHERE status != 'dismissed'"
    with connect() as c:
        return c.execute(f"""SELECT * FROM course_assignments {where}
          ORDER BY CASE status WHEN 'pending_review' THEN 0 WHEN 'confirmed' THEN 1
                   WHEN 'done' THEN 2 ELSE 3 END,
          CASE state WHEN 'open' THEN 0 WHEN 'unknown' THEN 1 WHEN 'submitted' THEN 2
                     WHEN 'graded' THEN 3 ELSE 4 END,
          due_date IS NULL, due_date, due_time, updated_at DESC LIMIT ?""", (limit,)).fetchall()

def get_course_assignment(assignment_key: str):
    with connect() as c:
        return c.execute("SELECT * FROM course_assignments WHERE assignment_key=?",
                         (assignment_key,)).fetchone()

def review_course_assignment(assignment_key: str, decision: str) -> bool:
    if decision not in COURSE_DECISIONS:
        raise ValueError("invalid decision")
    with connect() as c:
        cur = c.execute("""UPDATE course_assignments SET status=?,reviewed_at=?
          WHERE assignment_key=? AND status IN ('pending_review','confirmed')""",
                        (decision, datetime.now(timezone.utc).isoformat(timespec="seconds"),
                         assignment_key))
        return cur.rowcount > 0

def clear_all_data():
    with connect() as c:
        c.execute("DELETE FROM todos")
        c.execute("DELETE FROM messages")
        c.execute("DELETE FROM course_assignments")
    # Best-effort cleanup of SQLite freelist/WAL. This is not a forensic-grade
    # wipe and cannot override SSD wear-levelling, snapshots, or external backups.
    c = sqlite3.connect(DB_PATH, timeout=10)
    try:
        c.execute("PRAGMA secure_delete=ON")
        c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        c.execute("VACUUM")
        c.commit()
    finally:
        c.close()

def counts() -> dict:
    with connect() as c:
        return {row[0]: row[1] for row in c.execute("SELECT status, COUNT(*) FROM todos GROUP BY status").fetchall()}
