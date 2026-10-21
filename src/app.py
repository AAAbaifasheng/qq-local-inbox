from __future__ import annotations
import json
import os
import queue
import secrets
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
from datetime import date, datetime
from pathlib import Path
from tkinter import ttk, messagebox
from urllib.parse import urlparse
from .classifier import classify_message, message_context
from .api_classifier import classify_with_api, validate_api_endpoint
from .api_config import API_PRESETS, API_PRESET_MODELS
from .api_probe import probe_endpoint
from .chaoxing_bridge import DEFAULT_PORT as CHAOXING_DEFAULT_PORT, ChaoxingBridge
from .chaoxing_dialog import ChaoxingAccessDialog
from .config import HISTORY_API_DEFAULT, LOCAL_API_DEFAULT, data_dir, load_settings, save_settings
from .localnet import is_remote_url
from .login_dialog import NapCatLoginDialog
from .napcat_api import NapCatClient
from .napcat_launcher import (find_napcat_root, is_port_ready, read_webui_port,
                              read_webui_token, start_napcat, wait_port)
from .napcat_webui import NapCatWebUI, NapCatWebUIError
from .onebot import OneBotListener, validate_local_ws_url
from .secret_store import (SECRET_API_KEY, SECRET_CHAOXING_TOKEN, SECRET_HTTP_TOKEN,
                           SECRET_NAPCAT_WEBUI_TOKEN, SECRET_WS_TOKEN, clear_all_secrets,
                           load_secret, save_secret)
from .settings_drawer import SettingsDrawer
from .store import (init_db, insert_event, list_messages, list_todos, list_contacts,
                    list_competition_items, list_course_assignments, get_course_assignment,
                    review_course_assignment, review_todo, clear_all_data, safe_chaoxing_url)
from .sync import needs_model_analysis, sync_today
from .timeparse import format_due_display
from .dashboard import DashboardFrame
from .import_dialog import HistoryImportDialog
from .update_service import UpdateService
from .updater import UpdateError, apply_exe_pending, apply_pending
from .version import __version__
from .theme import (AMBER_SOFT, BG, BLUE, BLUE_HOVER, BLUE_SOFT, BORDER, CARD,
                    DANGER, RADIUS_LG, RED_SOFT, SELECT_BG, SELECT_FG, SUCCESS,
                    TEXT, TEXT_2, TEXT_3, WARNING, NavBar, RoundedBar,
                    RoundedButton, RoundedFrame, RoundedLabel, ToggleChip,
                    configure_styles, ui_font)

PAGE_BG = BG

def _configure_styles(root):
    configure_styles(root)

class InboxApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"QQ Local Inbox · 本地事务分拣器 · v{__version__}")
        self.root.geometry("1240x860")
        self.root.minsize(1024, 680)
        self.root.configure(bg=PAGE_BG)
        init_db()
        self.settings = load_settings()
        self.listener = None
        self.import_window = None
        self.chaoxing_window = None
        self.api_key_memory = load_secret(SECRET_API_KEY)
        self.token_memory = load_secret(SECRET_WS_TOKEN)
        self.http_token_memory = load_secret(SECRET_HTTP_TOKEN)
        self.sync_running = False
        self.auto_sync_attempted = False
        self.closing = False
        self.events = queue.Queue()
        self.bridge_token = load_secret(SECRET_CHAOXING_TOKEN) or self._new_bridge_token()
        self.bridge = ChaoxingBridge(
            self.bridge_token, self._on_chaoxing_import,
            preferred_port=int(self.settings.get("chaoxing_port", CHAOXING_DEFAULT_PORT)))
        self.bridge.start()
        if self.bridge.running and self.settings.get("chaoxing_port") != self.bridge.port:
            self.settings["chaoxing_port"] = self.bridge.port
            save_settings(self.settings)
        self.status = tk.StringVar(value="未连接 · 本地规则分类 · 不调用模型")
        self.url_var = tk.StringVar(value=self.settings.get("ws_url", "ws://127.0.0.1:3001"))
        self.token_var = tk.StringVar(value=self.token_memory)
        self.group_var = tk.BooleanVar(value=bool(self.settings.get("include_group_messages", False)))
        self.mode_var = tk.StringVar(value=self.settings.get("analysis_mode", "rules"))
        self.api_endpoint_var = tk.StringVar(value=self.settings.get("api_endpoint", LOCAL_API_DEFAULT))
        self.api_model_var = tk.StringVar(value=self.settings.get("api_model", ""))
        self.api_key_var = tk.StringVar(value="")
        self.api_preset_var = tk.StringVar(value=self._preset_name(self.api_endpoint_var.get()))
        self.remote_consent_var = tk.BooleanVar(value=bool(self.settings.get("allow_remote_api", False)))
        self.auto_connect_var = tk.BooleanVar(value=bool(self.settings.get("auto_connect", True)))
        self.auto_sync_var = tk.BooleanVar(value=bool(self.settings.get("auto_sync_today", True)))
        self.auto_check_updates_var = tk.BooleanVar(
            value=bool(self.settings.get("auto_check_updates", True)))
        self.auto_download_updates_var = tk.BooleanVar(
            value=bool(self.settings.get("auto_download_updates", True)))
        self.auto_apply_updates_var = tk.BooleanVar(
            value=bool(self.settings.get("auto_apply_updates", True)))
        self.napcat_root_var = tk.StringVar(value=self.settings.get("napcat_root", ""))
        self.napcat_webui_url_var = tk.StringVar(
            value=self.settings.get("napcat_webui_url", "http://127.0.0.1:6099"))
        self.auto_launch_napcat_var = tk.BooleanVar(
            value=bool(self.settings.get("auto_launch_napcat", True)))
        self.auto_quick_login_var = tk.BooleanVar(
            value=bool(self.settings.get("auto_quick_login", True)))
        self.napcat_webui_token_memory = load_secret(SECRET_NAPCAT_WEBUI_TOKEN)
        self.napcat_webui_token_var = tk.StringVar(value="")
        self.login_window = None
        self.napcat_login_running = False
        self._selection_vars = {}
        self._detail_buttons = {}
        self._build()
        self.update_service = UpdateService(__version__, data_dir() / "updates", self.events)
        self.status.trace_add("write", lambda *_args: self._sync_status_visual())
        self._toggle_api_fields()
        self._sync_status_visual()
        self.refresh_all()
        self._set_window_icon()
        self.root.bind("<Escape>", lambda _event: self.drawer.close())
        self.root.after(250, self._drain_events)
        self.root.after(800, self._auto_connect)
        self.root.after(3000, self._auto_check_updates)
        self.root.after(120000, self._periodic_refresh)
        self.root.after(6 * 60 * 60 * 1000, self._periodic_update_check)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    @staticmethod
    def _preset_name(endpoint: str) -> str:
        if "deepseek.com" in endpoint:
            return "DeepSeek"
        if "11434" in endpoint:
            return "Ollama"
        if ":1234" in endpoint:
            return "LM Studio"
        return "自定义"

    def _build(self):
        self._build_header()
        self._build_nav()
        self._build_footer()
        self.body = tk.Frame(self.root, bg=BG)
        self.body.pack(fill="both", expand=True)
        self.content_holder = tk.Frame(self.body, bg=BG)
        self.content_holder.pack(fill="both", expand=True, padx=20, pady=(16, 12))
        self._build_pages()
        self.drawer = SettingsDrawer(self.root, self)

    def _build_header(self):
        bar = tk.Frame(self.root, bg=CARD, height=68)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        left = tk.Frame(bar, bg=CARD)
        left.pack(side="left", padx=(20, 0), pady=10)
        self._logo_img = self._load_logo()
        if self._logo_img is not None:
            tk.Label(left, image=self._logo_img, bg=CARD).pack(side="left", padx=(0, 10))
        brand = tk.Frame(left, bg=CARD)
        brand.pack(side="left")
        tk.Label(brand, text="QQ Local Inbox", font=ui_font(15, "bold"),
                 bg=CARD, fg=TEXT).pack(anchor="w")
        tk.Label(brand, text="本地事务分拣器 · 隐私优先", font=ui_font(8),
                 bg=CARD, fg=TEXT_3).pack(anchor="w")

        right = tk.Frame(bar, bg=CARD)
        right.pack(side="right", padx=(0, 20), pady=10)

        self.conn_var = tk.StringVar(value="未连接")
        self.conn_pill = RoundedLabel(right, textvariable=self.conn_var, fill=BG,
                                      fg=TEXT_2, dot_color=TEXT_3, padx=10, pady=5,
                                      bg=CARD)
        self.conn_pill.pack(side="left", padx=(0, 14))

        self.settings_toggle_btn = RoundedButton(right, text="设置", kind="ghost",
                                                 command=self._toggle_settings_panel)
        self.settings_toggle_btn.pack(side="right", padx=(8, 0))
        self.stop_btn = RoundedButton(right, text="停止监听", kind="ghost",
                                      state="disabled", command=self.stop_listener)
        self.stop_btn.pack(side="right", padx=(8, 0))
        self.start_btn = RoundedButton(right, text="开始监听", kind="pink",
                                       command=self.start_listener)
        self.start_btn.pack(side="right", padx=(8, 0))
        self.sync_btn = RoundedButton(right, text="同步今天", kind="soft",
                                      command=self.start_today_sync)
        self.sync_btn.pack(side="right", padx=(8, 0))
        self.stop_btn.pack_forget()

    def _build_nav(self):
        self.nav = NavBar(self.root)
        self.nav.pack(fill="x")

    def _build_footer(self):
        footer = tk.Frame(self.root, bg=CARD)
        footer.pack(side="bottom", fill="x")
        tk.Frame(footer, bg=BORDER, height=1).pack(side="top", fill="x")
        inner = tk.Frame(footer, bg=CARD)
        inner.pack(fill="x", padx=20, pady=(8, 9))

        left = tk.Frame(inner, bg=CARD)
        left.pack(side="left", fill="x", expand=True)
        status_row = tk.Frame(left, bg=CARD)
        status_row.pack(fill="x")
        self.status_dot = tk.Label(status_row, text="●", font=ui_font(8), bg=CARD, fg=TEXT_3)
        self.status_dot.pack(side="left", padx=(0, 6))
        self.status_label = ttk.Label(status_row, textvariable=self.status,
                                      style="CardMuted.TLabel", justify="left",
                                      wraplength=900)
        self.status_label.pack(side="left", fill="x", expand=True)

        privacy_row = tk.Frame(left, bg=CARD)
        privacy_row.pack(fill="x", pady=(3, 0))
        tk.Label(privacy_row, text="消息仅存本机 SQLite · 凭据经 DPAPI 加密 · 远程调用需确认",
                 font=ui_font(8), bg=CARD, fg=TEXT_3).pack(side="left")
        privacy_link = tk.Label(privacy_row, text="隐私说明", font=ui_font(8, "bold"),
                                bg=CARD, fg=BLUE_HOVER, cursor="hand2")
        privacy_link.pack(side="left", padx=(8, 0))
        privacy_link.bind("<Button-1>", lambda _event: self._show_privacy())
        footer.bind("<Configure>", lambda event: self.status_label.configure(
            wraplength=max(320, event.width - 60)))

    def _build_pages(self):
        self.dashboard = DashboardFrame(self.content_holder, on_detail=self.show_dashboard_detail,
                                        on_confirm=self.dashboard_confirm,
                                        on_dismiss=self.dashboard_dismiss,
                                        on_complete=self.dashboard_complete)
        self.nav.add_page("dashboard", "事务中心", self.dashboard)

        self.competition_tab, competition_card = self._make_page(
            "比赛/竞赛", "比赛与竞赛相关信息集中展示，待确认 / 已确认 / 已完成")
        competition_body = self._card_body(competition_card)
        competition_buttons = tk.Frame(competition_body, bg=CARD)
        competition_buttons.pack(fill="x", pady=(0, 12))
        self.competition_detail_btn = RoundedButton(
            competition_buttons, text="查看完整信息", kind="ghost",
            command=self.competition_detail, state="disabled")
        self.competition_confirm_btn = RoundedButton(
            competition_buttons, text="确认加入待办", kind="primary",
            command=self.competition_confirm, state="disabled")
        self.competition_dismiss_btn = RoundedButton(
            competition_buttons, text="忽略此候选", kind="danger",
            command=self.competition_dismiss, state="disabled")
        self.competition_complete_btn = RoundedButton(
            competition_buttons, text="标记完成", kind="primary",
            command=self.competition_complete, state="disabled")
        for button in (self.competition_detail_btn, self.competition_confirm_btn,
                       self.competition_dismiss_btn, self.competition_complete_btn):
            button.pack(side="left", padx=(0, 8))
        self._create_tree(competition_body, "competition",
                          ("id", "priority", "status", "contact", "category", "due", "title"),
                          ("编号", "优先级", "状态", "联系人/群", "分类", "截止/提示", "比赛/竞赛事项"),
                          (45, 55, 60, 190, 155, 180, 330), empty_text="暂无比赛/竞赛事项")
        self.competition_tree.tag_configure("P0", foreground=DANGER)
        self.competition_tree.tag_configure("P1", foreground=WARNING)
        self.competition_tree.tag_configure("pending", background=AMBER_SOFT)
        self.competition_tree.tag_configure("overdue", background=RED_SOFT)
        self.competition_tree.bind("<Double-1>", lambda _event: self.competition_detail())
        self.competition_tree.bind("<<TreeviewSelect>>", self._competition_on_select)
        self._detail_buttons["competition"] = self.competition_detail_btn
        self.competition_selected = None
        self.nav.add_page("competition", "比赛/竞赛", self.competition_tab)

        self.course_tab, course_card = self._make_page(
            "课程作业", "从学习通网页只读同步；确认后才进入待办")
        course_body = self._card_body(course_card)
        course_buttons = tk.Frame(course_body, bg=CARD)
        course_buttons.pack(fill="x", pady=(0, 12))
        self.course_access_btn = RoundedButton(
            course_buttons, text="接入说明", kind="ghost",
            command=self.open_chaoxing_dialog)
        self.course_open_btn = RoundedButton(
            course_buttons, text="打开作业页", kind="ghost",
            command=self.course_open, state="disabled")
        self.course_detail_btn = RoundedButton(
            course_buttons, text="查看完整信息", kind="ghost",
            command=self.course_detail, state="disabled")
        self.course_confirm_btn = RoundedButton(
            course_buttons, text="确认加入待办", kind="primary",
            command=self.course_confirm, state="disabled")
        self.course_dismiss_btn = RoundedButton(
            course_buttons, text="忽略", kind="danger",
            command=self.course_dismiss, state="disabled")
        self.course_complete_btn = RoundedButton(
            course_buttons, text="标记完成", kind="primary",
            command=self.course_complete, state="disabled")
        for button in (self.course_access_btn, self.course_open_btn,
                       self.course_detail_btn, self.course_confirm_btn,
                       self.course_dismiss_btn, self.course_complete_btn):
            button.pack(side="left", padx=(0, 8))
        self._create_tree(course_body, "course",
                          ("course", "title", "due", "platform", "todo", "updated"),
                          ("课程", "作业", "截止", "平台状态", "待办状态", "最近同步"),
                          (180, 330, 190, 100, 90, 150),
                          empty_text="暂无课程作业；点“接入说明”连接学习通")
        self.course_tree.tag_configure("pending", background=AMBER_SOFT)
        self.course_tree.tag_configure("overdue", background=RED_SOFT)
        self.course_tree.bind("<Double-1>", lambda _event: self.course_detail())
        self.course_tree.bind("<<TreeviewSelect>>", self._course_on_select)
        self._detail_buttons["course"] = self.course_detail_btn
        self.course_selected = None
        self.nav.add_page("course", "课程作业", self.course_tab)

        self.msg_tab, msg_card = self._make_page("最近消息", "本地保存的最近 500 条文本，按接收时间倒序")
        msg_body = self._card_body(msg_card)
        msg_buttons = tk.Frame(msg_body, bg=CARD)
        msg_buttons.pack(fill="x", pady=(0, 10))
        self.messages_detail_btn = RoundedButton(
            msg_buttons, text="查看完整信息", kind="ghost", state="disabled",
            command=lambda: self.show_selected("messages"))
        self.messages_detail_btn.pack(side="left")
        self.messages_hint = tk.Label(msg_buttons, text="单击选中，双击也可打开完整信息",
                                      font=ui_font(8), bg=CARD, fg=TEXT_3)
        self.messages_hint.pack(side="right")
        self._create_tree(msg_body, "messages",
                          ("time", "contact", "kind", "priority", "text"),
                          ("时间", "联系人/群", "分类", "优先级", "消息摘要"),
                          (145, 180, 140, 60, 450), empty_text="暂无本地消息")
        self._detail_buttons["messages"] = self.messages_detail_btn
        self.nav.add_page("messages", "最近消息", self.msg_tab)

        self.review_tab, review_card = self._make_page("待审核事务", "候选事项经你确认后才进入待办")
        review_body = self._card_body(review_card)
        review_buttons = tk.Frame(review_body, bg=CARD)
        review_buttons.pack(fill="x", pady=(0, 12))
        self.review_detail_btn = RoundedButton(
            review_buttons, text="查看完整信息", kind="ghost", state="disabled",
            command=lambda: self.show_selected("review"))
        self.review_detail_btn.pack(side="left", padx=(0, 8))
        self.review_confirm_btn = RoundedButton(
            review_buttons, text="确认加入待办", kind="primary", state="disabled",
            command=self.confirm_selected)
        self.review_confirm_btn.pack(side="left", padx=(0, 8))
        self.review_dismiss_btn = RoundedButton(
            review_buttons, text="忽略此候选", kind="danger", state="disabled",
            command=self.dismiss_selected)
        self.review_dismiss_btn.pack(side="left")
        self._create_tree(review_body, "review",
                          ("id", "priority", "importance", "contact", "category", "due", "title"),
                          ("编号", "优先级", "分数", "联系人", "分类", "截止/提示", "候选事项（需人工确认）"),
                          (45, 55, 50, 180, 150, 185, 320), empty_text="暂无待审核候选")
        self.review_tree.bind("<<TreeviewSelect>>", lambda _event: self._update_page_buttons())
        self.review_tree.bind("<Double-1>", lambda _event: self.show_selected("review"))
        self._detail_buttons["review"] = self.review_detail_btn
        self.nav.add_page("review", "待审核事务", self.review_tab)

        self.todo_tab, todo_card = self._make_page("已确认待办", "已经确认、等待处理或完成的事务")
        todo_body = self._card_body(todo_card)
        todo_buttons = tk.Frame(todo_body, bg=CARD)
        todo_buttons.pack(fill="x", pady=(0, 12))
        self.todo_detail_btn = RoundedButton(
            todo_buttons, text="查看完整信息", kind="ghost", state="disabled",
            command=lambda: self.show_selected("todos"))
        self.todo_detail_btn.pack(side="left", padx=(0, 8))
        self.todo_complete_btn = RoundedButton(
            todo_buttons, text="标记完成", kind="primary", state="disabled",
            command=self.complete_selected)
        self.todo_complete_btn.pack(side="left")
        self._create_tree(todo_body, "todos",
                          ("id", "priority", "importance", "contact", "category", "due", "title"),
                          ("编号", "优先级", "分数", "联系人", "分类", "截止/提示", "已确认待办"),
                          (45, 55, 50, 180, 150, 185, 320), empty_text="暂无已确认待办")
        self.todos_tree.bind("<<TreeviewSelect>>", lambda _event: self._update_page_buttons())
        self.todos_tree.bind("<Double-1>", lambda _event: self.show_selected("todos"))
        self._detail_buttons["todos"] = self.todo_detail_btn
        self.nav.add_page("todos", "已确认待办", self.todo_tab)

        self.contact_tab, contact_card = self._make_page(
            "联系人排序", "按待处理工作量排序，不对联系人个人价值作评价")
        contact_body = self._card_body(contact_card)
        contact_buttons = tk.Frame(contact_body, bg=CARD)
        contact_buttons.pack(fill="x", pady=(0, 10))
        self.contacts_detail_btn = RoundedButton(
            contact_buttons, text="查看完整信息", kind="ghost", state="disabled",
            command=lambda: self.show_selected("contacts"))
        self.contacts_detail_btn.pack(side="left")
        self._create_tree(contact_body, "contacts",
                          ("contact", "messages", "today", "pending", "confirmed", "reply",
                           "max_priority", "max_score", "last_message", "rank_score"),
                          ("联系人/群", "消息数", "今日", "待审核", "已确认", "待回复",
                           "最高优先级", "最高分", "最近消息", "排序分"),
                          (200, 65, 55, 72, 72, 65, 88, 62, 140, 62),
                          empty_text="暂无联系人数据")
        self._detail_buttons["contacts"] = self.contacts_detail_btn
        self.nav.add_page("contacts", "联系人排序", self.contact_tab)

    def _make_page(self, title, subtitle):
        page = tk.Frame(self.content_holder, bg=BG)
        head = tk.Frame(page, bg=BG)
        head.pack(fill="x", pady=(0, 14))
        tk.Label(head, text=title, font=ui_font(18, "bold"),
                 bg=BG, fg=TEXT).pack(side="left")
        tk.Label(head, text=subtitle, font=ui_font(9), bg=BG,
                 fg=TEXT_3).pack(side="left", padx=(12, 0), pady=(7, 0))
        card = RoundedFrame(page, radius=RADIUS_LG, fill=CARD,
                            outline=BORDER, bg=BG)
        card.pack(fill="both", expand=True)
        return page, card

    @staticmethod
    def _card_body(card):
        parent = getattr(card, "content", card)
        body = tk.Frame(parent, bg=CARD)
        body.pack(fill="both", expand=True, padx=18, pady=14)
        return body

    @staticmethod
    def _asset_path(name: str) -> Path:
        path = Path(__file__).resolve().parent.parent / "assets" / name
        if path.exists():
            return path
        bundled = getattr(sys, "_MEIPASS", None)
        if bundled:
            candidate = Path(bundled) / "assets" / name
            if candidate.exists():
                return candidate
        return path

    def _load_logo(self):
        path = self._asset_path("icon.png")
        try:
            image = tk.PhotoImage(file=str(path))
        except (tk.TclError, OSError):
            return None
        factor = max(1, image.width() // 34)
        if factor > 1:
            image = image.subsample(factor, factor)
        return image

    def _toggle_settings_panel(self):
        self.drawer.toggle()

    def show_privacy(self):
        self._show_privacy()

    def _sync_status_visual(self):
        text = self.status.get()
        color = label = None
        if "已停止监听" in text or "自动连接未启动" in text or "未连接" in text:
            color, label = TEXT_3, "未连接"
        elif "已连接" in text:
            color, label = SUCCESS, "已连接"
        elif any(token in text for token in
                 ("连接异常", "连接错误", "断开", "重连", "正在连接")):
            color, label = WARNING, "连接中"
        if color is None:
            return
        self.conn_pill.set_dot_color(color)
        self.conn_var.set(label)
        self.status_dot.configure(fg=color)
        if hasattr(self, "drawer"):
            self.drawer.conn_badge.set_dot_color(color)

    def _show_privacy(self):
        window = tk.Toplevel(self.root)
        window.title("隐私说明")
        window.geometry("660x440")
        window.configure(bg=CARD)
        window.transient(self.root)
        accent_row = tk.Frame(window, bg=CARD)
        accent_row.pack(fill="x", pady=(10, 0))
        RoundedBar(accent_row, width=44, height=4, fill=BLUE, bg=CARD).pack(anchor="center")
        head = tk.Frame(window, bg=CARD)
        head.pack(fill="x", padx=22, pady=(12, 8))
        tk.Label(head, text="隐私说明", font=ui_font(16, "bold"),
                 bg=CARD, fg=TEXT).pack(anchor="w")
        tk.Label(head, text="本地优先 · 最小外发 · 可随时清除", font=ui_font(9),
                 bg=CARD, fg=TEXT_3).pack(anchor="w", pady=(4, 0))
        detail = (
            "QQ 接入仅限本机 WebSocket；历史导入只访问本机 NapCat HTTP；默认只调用本机模型。\n\n"
            "学习通接入为可选的只读油猴桥：只读取课程名、作业标题、截止时间、平台状态和链接，"
            "通过 127.0.0.1 回环服务写入本机；不保存学习通账号密码或 Cookie，不自动提交。\n\n"
            "勾选远程 API 并确认后，消息文本会发送给所配置服务商；不勾选则不会外发。\n\n"
            "API Key、NapCat Token 与学习通接入令牌使用 Windows DPAPI 加密保存在本机，可在底部清除；"
            "远程知情确认也会一并取消。\n\n"
            "消息、待办与课程作业只保存在本机 SQLite，不会上传。清空本地数据会永久删除这些记录。\n\n"
            "更新检查只访问 GitHub Releases，不上传聊天记录、Token 或 API Key；"
            "更新包会校验 SHA256，并在替换前备份旧版本。\n\n"
            f"本地数据目录：{data_dir()}"
        )
        tk.Label(window, text=detail, justify="left", anchor="nw", wraplength=600,
                 font=ui_font(10), bg=CARD, fg=TEXT_2).pack(
            fill="both", expand=True, padx=22, pady=(6, 8))
        RoundedButton(window, text="关闭", kind="primary", command=window.destroy).pack(
            anchor="e", padx=22, pady=(0, 18))
        window.bind("<Escape>", lambda _event: window.destroy())

    def _create_tree(self, parent, name, keys, headers, widths, empty_text="暂无记录"):
        selection_var = tk.StringVar(value="未选择记录 · 单击一行查看操作")
        self._selection_vars[name] = selection_var
        bar = tk.Frame(parent, bg=SELECT_BG)
        bar.pack(fill="x", pady=(0, 6))
        tk.Label(bar, textvariable=selection_var, font=ui_font(9, "bold"), bg=SELECT_BG,
                 fg=SELECT_FG, anchor="w", padx=10, pady=6).pack(fill="x")

        holder = tk.Frame(parent, bg=CARD)
        holder.pack(fill="both", expand=True)
        tree = ttk.Treeview(holder, columns=keys, show="headings", selectmode="browse")
        for key, header, width in zip(keys, headers, widths):
            tree.heading(key, text=header)
            tree.column(key, width=width, minwidth=45,
                        stretch=(key in {"text", "title", "contact"}))
        yscroll = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
        xscroll = ttk.Scrollbar(holder, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        holder.rowconfigure(0, weight=1)
        holder.columnconfigure(0, weight=1)
        setattr(self, f"{name}_tree", tree)
        empty = tk.Label(holder, text=empty_text, font=ui_font(10), bg=CARD, fg=TEXT_3)
        setattr(self, f"{name}_empty", empty)
        tree.bind("<<TreeviewSelect>>",
                  lambda _event, tree_name=name: self._update_tree_selection(tree_name),
                  add="+")
        if name in ("messages", "contacts"):
            tree.bind("<Double-1>", lambda _event, tree_name=name: self.show_selected(tree_name))

    def _toggle_api_fields(self):
        api_mode = self.mode_var.get() == "api"
        if hasattr(self, "drawer"):
            self.drawer.refresh_mode()
        if self.listener is None:
            if api_mode:
                if is_remote_url(self.api_endpoint_var.get()):
                    if self.remote_consent_var.get():
                        self.status.set("远程 API 模式：消息文本会发送给所配置服务商。")
                    else:
                        self.status.set("远程 API 模式：消息文本会发送给所配置服务商；请勾选知情确认。")
                else:
                    self.status.set("本机大模型模式：消息只发送给本机 OpenAI 兼容服务。")
            else:
                self.status.set("本地规则模式：不调用模型，不外发聊天文本。")

    def on_mode_change(self):
        self._toggle_api_fields()

    def apply_api_preset(self):
        preset = self.api_preset_var.get()
        endpoint = API_PRESETS.get(preset)
        if endpoint:
            self.api_endpoint_var.set(endpoint)
            models = API_PRESET_MODELS.get(preset, ())
            if models:
                self.api_model_var.set(models[0])
        self._toggle_api_fields()

    def set_status(self, text):
        self.events.put(("status", text))

    def _persist_settings(self):
        safe_url = validate_local_ws_url(self.url_var.get())
        token = self.token_var.get().strip()
        mode = self.mode_var.get()
        endpoint = self.api_endpoint_var.get().strip()
        model = self.api_model_var.get().strip()
        key_field = self.api_key_var.get().strip()
        api_key = key_field or self.api_key_memory
        allow_remote = self.remote_consent_var.get()
        if mode == "api":
            if not endpoint:
                raise ValueError("请填写 API Endpoint。")
            if is_remote_url(endpoint) and not allow_remote:
                raise ValueError("远程 API 需要先勾选知情确认；消息文本会发送给该服务商。")
            endpoint = validate_api_endpoint(endpoint, allow_remote=allow_remote)
            if is_remote_url(endpoint) and not api_key:
                raise ValueError("远程 API 必须填写 API Key。")
            if not model:
                raise ValueError("大模型 API 模式必须填写模型名称（例如 deepseek-flash 或 qwen3:8b）。")
        self.api_key_memory = api_key
        self.token_memory = token
        save_secret(SECRET_API_KEY, api_key)
        save_secret(SECRET_WS_TOKEN, token)
        webui_token_field = self.napcat_webui_token_var.get().strip()
        if webui_token_field:
            self.napcat_webui_token_memory = webui_token_field
            save_secret(SECRET_NAPCAT_WEBUI_TOKEN, webui_token_field)
            self.napcat_webui_token_var.set("")
        webui_url = self.napcat_webui_url_var.get().strip() or "http://127.0.0.1:6099"
        try:
            webui_url = NapCatWebUI(webui_url).base
        except NapCatWebUIError as exc:
            raise ValueError(str(exc))
        self.settings.update({
            "ws_url": safe_url,
            "include_group_messages": self.group_var.get(),
            "analysis_mode": mode,
            "api_endpoint": endpoint,
            "api_model": model,
            "history_api_url": self.settings.get("history_api_url", HISTORY_API_DEFAULT),
            "auto_connect": self.auto_connect_var.get(),
            "auto_sync_today": self.auto_sync_var.get(),
            "allow_remote_api": allow_remote,
            "chaoxing_port": self.settings.get("chaoxing_port", CHAOXING_DEFAULT_PORT),
            "auto_check_updates": self.auto_check_updates_var.get(),
            "auto_download_updates": self.auto_download_updates_var.get(),
            "auto_apply_updates": self.auto_apply_updates_var.get(),
            "napcat_root": self.napcat_root_var.get().strip(),
            "napcat_webui_url": webui_url,
            "auto_launch_napcat": self.auto_launch_napcat_var.get(),
            "auto_quick_login": self.auto_quick_login_var.get(),
        })
        save_settings(self.settings)
        self.api_endpoint_var.set(self.settings["api_endpoint"])
        if key_field:
            self.api_key_var.set("")
        return safe_url, token

    def save_settings_from_drawer(self):
        try:
            self._persist_settings()
        except Exception as exc:
            messagebox.showerror("无法保存设置", str(exc), parent=self.root)
            return
        self.status.set("设置已保存。")

    def save_and_connect(self):
        self.start_listener()

    def start_listener(self, auto=False):
        try:
            safe_url, token = self._persist_settings()
            listener = OneBotListener(safe_url, token, self.group_var.get(), self._on_event, self.set_status)
            listener.start()
            self.listener = listener
            self.drawer.close()
        except Exception as exc:
            if auto:
                self.drawer.open()
                self.status.set(f"自动连接未启动：{str(exc)[:160]}")
            else:
                messagebox.showerror("无法启动监听", str(exc), parent=self.root)
            return
        self.start_btn.pack_forget()
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.stop_btn.pack(side="right", padx=(8, 0), before=self.sync_btn)
        self.status.set("正在连接…仅接收启用后的新事件；不会自动读取历史消息。")
        if self.auto_sync_var.get() and not self.auto_sync_attempted:
            self.auto_sync_attempted = True
            self.root.after(1200, self.start_today_sync)

    def _auto_connect(self):
        if self.closing or self.listener:
            return
        if not self.auto_connect_var.get():
            return
        if self.auto_launch_napcat_var.get():
            self.start_napcat_and_login(auto=True)
        else:
            self.start_listener(auto=True)

    def _periodic_refresh(self):
        if self.closing:
            return
        try:
            importing = self.import_window is not None and getattr(self.import_window, "running", False)
            if not self.sync_running and not importing:
                self.refresh_all()
        finally:
            self.root.after(120000, self._periodic_refresh)

    def _auto_check_updates(self):
        if self.closing or not self.auto_check_updates_var.get():
            return
        self.update_service.start_check(auto_download=self.auto_download_updates_var.get())

    def _periodic_update_check(self):
        if self.closing:
            return
        try:
            if self.auto_check_updates_var.get():
                self.update_service.start_check(auto_download=self.auto_download_updates_var.get())
        finally:
            self.root.after(6 * 60 * 60 * 1000, self._periodic_update_check)

    def check_updates_manual(self):
        if self.update_service.start_check(auto_download=self.auto_download_updates_var.get()):
            self.drawer.set_update_status("正在检查更新…", TEXT_3)

    def apply_update_now(self):
        staging = data_dir() / "updates"
        if getattr(sys, "frozen", False):
            try:
                result = apply_exe_pending(Path(sys.executable), staging, __version__)
            except UpdateError as exc:
                messagebox.showerror("更新失败", str(exc), parent=self.root)
                return
            if not result.applied:
                messagebox.showinfo("无法应用更新", "没有已下载的可执行更新包。", parent=self.root)
                return
            messagebox.showinfo("更新已应用", "程序将重新启动。", parent=self.root)
            subprocess.Popen([sys.executable, *sys.argv[1:]])
            self.close()
            return
        try:
            result = apply_pending(Path(__file__).resolve().parent.parent, staging, __version__)
        except UpdateError as exc:
            messagebox.showerror("更新失败", str(exc), parent=self.root)
            return
        if not result.applied:
            reason = {
                "git-checkout": "当前是开发目录（含 .git），不会自动覆盖。请手动更新。",
                "no-pending": "没有已下载的更新。",
            }.get(result.reason, result.reason or "未知原因")
            messagebox.showinfo("无法应用更新", reason, parent=self.root)
            return
        messagebox.showinfo("更新已应用", "程序将重新启动。", parent=self.root)
        subprocess.Popen([sys.executable, "-m", "src.main"],
                         cwd=str(Path(__file__).resolve().parent.parent))
        self.close()

    def test_api_connection(self, _populate_models=False):
        endpoint = self.api_endpoint_var.get().strip()
        key = self.api_key_var.get().strip() or self.api_key_memory
        allow_remote = self.remote_consent_var.get()
        self.drawer.set_probe_running()
        threading.Thread(target=self._probe_api_worker,
                         args=(endpoint, key, allow_remote), daemon=True).start()

    def _probe_api_worker(self, endpoint, key, allow_remote):
        result = probe_endpoint(endpoint, key, allow_remote)
        self.events.put(("api_probe_result", result))

    def clear_api_key(self):
        self.api_key_memory = ""
        self.api_key_var.set("")
        save_secret(SECRET_API_KEY, "")
        self.drawer.probe_status.configure(text="已清除保存的 API Key。", fg=TEXT_2)

    def auto_detect_napcat_root(self):
        root = find_napcat_root(self.napcat_root_var.get().strip()
                                or self.settings.get("napcat_root"))
        if root is None:
            messagebox.showinfo("未找到 NapCat",
                                "没有在常见位置找到 NapCatWinBootMain.exe；请手动填写安装目录。",
                                parent=self.root)
            return
        self.napcat_root_var.set(str(root))
        self.status.set(f"已找到 NapCat 安装目录：{root}")

    def auto_read_webui_token(self):
        root = find_napcat_root(self.napcat_root_var.get().strip()
                                or self.settings.get("napcat_root"))
        if root is None:
            self.auto_detect_napcat_root()
            root = find_napcat_root(self.napcat_root_var.get().strip())
        if root is None:
            return
        self.napcat_root_var.set(str(root))
        token = read_webui_token(root)
        if not token:
            messagebox.showinfo("未读取到 Token",
                                "NapCat 配置中没有 WebUI Token；请先启动一次 NapCat 或手动填写。",
                                parent=self.root)
            return
        self.napcat_webui_token_memory = token
        save_secret(SECRET_NAPCAT_WEBUI_TOKEN, token)
        self.napcat_webui_url_var.set(f"http://127.0.0.1:{read_webui_port(root)}")
        self.status.set("已读取本机 NapCat WebUI Token，并用 DPAPI 加密保存。")

    def start_napcat_and_login(self, auto=False):
        if self.napcat_login_running:
            return
        self.napcat_login_running = True
        root_hint = (self.napcat_root_var.get().strip()
                     or self.settings.get("napcat_root", ""))
        webui_url = (self.napcat_webui_url_var.get().strip()
                     or self.settings.get("napcat_webui_url", "http://127.0.0.1:6099"))
        auto_quick = self.auto_quick_login_var.get()
        threading.Thread(target=self._napcat_login_worker,
                         args=(auto, root_hint, webui_url, auto_quick), daemon=True).start()

    def _napcat_login_worker(self, auto, root_hint, webui_url, auto_quick):
        try:
            root = find_napcat_root(root_hint)
            if root is None:
                raise NapCatWebUIError("未找到 NapCat 安装目录；请在设置 → 连接中填写或自动检测。")
            self.events.put(("napcat_root_found", str(root)))
            webui = NapCatWebUI(webui_url)
            port = urlparse(webui.base).port or 6099
            if not is_port_ready("127.0.0.1", port, timeout=0.5):
                self.events.put(("napcat_status", "正在启动 NapCat（无控制台窗口）…"))
                start_napcat(root)
                if not wait_port("127.0.0.1", port, timeout=30):
                    raise NapCatWebUIError("NapCat 启动超时：WebUI 端口未就绪。")
            token = self.napcat_webui_token_memory or read_webui_token(root)
            if not token:
                raise NapCatWebUIError("缺少 NapCat WebUI Token；请点击“读取 WebUI Token”或手动填写。")
            if not self.napcat_webui_token_memory:
                self.napcat_webui_token_memory = token
                save_secret(SECRET_NAPCAT_WEBUI_TOKEN, token)
            webui.login(token)
            if webui.check_status().is_login:
                self.events.put(("napcat_logged_in", None))
                return
            accounts = webui.quick_login_list() if auto_quick else []
            if accounts:
                webui.set_quick_login(accounts[0]["uin"])
                self.events.put(("napcat_status",
                                 f"正在使用已保存账号 {accounts[0]['nick']} 快速登录…"))
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    if webui.check_status().is_login:
                        self.events.put(("napcat_logged_in", None))
                        return
                    time.sleep(1.5)
                raise NapCatWebUIError("快速登录超时；请手动扫码登录。")
            self.events.put(("napcat_login_needed", webui))
        except Exception as exc:
            self.napcat_login_running = False
            if auto:
                self.events.put(("napcat_status", f"NapCat 自动登录未启动：{str(exc)[:160]}"))
                self.events.put(("napcat_fallback_connect", None))
            else:
                self.events.put(("napcat_error", str(exc)[:200]))

    def _on_napcat_logged_in(self):
        self.napcat_login_running = False
        if self.login_window is not None:
            try:
                self.login_window.closed = True
                self.login_window.destroy()
            except tk.TclError:
                pass
            self.login_window = None
        self.status.set("QQ 已登录，正在连接…")
        self.start_listener(auto=True)

    def _open_login_dialog(self, webui):
        self.napcat_login_running = False
        if self.login_window is not None:
            try:
                if self.login_window.winfo_exists():
                    self.login_window.lift()
                    return
            except tk.TclError:
                pass
        self.login_window = NapCatLoginDialog(
            self.root, webui,
            on_logged_in=self._on_napcat_logged_in,
            on_cancel=self._on_login_cancel)

    def _on_login_cancel(self):
        self.login_window = None
        self.status.set("已取消扫码登录；可在设置 → 连接中重新发起。")

    def _set_window_icon(self):
        icon = self._asset_path("icon.ico")
        if icon.exists():
            try:
                self.root.iconbitmap(default=str(icon))
            except tk.TclError:
                pass

    def start_today_sync(self):
        if self.closing or self.sync_running:
            return
        mode = self.mode_var.get()
        endpoint = self.api_endpoint_var.get().strip()
        model = self.api_model_var.get().strip()
        api_key = self.api_key_memory or self.api_key_var.get().strip()
        allow_remote = self.remote_consent_var.get()
        prefilter = classify_message
        if mode == "api":
            try:
                if not endpoint:
                    raise ValueError("请填写 API Endpoint。")
                if is_remote_url(endpoint) and not allow_remote:
                    raise ValueError("远程 API 需要勾选知情确认。")
                endpoint = validate_api_endpoint(endpoint, allow_remote=allow_remote)
                if is_remote_url(endpoint) and not api_key:
                    raise ValueError("远程 API 必须填写 API Key。")
                if not model:
                    raise ValueError("请填写模型名称。")
            except Exception as exc:
                self.status.set(f"今天消息同步未启动：{exc}")
                return
            def classify(text, context=None):
                return classify_with_api(text, endpoint, model, api_key, allow_remote=allow_remote,
                                         context=context)
        else:
            classify = classify_message
            prefilter = None
        base_url = self.settings.get("history_api_url", HISTORY_API_DEFAULT)
        token = self.http_token_memory
        self.sync_running = True
        self.sync_btn.configure(state="disabled")
        self.status.set("正在同步今天消息…")
        threading.Thread(target=self._sync_worker,
                         args=(base_url, token, classify, prefilter, self.group_var.get()),
                         daemon=True).start()

    def _sync_worker(self, base_url, token, classify, prefilter, include_groups):
        try:
            client = NapCatClient(base_url, token)
            summary = sync_today(
                client, classify, prefilter=prefilter, include_groups=include_groups,
                progress=lambda text: self.events.put(("sync_status", text)),
                should_stop=lambda: self.closing,
            )
        except Exception as exc:
            self.events.put(("sync_error", f"今天消息同步失败：{str(exc)[:160]}"))
            return
        self.events.put(("sync_done", summary))

    def stop_listener(self):
        if self.listener:
            self.listener.stop()
            self.listener = None
        self.drawer.open()
        self.stop_btn.pack_forget()
        self.stop_btn.configure(state="disabled")
        self.start_btn.configure(state="normal")
        self.start_btn.pack(side="right", padx=(8, 0), before=self.sync_btn)
        self.status.set("已停止监听")

    def _on_event(self, event, text):
        self.events.put(("message", event, text))

    def _drain_events(self):
        dirty = False
        try:
            while True:
                item = self.events.get_nowait()
                if item[0] == "status":
                    self.status.set(item[1])
                elif item[0] == "message":
                    _, event, text = item
                    mode = self.settings.get("analysis_mode", "rules")
                    context = message_context(event)
                    is_group = bool(context.get("is_group"))
                    rules = classify_message(text, context) if is_group and mode == "api" else None
                    use_api = mode == "api" and (rules is None or needs_model_analysis(rules))
                    if use_api:
                        settings = dict(self.settings)
                        api_key = self.api_key_memory
                        allow_remote = self.remote_consent_var.get()
                        threading.Thread(target=self._classify_api_worker,
                                         args=(event, text, settings, api_key, allow_remote, context),
                                         daemon=True).start()
                    else:
                        analysis = rules or classify_message(text, context)
                        try:
                            if insert_event(event, text, analysis):
                                dirty = True
                        except Exception as exc:
                            self.status.set(f"本地存储错误：{type(exc).__name__}，请检查数据目录权限")
                elif item[0] == "api_result":
                    _, event, text, analysis, error = item
                    if error:
                        analysis = classify_message(text, message_context(event))
                        try:
                            if insert_event(event, text, analysis):
                                dirty = True
                        except Exception as exc:
                            self.status.set(f"本地存储错误：{type(exc).__name__}，请检查数据目录权限")
                        else:
                            self.status.set(f"API 分析失败：{error}；该消息已用本地规则入库。")
                    else:
                        try:
                            if insert_event(event, text, analysis):
                                dirty = True
                        except Exception as exc:
                            self.status.set(f"本地存储错误：{type(exc).__name__}，请检查数据目录权限")
                elif item[0] == "sync_status":
                    self.status.set(item[1])
                elif item[0] == "sync_done":
                    self.sync_running = False
                    self.sync_btn.configure(state="normal")
                    summary = item[1]
                    if summary.get("contacts"):
                        error_hint = ""
                        if summary.get("errors"):
                            error_hint = f"（首个失败：{summary['errors'][0][:120]}）"
                        self.status.set(
                            f"今天同步完成：新增 {summary['inserted']} 条，跳过重复 {summary['duplicates']} 条，"
                            f"失败 {summary['failed']} 条{error_hint}；新增待审核 {summary['pending']} 条；"
                            f"模型分析 {summary['model_calls']} 条。")
                    else:
                        self.status.set("今天没有需要同步的新消息。")
                    dirty = True
                elif item[0] == "sync_error":
                    self.sync_running = False
                    self.sync_btn.configure(state="normal")
                    self.status.set(item[1])
                    dirty = True
                elif item[0] == "chaoxing_import":
                    summary = item[1]
                    self.status.set(
                        f"学习通作业已同步：新增 {summary.get('inserted', 0)}，"
                        f"更新 {summary.get('updated', 0)}，跳过 {summary.get('skipped', 0)}。")
                    dirty = True
                elif item[0] == "update_checking":
                    self.drawer.set_update_status("正在检查更新…", TEXT_3)
                elif item[0] == "update_checked":
                    self.drawer.set_update_checked()
                elif item[0] == "update_available":
                    info = item[1]
                    self.drawer.set_update_info(info, staged=False)
                    if not self.auto_download_updates_var.get():
                        self.status.set(f"发现新版本 v{info.version}；自动下载已关闭。")
                elif item[0] == "update_staged":
                    info = item[1]
                    self.drawer.set_update_info(info, staged=True)
                    self.status.set(f"更新 v{info.version} 已下载，下次启动生效。")
                elif item[0] == "update_error":
                    self.drawer.set_update_error(item[1])
                elif item[0] == "api_probe_result":
                    self.drawer.set_probe_result(item[1])
                elif item[0] == "napcat_status":
                    self.status.set(item[1])
                elif item[0] == "napcat_root_found":
                    self.napcat_root_var.set(item[1])
                elif item[0] == "napcat_error":
                    messagebox.showerror("NapCat 登录失败", item[1], parent=self.root)
                elif item[0] == "napcat_logged_in":
                    self._on_napcat_logged_in()
                elif item[0] == "napcat_login_needed":
                    self._open_login_dialog(item[1])
                elif item[0] == "napcat_fallback_connect":
                    self.start_listener(auto=True)
        except queue.Empty:
            pass
        if dirty:
            self.refresh_all()
        self.root.after(250, self._drain_events)

    def _classify_api_worker(self, event, text, settings, api_key, allow_remote, context=None):
        try:
            analysis = classify_with_api(
                text,
                settings.get("api_endpoint", ""),
                settings.get("api_model", ""),
                api_key,
                allow_remote=allow_remote,
                context=context,
            )
            error = None
        except Exception as exc:
            analysis = None
            error = str(exc)[:180]
        self.events.put(("api_result", event, text, analysis, error))

    def refresh_all(self):
        self.dashboard.refresh()
        for tree_name in ("contacts_tree", "messages_tree", "review_tree", "todos_tree",
                          "competition_tree", "course_tree"):
            tree = getattr(self, tree_name)
            for row_id in tree.get_children():
                tree.delete(row_id)
        for row in list_contacts(500):
            rank = {4: "P0", 3: "P1", 2: "P2", 1: "P3", 0: "—"}.get(int(row["priority_rank"]), "—")
            last_message = (row["last_message_at"] or "").replace("T", " ")[:19] or "—"
            self.contacts_tree.insert("", "end", iid=row["chat_label"], values=(
                row["chat_label"], row["message_count"], row["today_count"], row["pending_count"],
                row["confirmed_count"], row["reply_count"], rank, row["max_importance"],
                last_message, row["rank_score"]))
        for row in list_messages(500):
            analysis = json.loads(row["analysis_json"])
            time_txt = row["timestamp"].replace("T", " ")[:19]
            text = row["text"].replace("\n", " ")
            self.messages_tree.insert("", "end", iid=row["message_key"], values=(
                time_txt, row["chat_label"], "、".join(analysis.get("categories", [])),
                analysis.get("priority", "P3"), text[:300]))
        for status, tree in (("pending_review", self.review_tree), ("confirmed", self.todos_tree)):
            for row in list_todos(status):
                tree.insert("", "end", iid=str(row["id"]), values=(
                    row["id"], row["priority"], row["importance"], row["chat_label"], row["category"],
                    format_due_display(row["due_date"], row["due_display"], row["due_hint"]),
                    row["title"][:300]))
        self.nav.set_text("review", f"待审核事务 {len(self.review_tree.get_children())}")
        self.nav.set_text("todos", f"已确认待办 {len(self.todos_tree.get_children())}")
        self.nav.set_text("messages", f"最近消息 {len(self.messages_tree.get_children())}")
        today = date.today().isoformat()
        for row in list_competition_items(500):
            status = row["status"]
            tags = [row["priority"]]
            if status == "pending_review":
                tags.append("pending")
            due_text = format_due_display(row["due_date"], row["due_display"], row["due_hint"])
            if row["due_date"] and row["due_date"] < today:
                due_text = "逾期 · " + due_text
                tags.append("overdue")
            status_text = {"pending_review": "待确认", "confirmed": "已确认", "done": "已完成"}.get(status, status)
            self.competition_tree.insert("", "end", iid=f"{status}:{row['id']}", tags=tuple(tags), values=(
                row["id"], row["priority"], status_text, row["chat_label"], row["category"],
                due_text, row["title"][:300]))
        for row in list_course_assignments(500):
            status = row["status"]
            tags = []
            if status == "pending_review":
                tags.append("pending")
            due_text = format_due_display(row["due_date"], row["due_display"])
            if (row["due_date"] and row["due_date"] < today
                    and row["state"] in {"open", "unknown"}
                    and status in {"pending_review", "confirmed"}):
                due_text = "逾期 · " + due_text
                tags.append("overdue")
            platform = row["state_text"] or {
                "open": "待交", "submitted": "已交", "graded": "已批阅",
                "closed": "已截止", "unknown": "—"}.get(row["state"], "—")
            todo_text = {"pending_review": "待确认", "confirmed": "已确认",
                         "done": "已完成", "dismissed": "已忽略"}.get(status, status)
            updated = self._local_iso_text(row["updated_at"])
            self.course_tree.insert("", "end", iid=row["assignment_key"], tags=tuple(tags), values=(
                row["course_name"], row["title"][:300], due_text, platform, todo_text, updated))
        for name in ("messages", "review", "todos", "contacts", "competition", "course"):
            tree = getattr(self, f"{name}_tree")
            empty = getattr(self, f"{name}_empty")
            if tree.get_children():
                empty.place_forget()
            else:
                empty.place(relx=0.5, rely=0.5, anchor="center")
        self.competition_selected = None
        self.course_selected = None
        self._update_competition_buttons()
        self._update_course_buttons()
        self._update_page_buttons()
        self.nav.set_text("competition", f"比赛/竞赛 {len(self.competition_tree.get_children())}")
        self.nav.set_text("course", f"课程作业 {len(self.course_tree.get_children())}")

    def _selected_row(self, tree_name):
        tree = getattr(self, f"{tree_name}_tree")
        selected = tree.selection()
        if not selected:
            messagebox.showinfo("请选择一项", "请先选择一条记录。", parent=self.root)
            return None
        return selected[0]

    def show_selected(self, tree_name):
        selected = self._selected_row(tree_name)
        if selected is None:
            return
        if tree_name == "contacts":
            row = next((item for item in list_contacts(1000) if item["chat_label"] == selected), None)
            if not row:
                return
            recent = [item for item in list_messages(1000) if item["chat_label"] == selected][:12]
            rank = {4: "P0", 3: "P1", 2: "P2", 1: "P3", 0: "—"}.get(int(row["priority_rank"]), "—")
            meta = (f"联系人/群：{row['chat_label']}\n消息数：{row['message_count']}\n今日消息：{row['today_count']}\n"
                    f"待审核事务：{row['pending_count']}\n已确认待办：{row['confirmed_count']}\n"
                    f"待回复项：{row['reply_count']}\n最高待处理优先级：{rank}\n排序分：{row['rank_score']}\n"
                    f"最近消息：{(row['last_message_at'] or '—')}\n\n最近消息（最多 12 条）")
            text = "\n".join(f"[{item['timestamp']}] {item['text']}" for item in recent) or "暂无本地消息"
            self._show_detail_window(meta, text, title=f"联系人 · {row['chat_label']}")
        elif tree_name == "messages":
            row = next((item for item in list_messages(1000) if item["message_key"] == selected), None)
            if not row:
                return
            analysis = json.loads(row["analysis_json"])
            meta = (f"来源联系人/群：{row['chat_label']}\n消息时间：{row['timestamp'].replace('T', ' ')[:19]}\n"
                    f"分类：{'、'.join(analysis.get('categories', []))}\n"
                    f"优先级：{analysis.get('priority', '—')}（分数 {analysis.get('importance', '—')}）\n"
                    f"需要回复：{'是' if analysis.get('needs_reply') else '否/不确定'}\n"
                    f"日期提示：{analysis.get('date_hint') or '无'}\n"
                    f"分析理由：{'；'.join(analysis.get('reasons', [])) or '无'}")
            self._show_detail_window(meta, row["text"], title=f"消息 · {row['chat_label']}")
        else:
            rows = list_todos("pending_review" if tree_name == "review" else "confirmed")
            row = next((item for item in rows if str(item["id"]) == selected), None)
            if row:
                self._show_todo_detail(row)

    def _show_todo_detail(self, row):
        due_display = format_due_display(row["due_date"], row["due_display"], row["due_hint"])
        status_label = {"pending_review": "待确认", "confirmed": "已确认",
                        "done": "已完成", "dismissed": "已忽略"}.get(
                            row["status"], row["status"])
        reasons = "；".join(json.loads(row["reasons_json"])) or "无"
        message_time = (row["timestamp"] or "").replace("T", " ")[:19]
        meta = (f"候选编号：{row['id']}\n联系人/群：{row['chat_label']}\n消息时间：{message_time}\n"
                f"分类：{row['category']}\n优先级：{row['priority']}（分数 {row['importance']}）\n"
                f"截止/提示：{due_display}\n原始时间提示：{row['due_hint'] or '无'}\n"
                f"需要回复：{'是' if row['needs_reply'] else '不确定/否'}\n"
                f"置信度：{row['confidence']:.0%}\n分析理由：{reasons}\n状态：{status_label}")
        actions = []
        if row["status"] == "pending_review":
            actions.append(("确认加入待办", "primary",
                            lambda window: self._detail_decide_todo(window, row["id"], "confirmed")))
            actions.append(("忽略此候选", "danger",
                            lambda window: self._detail_decide_todo(
                                window, row["id"], "dismissed", confirm=True)))
        elif row["status"] == "confirmed":
            actions.append(("标记完成", "primary",
                            lambda window: self._detail_decide_todo(window, row["id"], "done")))
        self._show_detail_window(meta, row["source_text"], title=row["title"], actions=actions)

    def _detail_decide_todo(self, window, todo_id, decision, confirm=False):
        if confirm and not messagebox.askyesno(
                "忽略候选", "确认忽略这条候选？原始消息仍保留在本地消息列表中。",
                parent=window):
            return
        if review_todo(todo_id, decision):
            self.refresh_all()
            window.destroy()
            label = {"confirmed": "已加入待办", "dismissed": "已忽略", "done": "已标记完成"}[decision]
            self.status.set(label)
        else:
            messagebox.showinfo("无法更新", "这条记录的状态已变化，请刷新后重试。", parent=window)

    def _show_detail_window(self, meta, text, title="事项详情", actions=None):
        window = tk.Toplevel(self.root)
        window.title(f"{str(title)[:30]} · 完整信息")
        window.geometry("820x620")
        window.minsize(680, 500)
        window.configure(bg=BG)
        window.transient(self.root)
        accent_row = tk.Frame(window, bg=CARD)
        accent_row.pack(fill="x", pady=(10, 0))
        RoundedBar(accent_row, width=44, height=4, fill=BLUE, bg=CARD).pack(anchor="center")

        head = tk.Frame(window, bg=CARD)
        head.pack(fill="x", padx=22, pady=(12, 10))
        title_box = tk.Frame(head, bg=CARD)
        title_box.pack(side="left", fill="x", expand=True)
        tk.Label(title_box, text=str(title), font=ui_font(15, "bold"),
                 bg=CARD, fg=TEXT, anchor="w", justify="left",
                 wraplength=560).pack(anchor="w")
        tk.Label(title_box, text="完整信息 · 内容仅在本机展示", font=ui_font(8),
                 bg=CARD, fg=TEXT_3).pack(anchor="w", pady=(3, 0))
        RoundedButton(head, text="关闭", kind="ghost", height=32, padx=14,
                      command=window.destroy).pack(side="right", padx=(8, 0))
        RoundedButton(head, text="复制全文", kind="soft", height=32, padx=14,
                      command=lambda: self._copy_detail(window, text)).pack(side="right")

        body = tk.Frame(window, bg=BG)
        body.pack(fill="both", expand=True, padx=22, pady=(0, 12))
        meta_card = RoundedFrame(body, radius=12, fill=CARD, outline=BORDER, bg=BG)
        meta_card.pack(fill="x")
        tk.Label(meta_card.content, text=meta, justify="left", anchor="w", wraplength=720,
                 font=ui_font(9), bg=CARD, fg=TEXT_2).pack(fill="x", padx=16, pady=14)
        tk.Label(body, text=f"完整原始内容（{len(text)} 字，本地保存）", font=ui_font(10, "bold"),
                 bg=BG, fg=TEXT).pack(anchor="w", pady=(14, 6))

        text_holder = RoundedFrame(body, radius=12, fill=CARD, outline=BORDER, bg=BG)
        text_holder.pack(fill="both", expand=True)
        box = tk.Text(text_holder.content, wrap="word", font=ui_font(10), bg=CARD, fg=TEXT,
                      relief="flat", bd=0, padx=14, pady=12, insertbackground=TEXT,
                      selectbackground=SELECT_BG, selectforeground=TEXT)
        scroll = ttk.Scrollbar(text_holder.content, orient="vertical", command=box.yview)
        box.configure(yscrollcommand=scroll.set)
        box.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        box.insert("1.0", text)
        box.configure(state="disabled")

        footer = tk.Frame(window, bg=BG)
        footer.pack(side="bottom", fill="x", padx=22, pady=(0, 16), before=body)
        for label, kind, callback in (actions or []):
            RoundedButton(footer, text=label, kind=kind, height=34,
                          command=lambda cb=callback: cb(window)).pack(side="left", padx=(0, 8))
        RoundedButton(footer, text="关闭", kind="ghost", height=34,
                      command=window.destroy).pack(side="right")
        window.bind("<Escape>", lambda _event: window.destroy())

    def _copy_detail(self, window, text):
        window.clipboard_clear()
        window.clipboard_append(text)
        self.status.set("完整内容已复制到剪贴板。")

    def show_dashboard_detail(self, status, todo_id):
        rows = list_todos("pending_review" if status == "pending_review" else "confirmed")
        row = next((item for item in rows if str(item["id"]) == str(todo_id)), None)
        if row:
            self._show_todo_detail(row)

    def _apply_decision(self, decision, tree_name):
        selected = self._selected_row(tree_name)
        if selected is None:
            return
        try:
            todo_id = int(selected)
        except ValueError:
            return
        if review_todo(todo_id, decision):
            self.refresh_all()

    def confirm_selected(self):
        self._apply_decision("confirmed", "review")

    def dismiss_selected(self):
        selected = self._selected_row("review")
        if selected is None:
            return
        if messagebox.askyesno("忽略候选", "确认将此候选标记为忽略？原始消息仍保留在本地消息列表中。", parent=self.root):
            self._apply_decision("dismissed", "review")

    def complete_selected(self):
        self._apply_decision("done", "todos")

    def dashboard_confirm(self, todo_id):
        if review_todo(todo_id, "confirmed"):
            self.refresh_all()

    def dashboard_dismiss(self, todo_id):
        if messagebox.askyesno("忽略候选", "确认将此候选标记为忽略？原始消息仍保留在本地消息列表中。", parent=self.root):
            if review_todo(todo_id, "dismissed"):
                self.refresh_all()

    def dashboard_complete(self, todo_id):
        if review_todo(todo_id, "done"):
            self.refresh_all()

    def _update_tree_selection(self, name):
        tree = getattr(self, f"{name}_tree", None)
        var = self._selection_vars.get(name)
        button = self._detail_buttons.get(name)
        if tree is None or var is None:
            return
        selection = tree.selection()
        if not selection:
            var.set("未选择记录 · 单击一行查看操作")
            if button:
                button.configure(state="disabled")
            return
        values = tree.item(selection[0], "values")

        def val(index):
            return str(values[index]) if index < len(values) else ""

        if name in ("review", "todos", "competition"):
            text = f"已选择 {val(1)} · {val(3)} · {val(6)}"
            if val(5):
                text += f" · 截止 {val(5)}"
        elif name == "course":
            text = f"已选择课程作业 · {val(0)} · {val(1)} · 截止 {val(2)}"
        elif name == "messages":
            snippet = val(4)
            if len(snippet) > 70:
                snippet = snippet[:70] + "…"
            text = f"已选择消息 · {val(1)} · {val(3)} · {snippet}"
        elif name == "contacts":
            text = f"已选择 {val(0)} · 消息 {val(1)} 条 · 待审核 {val(3)} · 待回复 {val(5)}"
        else:
            text = "已选择 · " + " · ".join(value for value in values[:3] if value)
        var.set(text)
        if button:
            button.configure(state="normal")

    def _update_page_buttons(self):
        review_ready = bool(self.review_tree.selection())
        for button in (self.review_detail_btn, self.review_confirm_btn,
                       self.review_dismiss_btn):
            button.configure(state="normal" if review_ready else "disabled")
        todo_ready = bool(self.todos_tree.selection())
        self.todo_detail_btn.configure(state="normal" if todo_ready else "disabled")
        self.todo_complete_btn.configure(state="normal" if todo_ready else "disabled")

    def _competition_on_select(self, _event=None):
        selection = self.competition_tree.selection()
        if not selection:
            self.competition_selected = None
        else:
            status, todo_id = selection[0].split(":", 1)
            self.competition_selected = (status, int(todo_id))
        self._update_competition_buttons()

    def _update_competition_buttons(self):
        if self.competition_selected is None:
            for button in (self.competition_detail_btn, self.competition_confirm_btn,
                           self.competition_dismiss_btn, self.competition_complete_btn):
                button.configure(state="disabled")
            return
        status, _todo_id = self.competition_selected
        self.competition_detail_btn.configure(state="normal")
        pending = status == "pending_review"
        confirmed = status == "confirmed"
        self.competition_confirm_btn.configure(state="normal" if pending else "disabled")
        self.competition_dismiss_btn.configure(state="normal" if pending else "disabled")
        self.competition_complete_btn.configure(state="normal" if confirmed else "disabled")

    def competition_detail(self):
        if not self.competition_selected:
            return
        status, todo_id = self.competition_selected
        row = next((item for item in list_todos(status) if str(item["id"]) == str(todo_id)), None)
        if row:
            self._show_todo_detail(row)

    def competition_confirm(self):
        if self.competition_selected and self.competition_selected[0] == "pending_review":
            if review_todo(self.competition_selected[1], "confirmed"):
                self.refresh_all()

    def competition_dismiss(self):
        if self.competition_selected and self.competition_selected[0] == "pending_review":
            if messagebox.askyesno("忽略候选", "确认将此比赛/竞赛候选标记为忽略？原始消息仍保留在本地消息列表中。", parent=self.root):
                if review_todo(self.competition_selected[1], "dismissed"):
                    self.refresh_all()

    def competition_complete(self):
        if self.competition_selected and self.competition_selected[0] == "confirmed":
            if review_todo(self.competition_selected[1], "done"):
                self.refresh_all()

    def _course_on_select(self, _event=None):
        selection = self.course_tree.selection()
        self.course_selected = selection[0] if selection else None
        self._update_course_buttons()

    def _course_row(self):
        if not self.course_selected:
            return None
        return get_course_assignment(self.course_selected)

    def _update_course_buttons(self):
        row = self._course_row()
        if row is None:
            for button in (self.course_open_btn, self.course_detail_btn,
                           self.course_confirm_btn, self.course_dismiss_btn,
                           self.course_complete_btn):
                button.configure(state="disabled")
            return
        self.course_open_btn.configure(state="normal" if row["detail_url"] else "disabled")
        self.course_detail_btn.configure(state="normal")
        pending = row["status"] == "pending_review"
        confirmed = row["status"] == "confirmed"
        self.course_confirm_btn.configure(state="normal" if pending else "disabled")
        self.course_dismiss_btn.configure(state="normal" if pending else "disabled")
        self.course_complete_btn.configure(state="normal" if confirmed else "disabled")

    @staticmethod
    def _local_iso_text(value: str) -> str:
        try:
            return datetime.fromisoformat(value).astimezone().strftime("%m-%d %H:%M")
        except (TypeError, ValueError):
            return (value or "").replace("T", " ")[:16]

    def _course_state_label(self, row):
        return row["state_text"] or {
            "open": "待交", "submitted": "已交", "graded": "已批阅",
            "closed": "已截止", "unknown": "—"}.get(row["state"], "—")

    def course_detail(self):
        row = self._course_row()
        if row is None:
            return
        due_display = format_due_display(row["due_date"], row["due_display"])
        todo_text = {"pending_review": "待确认", "confirmed": "已确认",
                     "done": "已完成", "dismissed": "已忽略"}.get(row["status"], row["status"])
        meta = (f"课程：{row['course_name']}\n作业：{row['title']}\n"
                f"截止：{due_display}\n平台状态：{self._course_state_label(row)}\n"
                f"待办状态：{todo_text}\n首次同步：{self._local_iso_text(row['first_seen_at'])}\n"
                f"最近同步：{self._local_iso_text(row['updated_at'])}\n"
                f"作业链接：{row['detail_url'] or '平台未提供'}")
        actions = []
        if row["status"] == "pending_review":
            actions.append(("确认加入待办", "primary",
                            lambda window: self._detail_decide_course(
                                window, row["assignment_key"], "confirmed")))
            actions.append(("忽略作业", "danger",
                            lambda window: self._detail_decide_course(
                                window, row["assignment_key"], "dismissed", confirm=True)))
        elif row["status"] == "confirmed":
            actions.append(("标记完成", "primary",
                            lambda window: self._detail_decide_course(
                                window, row["assignment_key"], "done")))
        self._show_detail_window(meta, row["title"], title=f"课程作业 · {row['title']}",
                                 actions=actions)

    def _detail_decide_course(self, window, assignment_key, decision, confirm=False):
        if confirm and not messagebox.askyesno(
                "忽略作业", "确认忽略这条课程作业？它会从列表中隐藏，原始记录仍保留在本地。",
                parent=window):
            return
        if review_course_assignment(assignment_key, decision):
            self.refresh_all()
            window.destroy()
            self.status.set("课程作业状态已更新。")
        else:
            messagebox.showinfo("无法更新", "这条作业的状态已变化，请刷新后重试。", parent=window)

    def course_open(self):
        row = self._course_row()
        url = safe_chaoxing_url(row["detail_url"]) if row is not None else ""
        if not url:
            messagebox.showinfo("没有链接", "这条作业没有可打开的学习通链接。", parent=self.root)
            return
        webbrowser.open(url)

    def course_confirm(self):
        if self.course_selected:
            if review_course_assignment(self.course_selected, "confirmed"):
                self.refresh_all()

    def course_dismiss(self):
        if self.course_selected:
            if messagebox.askyesno("忽略作业", "确认忽略这条课程作业？它会从列表中隐藏，原始记录仍保留在本地。",
                                   parent=self.root):
                if review_course_assignment(self.course_selected, "dismissed"):
                    self.refresh_all()

    def course_complete(self):
        if self.course_selected:
            if review_course_assignment(self.course_selected, "done"):
                self.refresh_all()

    def _chaoxing_script_text(self) -> str:
        path = self._asset_path("chaoxing_bridge.user.js")
        template = path.read_text(encoding="utf-8")
        if "__PORT__" not in template or "__TOKEN__" not in template:
            raise ValueError("学习通脚本模板缺少占位符")
        return (template.replace("__PORT__", str(self.bridge.port))
                .replace("__TOKEN__", self.bridge_token))

    def open_chaoxing_dialog(self):
        if self.chaoxing_window is not None:
            try:
                if self.chaoxing_window.winfo_exists():
                    self.chaoxing_window.lift()
                    self.chaoxing_window.focus_force()
                    return
            except tk.TclError:
                pass
        try:
            script = self._chaoxing_script_text()
        except (OSError, ValueError) as exc:
            messagebox.showerror("无法打开接入说明", f"读取脚本模板失败：{exc}", parent=self.root)
            return
        self.chaoxing_window = ChaoxingAccessDialog(
            self.root, script, self.bridge.port, self.bridge.running,
            self.bridge.error, on_reset_token=self._rotate_bridge_token)

    def _on_chaoxing_import(self, summary: dict):
        self.events.put(("chaoxing_import", summary))

    @staticmethod
    def _new_bridge_token() -> str:
        token = secrets.token_urlsafe(32)
        save_secret(SECRET_CHAOXING_TOKEN, token)
        return token

    def _rotate_bridge_token(self):
        if self.bridge is not None:
            self.bridge.stop()
        self.bridge_token = self._new_bridge_token()
        self.bridge = ChaoxingBridge(
            self.bridge_token, self._on_chaoxing_import,
            preferred_port=int(self.settings.get("chaoxing_port", CHAOXING_DEFAULT_PORT)))
        started = self.bridge.start()
        if started and self.settings.get("chaoxing_port") != self.bridge.port:
            self.settings["chaoxing_port"] = self.bridge.port
            save_settings(self.settings)
        return self._chaoxing_script_text(), self.bridge.port, started, self.bridge.error

    def open_import_dialog(self):
        if self.import_window is not None:
            try:
                if self.import_window.winfo_exists():
                    self.import_window.lift()
                    self.import_window.focus_force()
                    return
            except tk.TclError:
                pass
        self.import_window = HistoryImportDialog(
            self.root,
            self.settings.get("history_api_url", HISTORY_API_DEFAULT),
            self.http_token_memory,
            self.mode_var.get(),
            self.api_endpoint_var.get().strip(),
            self.api_model_var.get().strip(),
            self.api_key_memory or self.api_key_var.get().strip(),
            allow_remote=self.remote_consent_var.get(),
            on_imported=self.refresh_all,
            on_url_change=self._save_history_url,
            on_http_token=self._save_http_token,
        )

    def _save_history_url(self, url):
        self.settings["history_api_url"] = url
        save_settings(self.settings)

    def _save_http_token(self, token):
        self.http_token_memory = (token or "").strip()
        save_secret(SECRET_HTTP_TOKEN, self.http_token_memory)

    def clear_credentials(self):
        if messagebox.askyesno(
                "清除已保存凭据",
                "这会删除 Windows DPAPI 加密保存的 API Key、NapCat Token 与学习通接入令牌，"
                "并取消远程知情确认；学习通脚本需要重新复制。不会删除消息和待办。确认继续？",
                parent=self.root):
            clear_all_secrets()
            self.api_key_memory = ""
            self.token_memory = ""
            self.http_token_memory = ""
            self.napcat_webui_token_memory = ""
            self.api_key_var.set("")
            self.token_var.set("")
            self.napcat_webui_token_var.set("")
            self.remote_consent_var.set(False)
            self.settings["allow_remote_api"] = False
            save_settings(self.settings)
            if self.chaoxing_window is not None:
                try:
                    self.chaoxing_window._close()
                except tk.TclError:
                    pass
                self.chaoxing_window = None
            try:
                self._rotate_bridge_token()
            except (OSError, ValueError):
                pass
            self.status.set("已清除加密保存的凭据，并重置学习通接入令牌；请在接入说明中重新复制脚本")

    def clear_data(self):
        if messagebox.askyesno("清空本地数据",
                               "这会永久删除本地保存的消息、待办与课程作业，且无法撤销。确认继续？",
                               icon="warning", parent=self.root):
            clear_all_data()
            self.refresh_all()

    def close(self):
        self.closing = True
        if self.bridge is not None:
            self.bridge.stop()
        if self.listener:
            self.listener.stop()
        if self.import_window is not None:
            try:
                self.import_window.closed = True
                self.import_window.destroy()
            except tk.TclError:
                pass
        if self.chaoxing_window is not None:
            try:
                self.chaoxing_window.closed = True
                self.chaoxing_window.destroy()
            except tk.TclError:
                pass
        self.api_key_memory = ""
        self.token_memory = ""
        self.http_token_memory = ""
        self.napcat_webui_token_memory = ""
        self.api_key_var.set("")
        self.token_var.set("")
        self.napcat_webui_token_var.set("")
        self.root.destroy()

def main():
    root = tk.Tk()
    _configure_styles(root)
    InboxApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
