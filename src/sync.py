from __future__ import annotations
from datetime import datetime
from .classifier import message_context
from .store import build_message_key, insert_event, message_exists

DEFAULT_LIMIT_CONTACTS = 50
DEFAULT_PER_CONTACT = 30
DEFAULT_MAX_TOTAL = 300

def today_start_ts(now: datetime | None = None) -> int:
    current = now or datetime.now()
    return int(current.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())

def needs_model_analysis(analysis: dict | None) -> bool:
    return bool(analysis and (analysis.get("task_candidate") or analysis.get("needs_reply")))

def sync_today(client, classify, prefilter=None, now: datetime | None = None,
               limit_contacts: int = DEFAULT_LIMIT_CONTACTS, per_contact: int = DEFAULT_PER_CONTACT,
               max_total: int = DEFAULT_MAX_TOTAL, include_groups: bool = True,
               progress=None, should_stop=None) -> dict:
    start_ts = today_start_ts(now)
    contacts = [contact for contact in client.get_recent_contacts(limit_contacts)
                if (include_groups or contact.get("kind") != "group")
                and int(contact.get("message_time") or 0) >= start_ts]
    summary = {"contacts": 0, "messages": 0, "inserted": 0, "duplicates": 0, "failed": 0,
               "pending": 0, "model_calls": 0, "errors": []}
    processed = 0
    for index, contact in enumerate(contacts, 1):
        if should_stop and should_stop():
            break
        summary["contacts"] += 1
        label = contact.get("name") or contact.get("id")
        if progress:
            progress(f"正在同步 {label}（{index}/{len(contacts)}）…")
        try:
            if contact.get("kind") == "private":
                items = client.fetch_friend_history(contact["id"], per_contact)
            else:
                items = client.fetch_group_history(contact["id"], per_contact)
        except Exception as exc:
            summary["failed"] += 1
            summary["errors"].append(f"{label}: {str(exc)[:100]}")
            continue
        for item in items:
            if should_stop and should_stop():
                break
            event = item.get("event") or {}
            try:
                message_time = int(float(event.get("time") or 0))
            except (TypeError, ValueError):
                message_time = 0
            if message_time < start_ts:
                continue
            if message_exists(build_message_key(event)):
                summary["duplicates"] += 1
                continue
            if processed >= max_total:
                break
            processed += 1
            summary["messages"] += 1
            try:
                context = message_context(event)
                rules = prefilter(item["text"], context=context) if prefilter else None
                if rules is not None and not needs_model_analysis(rules):
                    analysis = rules
                else:
                    analysis = classify(item["text"], context=context)
                    summary["model_calls"] += 1
                if insert_event(event, item["text"], analysis):
                    summary["inserted"] += 1
                    if analysis.get("task_candidate"):
                        summary["pending"] += 1
                else:
                    summary["duplicates"] += 1
            except Exception as exc:
                summary["failed"] += 1
                summary["errors"].append(f"{label}: {str(exc)[:100]}")
                continue
            if progress and summary["messages"] % 5 == 0:
                progress(f"已分析 {summary['messages']} 条今日消息…")
        if processed >= max_total:
            break
    return summary
