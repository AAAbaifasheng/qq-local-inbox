from __future__ import annotations
import json
import queue
import threading
import tkinter as tk
from datetime import date
from pathlib import Path
from tkinter import ttk, messagebox
from .classifier import classify_message, message_context
from .api_classifier import classify_with_api, validate_api_endpoint
from .config import HISTORY_API_DEFAULT, LOCAL_API_DEFAULT, data_dir, load_settings, save_settings
from .localnet import is_remote_url
from .napcat_api import NapCatClient
from .onebot import OneBotListener, validate_local_ws_url
from .secret_store import (SECRET_API_KEY, SECRET_HTTP_TOKEN, SECRET_WS_TOKEN,
                           clear_all_secrets, load_secret, save_secret)
from .store import (init_db, insert_event, list_messages, list_todos, list_contacts,
                    list_competition_items, review_todo, clear_all_data)
from .sync import needs_model_analysis, sync_today
from .dashboard import DashboardFrame
from .import_dialog import HistoryImportDialog

UI_FONT = ("Microsoft YaHei UI", 9)
PAGE_BG = "#f4f5f7"
API_PRESETS = {
    "Ollama": "http://127.0.0.1:11434/v1/chat/completions",
    "LM Studio": "http://127.0.0.1:1234/v1/chat/completions",
    "DeepSeek": "https://api.deepseek.com/v1/chat/completions",
}

def _configure_styles(root):
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure(".", font=UI_FONT)
    style.configure("TFrame", background=PAGE_BG)
    style.configure("TLabel", background=PAGE_BG, foreground="#1f2329")
    style.configure("TButton", padding=(10, 4))
    style.configure("TCheckbutton", background=PAGE_BG)
    style.configure("TRadiobutton", background=PAGE_BG)
    style.configure("TNotebook", background=PAGE_BG, borderwidth=0)
    style.configure("TNotebook.Tab", padding=(16, 7))
    style.map("TNotebook.Tab", background=[("selected", "#ffffff")], foreground=[("selected", "#1f2329")])
    style.configure("Treeview", rowheight=26, background="#ffffff", fieldbackground="#ffffff", borderwidth=0)
    style.configure("Treeview.Heading", font=(UI_FONT[0], 9, "bold"))

class InboxApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("QQ Local Inbox · 本地事务分拣器")
        self.root.geometry("1160x820")
        self.root.minsize(940, 650)
        self.root.configure(bg=PAGE_BG)
        init_db()
        self.settings = load_settings()
        self.listener = None
        self.import_window = None
        self.api_key_memory = load_secret(SECRET_API_KEY)
        self.token_memory = load_secret(SECRET_WS_TOKEN)
        self.http_token_memory = load_secret(SECRET_HTTP_TOKEN)
        self.sync_running = False
        self.auto_sync_attempted = False
        self.closing = False
        self.events = queue.Queue()
        self.status = tk.StringVar(value="未连接 · 本地规则分类 · 不调用模型")
        self.url_var = tk.StringVar(value=self.settings.get("ws_url", "ws://127.0.0.1:3001"))
        self.token_var = tk.StringVar(value=self.token_memory)
        self.group_var = tk.BooleanVar(value=bool(self.settings.get("include_group_messages", False)))
        self.mode_var = tk.StringVar(value=self.settings.get("analysis_mode", "rules"))
        self.api_endpoint_var = tk.StringVar(value=self.settings.get("api_endpoint", LOCAL_API_DEFAULT))
        self.api_model_var = tk.StringVar(value=self.settings.get("api_model", ""))
        self.api_key_var = tk.StringVar(value=self.api_key_memory)
        self.api_preset_var = tk.StringVar(value=self._preset_name(self.api_endpoint_var.get()))
        self.remote_consent_var = tk.BooleanVar(value=bool(self.settings.get("allow_remote_api", False)))
        self.auto_connect_var = tk.BooleanVar(value=bool(self.settings.get("auto_connect", True)))
        self.auto_sync_var = tk.BooleanVar(value=bool(self.settings.get("auto_sync_today", True)))
        self._build()
        self._toggle_api_fields()
        self.refresh_all()
        self._set_window_icon()
        self.root.after(250, self._drain_events)
        self.root.after(800, self._auto_connect)
        self.root.after(120000, self._periodic_refresh)
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
        top = ttk.Frame(self.root, padding=(14, 10, 14, 4))
        top.pack(fill="x")
        self.ws_label = ttk.Label(top, text="NapCat OneBot WebSocket：")
        self.ws_label.grid(row=0, column=0, sticky="w")
        self.ws_entry = ttk.Entry(top, textvariable=self.url_var, width=34)
        self.ws_entry.grid(row=0, column=1, sticky="ew", padx=(4, 10))
        self.token_label = ttk.Label(top, text="Access Token（加密保存，可留空）：")
        self.token_label.grid(row=0, column=2, sticky="w")
        self.token_entry = ttk.Entry(top, textvariable=self.token_var, show="•", width=24)
        self.token_entry.grid(row=0, column=3, sticky="ew", padx=(4, 10))
        self.options_frame = ttk.Frame(top)
        self.options_frame.grid(row=1, column=1, columnspan=3, sticky="w", pady=(6, 0))
        self.group_check = ttk.Checkbutton(self.options_frame, text="接收群消息", variable=self.group_var)
        self.group_check.pack(side="left")
        self.auto_connect_check = ttk.Checkbutton(self.options_frame, text="启动时自动连接",
                                                  variable=self.auto_connect_var)
        self.auto_connect_check.pack(side="left", padx=(16, 0))
        self.auto_sync_check = ttk.Checkbutton(self.options_frame, text="启动时同步今天消息",
                                               variable=self.auto_sync_var)
        self.auto_sync_check.pack(side="left", padx=(16, 0))

        self.mode_label = ttk.Label(top, text="分析方式：")
        self.mode_label.grid(row=2, column=0, sticky="w", pady=(8, 0))
        mode_frame = ttk.Frame(top)
        mode_frame.grid(row=2, column=1, columnspan=3, sticky="w", pady=(8, 0))
        self.mode_rules_btn = ttk.Radiobutton(mode_frame, text="本地规则", value="rules",
                                              variable=self.mode_var, command=self._toggle_api_fields)
        self.mode_rules_btn.pack(side="left")
        self.mode_api_btn = ttk.Radiobutton(mode_frame, text="大模型 API（本机/远程）", value="api",
                                            variable=self.mode_var, command=self._toggle_api_fields)
        self.mode_api_btn.pack(side="left", padx=(14, 0))

        self.api_endpoint_label = ttk.Label(top, text="API Endpoint：")
        self.api_endpoint_label.grid(row=3, column=0, sticky="w", pady=(6, 0))
        self.api_endpoint_entry = ttk.Entry(top, textvariable=self.api_endpoint_var)
        self.api_endpoint_entry.grid(row=3, column=1, columnspan=2, sticky="ew", padx=(4, 10), pady=(6, 0))
        self.api_preset_box = ttk.Combobox(top, textvariable=self.api_preset_var,
                                           values=tuple(API_PRESETS) + ("自定义",), state="readonly", width=12)
        self.api_preset_box.grid(row=3, column=3, sticky="w", padx=(4, 10), pady=(6, 0))
        self.api_preset_box.bind("<<ComboboxSelected>>", lambda _event: self._apply_api_preset())

        self.api_model_label = ttk.Label(top, text="API Model（模型名）：")
        self.api_model_label.grid(row=4, column=0, sticky="w", pady=(6, 0))
        self.api_model_entry = ttk.Entry(top, textvariable=self.api_model_var, width=28)
        self.api_model_entry.grid(row=4, column=1, sticky="ew", padx=(4, 10), pady=(6, 0))
        self.api_key_label = ttk.Label(top, text="API Key（加密保存；远程必填）：")
        self.api_key_label.grid(row=4, column=2, sticky="e", pady=(6, 0))
        self.api_key_entry = ttk.Entry(top, textvariable=self.api_key_var, show="•", width=24)
        self.api_key_entry.grid(row=4, column=3, sticky="ew", padx=(4, 10), pady=(6, 0))
        self.api_hint_label = ttk.Label(top, text="本机端点默认允许；远程需 HTTPS + 知情确认。Key/Token 用 Windows DPAPI 加密保存在本机。",
                                        foreground="#5c6b7a")
        self.api_hint_label.grid(row=5, column=1, columnspan=3, sticky="w", pady=(6, 0))
        self.remote_consent_check = ttk.Checkbutton(
            top, text="我知晓远程 API 会把消息文本发送给该服务商",
            variable=self.remote_consent_var, command=self._toggle_api_fields)
        self.remote_consent_check.grid(row=6, column=1, columnspan=3, sticky="w", pady=(6, 0))
        self.api_widgets = (self.api_endpoint_label, self.api_endpoint_entry, self.api_preset_box,
                            self.api_model_label, self.api_model_entry, self.api_key_label,
                            self.api_key_entry, self.api_hint_label, self.remote_consent_check)
        self.connection_widgets = (self.ws_label, self.ws_entry, self.token_label, self.token_entry,
                                   self.options_frame, self.mode_label, mode_frame) + self.api_widgets

        btns = ttk.Frame(top)
        btns.grid(row=7, column=1, columnspan=3, sticky="e", pady=(8, 0))
        self.sync_btn = ttk.Button(btns, text="同步今天消息", command=self.start_today_sync)
        self.sync_btn.pack(side="left", padx=4)
        self.import_btn = ttk.Button(btns, text="导入历史消息…", command=self.open_import_dialog)
        self.import_btn.pack(side="left", padx=4)
        self.start_btn = ttk.Button(btns, text="开始监听新消息", command=self.start_listener)
        self.start_btn.pack(side="left", padx=4)
        self.stop_btn = ttk.Button(btns, text="停止监听", command=self.stop_listener, state="disabled")
        self.stop_btn.pack(side="left", padx=4)
        top.columnconfigure(1, weight=1)
        top.columnconfigure(3, weight=1)

        ttk.Label(self.root, textvariable=self.status, padding=(14, 4)).pack(fill="x")
        ttk.Label(self.root, text="隐私说明：QQ 接入仅限本机 WebSocket；历史导入只访问本机 NapCat HTTP；默认只调用本机模型。勾选远程 API 后，消息文本会发送给所配置服务商；Key/Token 使用 Windows DPAPI 加密保存在本机，可在底部清除；消息只保存在本机 SQLite。",
                  foreground="#8a3d00", wraplength=1080).pack(fill="x", padx=14, pady=(0, 8))

        bottom = ttk.Frame(self.root, padding=(14, 0, 14, 8))
        bottom.pack(side="bottom", fill="x")
        ttk.Label(bottom, text=f"本地数据目录：{data_dir()}").pack(side="left", fill="x", expand=True)
        ttk.Button(bottom, text="清除已保存凭据", command=self.clear_credentials).pack(side="right", padx=(0, 8))
        ttk.Button(bottom, text="清空本地消息和待办…", command=self.clear_data).pack(side="right")

        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        self.dashboard = DashboardFrame(self.tabs, on_detail=self.show_dashboard_detail,
                                        on_confirm=self.dashboard_confirm, on_dismiss=self.dashboard_dismiss,
                                        on_complete=self.dashboard_complete)
        self.tabs.add(self.dashboard, text="事务中心")
        self.competition_tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(self.competition_tab, text="比赛/竞赛")
        self.msg_tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(self.msg_tab, text="最近消息")
        self.review_tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(self.review_tab, text="待审核事务")
        self.todo_tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(self.todo_tab, text="已确认待办")
        self.contact_tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(self.contact_tab, text="联系人排序")

        self._create_tree(self.msg_tab, "messages", ("time", "contact", "kind", "priority", "text"),
                          ("时间", "联系人/群", "分类", "优先级", "消息摘要"), (145, 180, 140, 70, 520))
        review_buttons = ttk.Frame(self.review_tab)
        review_buttons.pack(side="bottom", fill="x", pady=(8, 0))
        ttk.Button(review_buttons, text="查看原消息", command=lambda: self.show_selected("review")).pack(side="left", padx=3)
        ttk.Button(review_buttons, text="确认加入待办", command=self.confirm_selected).pack(side="left", padx=3)
        ttk.Button(review_buttons, text="忽略此候选", command=self.dismiss_selected).pack(side="left", padx=3)
        self._create_tree(self.review_tab, "review", ("id", "priority", "importance", "contact", "category", "due", "title"),
                          ("编号", "优先级", "分数", "联系人", "分类", "截止/提示", "候选事项（需人工确认）"),
                          (55, 65, 55, 150, 130, 175, 400))
        todo_buttons = ttk.Frame(self.todo_tab)
        todo_buttons.pack(side="bottom", fill="x", pady=(8, 0))
        ttk.Button(todo_buttons, text="查看原消息", command=lambda: self.show_selected("todos")).pack(side="left", padx=3)
        ttk.Button(todo_buttons, text="标记完成", command=self.complete_selected).pack(side="left", padx=3)
        self._create_tree(self.todo_tab, "todos", ("id", "priority", "importance", "contact", "category", "due", "title"),
                          ("编号", "优先级", "分数", "联系人", "分类", "截止/提示", "已确认待办"),
                          (55, 65, 55, 150, 130, 175, 400))
        self._create_tree(self.contact_tab, "contacts",
                          ("contact", "messages", "today", "pending", "confirmed", "reply", "max_priority", "max_score", "last_message", "rank_score"),
                          ("联系人/群", "消息数", "今日", "待审核", "已确认", "待回复", "最高优先级", "最高分", "最近消息", "排序分"),
                          (210, 65, 55, 75, 75, 65, 90, 65, 135, 65))
        competition_buttons = ttk.Frame(self.competition_tab)
        competition_buttons.pack(side="bottom", fill="x", pady=(8, 0))
        self.competition_detail_btn = ttk.Button(competition_buttons, text="查看详情",
                                                 command=self.competition_detail, state="disabled")
        self.competition_confirm_btn = ttk.Button(competition_buttons, text="确认加入待办",
                                                  command=self.competition_confirm, state="disabled")
        self.competition_dismiss_btn = ttk.Button(competition_buttons, text="忽略此候选",
                                                  command=self.competition_dismiss, state="disabled")
        self.competition_complete_btn = ttk.Button(competition_buttons, text="标记完成",
                                                   command=self.competition_complete, state="disabled")
        for button in (self.competition_detail_btn, self.competition_confirm_btn,
                       self.competition_dismiss_btn, self.competition_complete_btn):
            button.pack(side="left", padx=(0, 6))
        self._create_tree(self.competition_tab, "competition",
                          ("id", "priority", "status", "contact", "category", "due", "title"),
                          ("编号", "优先级", "状态", "联系人/群", "分类", "截止/提示", "比赛/竞赛事项"),
                          (55, 65, 75, 170, 150, 175, 380))
        self.competition_tree.tag_configure("P0", foreground="#c0392b")
        self.competition_tree.tag_configure("P1", foreground="#b45309")
        self.competition_tree.tag_configure("pending", background="#fff8e1")
        self.competition_tree.tag_configure("overdue", background="#fee2e2")
        self.competition_tree.bind("<Double-1>", lambda _event: self.competition_detail())
        self.competition_tree.bind("<<TreeviewSelect>>", self._competition_on_select)
        self.competition_selected = None

    def _create_tree(self, parent, name, keys, headers, widths):
        holder = ttk.Frame(parent)
        holder.pack(fill="both", expand=True)
        tree = ttk.Treeview(holder, columns=keys, show="headings", selectmode="browse")
        for key, header, width in zip(keys, headers, widths):
            tree.heading(key, text=header)
            tree.column(key, width=width, minwidth=45, stretch=(key in {"text", "title"}))
        yscroll = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
        xscroll = ttk.Scrollbar(holder, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        holder.rowconfigure(0, weight=1)
        holder.columnconfigure(0, weight=1)
        setattr(self, f"{name}_tree", tree)
        tree.bind("<Double-1>", lambda _event, tree_name=name: self.show_selected(tree_name))

    def _toggle_api_fields(self):
        api_mode = self.mode_var.get() == "api"
        if api_mode:
            for widget in self.api_widgets:
                widget.grid()
            self.api_endpoint_entry.configure(state="normal")
            self.api_model_entry.configure(state="normal")
            self.api_key_entry.configure(state="normal")
            self.api_preset_box.configure(state="readonly")
        else:
            for widget in self.api_widgets:
                widget.grid_remove()
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

    def _set_connection_settings_visible(self, visible: bool):
        if visible:
            for widget in self.connection_widgets:
                if widget not in self.api_widgets:
                    widget.grid()
            self._toggle_api_fields()
        else:
            for widget in self.connection_widgets:
                widget.grid_remove()

    def _apply_api_preset(self):
        preset = self.api_preset_var.get()
        endpoint = API_PRESETS.get(preset)
        if endpoint:
            self.api_endpoint_var.set(endpoint)
            if preset == "DeepSeek":
                self.api_model_var.set("deepseek-chat")
        self._toggle_api_fields()

    def set_status(self, text):
        self.events.put(("status", text))

    def start_listener(self, auto=False):
        try:
            safe_url = validate_local_ws_url(self.url_var.get())
            token = self.token_var.get()
            mode = self.mode_var.get()
            endpoint = self.api_endpoint_var.get().strip()
            model = self.api_model_var.get().strip()
            api_key = self.api_key_var.get().strip()
            if mode == "api":
                if not endpoint:
                    raise ValueError("请填写 API Endpoint。")
                allow_remote = self.remote_consent_var.get()
                if is_remote_url(endpoint) and not allow_remote:
                    raise ValueError("远程 API 需要先勾选知情确认；消息文本会发送给该服务商。")
                endpoint = validate_api_endpoint(endpoint, allow_remote=allow_remote)
                if is_remote_url(endpoint) and not api_key:
                    raise ValueError("远程 API 必须填写 API Key。")
                if not model:
                    raise ValueError("大模型 API 模式必须填写模型名称（例如 deepseek-chat 或 qwen2.5:7b）。")
            self.api_key_memory = api_key
            self.token_memory = token.strip()
            save_secret(SECRET_API_KEY, api_key)
            save_secret(SECRET_WS_TOKEN, self.token_memory)
            self.settings = {
                "ws_url": safe_url,
                "include_group_messages": self.group_var.get(),
                "analysis_mode": mode,
                "api_endpoint": endpoint,
                "api_model": model,
                "history_api_url": self.settings.get("history_api_url", HISTORY_API_DEFAULT),
                "auto_connect": self.auto_connect_var.get(),
                "auto_sync_today": self.auto_sync_var.get(),
                "allow_remote_api": self.remote_consent_var.get(),
            }
            save_settings(self.settings)
            self.api_endpoint_var.set(self.settings["api_endpoint"])
            listener = OneBotListener(safe_url, token, self.group_var.get(), self._on_event, self.set_status)
            listener.start()
            self.listener = listener
            self._set_connection_settings_visible(False)
        except Exception as exc:
            if auto:
                self._set_connection_settings_visible(True)
                self.status.set(f"自动连接未启动：{str(exc)[:160]}")
            else:
                messagebox.showerror("无法启动监听", str(exc), parent=self.root)
            return
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.status.set("正在连接…仅接收启用后的新事件；不会自动读取历史消息。")
        if self.auto_sync_var.get() and not self.auto_sync_attempted:
            self.auto_sync_attempted = True
            self.root.after(1200, self.start_today_sync)

    def _auto_connect(self):
        if self.closing or self.listener:
            return
        if self.auto_connect_var.get():
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

    def _set_window_icon(self):
        icon = Path(__file__).resolve().parent.parent / "assets" / "icon.ico"
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
        self._set_connection_settings_visible(True)
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
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
        for tree_name in ("contacts_tree", "messages_tree", "review_tree", "todos_tree", "competition_tree"):
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
                    row["due_display"] or row["due_hint"] or "待核对", row["title"][:300]))
        self.tabs.tab(self.review_tab, text=f"待审核事务（{len(self.review_tree.get_children())}）")
        self.tabs.tab(self.todo_tab, text=f"已确认待办（{len(self.todos_tree.get_children())}）")
        today = date.today().isoformat()
        for row in list_competition_items(500):
            status = row["status"]
            tags = [row["priority"]]
            if status == "pending_review":
                tags.append("pending")
            due_text = row["due_display"] or row["due_hint"] or "待核对"
            if row["due_date"] and row["due_date"] < today:
                due_text = "逾期 · " + due_text
                tags.append("overdue")
            status_text = {"pending_review": "待确认", "confirmed": "已确认", "done": "已完成"}.get(status, status)
            self.competition_tree.insert("", "end", iid=f"{status}:{row['id']}", tags=tuple(tags), values=(
                row["id"], row["priority"], status_text, row["chat_label"], row["category"],
                due_text, row["title"][:300]))
        self.competition_selected = None
        self._update_competition_buttons()
        self.tabs.tab(self.competition_tab, text=f"比赛/竞赛（{len(self.competition_tree.get_children())}）")

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
            self._show_detail_window(meta, text)
        elif tree_name == "messages":
            row = next((item for item in list_messages(1000) if item["message_key"] == selected), None)
            if not row:
                return
            analysis = json.loads(row["analysis_json"])
            meta = (f"来源联系人：{row['chat_label']}\n时间：{row['timestamp']}\n"
                    f"分类：{'、'.join(analysis['categories'])}\n"
                    f"优先级：{analysis['priority']}（分数 {analysis['importance']}）\n"
                    f"理由：{'；'.join(analysis.get('reasons', []))}")
            self._show_detail_window(meta, row["text"])
        else:
            rows = list_todos("pending_review" if tree_name == "review" else "confirmed")
            row = next((item for item in rows if str(item["id"]) == selected), None)
            if row:
                self._show_todo_detail(row)

    def _show_todo_detail(self, row):
        due_display = row["due_display"] or row["due_hint"] or "未识别"
        meta = (f"候选编号：{row['id']}\n联系人：{row['chat_label']}\n分类：{row['category']}\n"
                f"优先级：{row['priority']}（分数 {row['importance']}）\n"
                f"截止/提示：{due_display}\n原始时间提示：{row['due_hint'] or '无'}\n"
                f"需要回复：{'是' if row['needs_reply'] else '不确定/否'}\n"
                f"置信度：{row['confidence']:.0%}\n分析理由：{'；'.join(json.loads(row['reasons_json']))}\n"
                f"状态：{row['status']}")
        self._show_detail_window(meta, row["source_text"])

    def _show_detail_window(self, meta, text):
        window = tk.Toplevel(self.root)
        window.title("消息详情 · 本地")
        window.geometry("720x460")
        window.configure(bg=PAGE_BG)
        window.transient(self.root)
        ttk.Label(window, text=meta, justify="left", wraplength=680).pack(fill="x", padx=14, pady=12)
        ttk.Label(window, text="原始文字（本地保存）", font=(UI_FONT[0], 10, "bold")).pack(anchor="w", padx=14)
        box = tk.Text(window, wrap="word", height=10)
        box.pack(fill="both", expand=True, padx=14, pady=(4, 14))
        box.insert("1.0", text)
        box.configure(state="disabled")

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
                "这会删除 Windows DPAPI 加密保存的 API Key 与 NapCat Token，并取消远程知情确认。"
                "不会删除消息和待办。确认继续？", parent=self.root):
            clear_all_secrets()
            self.api_key_memory = ""
            self.token_memory = ""
            self.http_token_memory = ""
            self.api_key_var.set("")
            self.token_var.set("")
            self.remote_consent_var.set(False)
            self.settings["allow_remote_api"] = False
            save_settings(self.settings)
            self.status.set("已清除加密保存的凭据，并取消远程知情确认")

    def clear_data(self):
        if messagebox.askyesno("清空本地数据", "这会永久删除本地保存的消息与所有待办，且无法撤销。确认继续？",
                               icon="warning", parent=self.root):
            clear_all_data()
            self.refresh_all()

    def close(self):
        self.closing = True
        if self.listener:
            self.listener.stop()
        if self.import_window is not None:
            try:
                self.import_window.closed = True
                self.import_window.destroy()
            except tk.TclError:
                pass
        self.api_key_memory = ""
        self.token_memory = ""
        self.http_token_memory = ""
        self.api_key_var.set("")
        self.token_var.set("")
        self.root.destroy()

def main():
    root = tk.Tk()
    _configure_styles(root)
    InboxApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
