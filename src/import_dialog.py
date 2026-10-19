from __future__ import annotations
import queue
import re
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from .api_classifier import classify_with_api, validate_api_endpoint
from .classifier import classify_message, message_context
from .localnet import is_remote_url
from .napcat_api import NapCatClient, validate_local_http_url
from .store import insert_event
from .theme import (AMBER_SOFT, BG, BLUE, BLUE_HOVER, BLUE_SOFT, BORDER, CARD,
                    RADIUS_LG, TEXT, TEXT_2, TEXT_3, RoundedBar, RoundedButton,
                    RoundedFrame, RoundedLabel, ui_font)

PAGE_BG = BG

class HistoryImportDialog(tk.Toplevel):
    def __init__(self, parent, history_api_url, token_hint, mode, endpoint, model, api_key,
                 allow_remote=False, on_imported=None, on_url_change=None, on_http_token=None):
        super().__init__(parent)
        self.title("导入已有聊天记录 · 仅本机")
        self.geometry("760x580")
        self.minsize(700, 540)
        self.configure(bg=PAGE_BG)
        self.transient(parent)
        self.mode = mode
        self.endpoint = endpoint
        self.model = model
        self.api_key = api_key
        self.allow_remote = allow_remote
        self.on_imported = on_imported
        self.on_url_change = on_url_change
        self.on_http_token = on_http_token
        self.events = queue.Queue()
        self.running = False
        self.closed = False
        self.contacts = {"private": [], "group": []}
        self._build(history_api_url, token_hint)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.bind("<Escape>", lambda _event: self._close())
        self.after(100, self._poll)

    def _build(self, history_api_url, token_hint):
        remote = self.mode == "api" and is_remote_url(self.endpoint)
        note = "只读取你选择的这个会话最近 N 条文本，保存到本地 SQLite；不下载图片/文件。"
        if remote and self.allow_remote:
            note += "当前为远程 API：导入的每条文本会发送给服务商。"
        elif remote:
            note += "当前端点为远程地址，尚未授权；导入前请先在主窗口勾选“允许远程 API”。"
        else:
            note += "不发送到远程服务。"
        warning = remote and not self.allow_remote

        accent_row = tk.Frame(self, bg=CARD)
        accent_row.pack(fill="x", pady=(10, 0))
        RoundedBar(accent_row, width=44, height=4, fill=BLUE, bg=CARD).pack(anchor="center")
        header = tk.Frame(self, bg=CARD)
        header.pack(fill="x")
        title_box = tk.Frame(header, bg=CARD)
        title_box.pack(side="left", padx=22, pady=(12, 12))
        tk.Label(title_box, text="导入历史消息", font=ui_font(16, "bold"),
                 bg=CARD, fg=TEXT).pack(anchor="w")
        tk.Label(title_box, text="从本机 NapCat 读取指定会话的历史文本", font=ui_font(8),
                 bg=CARD, fg=TEXT_3).pack(anchor="w", pady=(3, 0))
        RoundedLabel(header, text="仅本机", fill=BLUE_SOFT, fg=BLUE_HOVER,
                     bg=CARD, padx=10, pady=4).pack(side="right", padx=22, pady=16)

        content = tk.Frame(self, bg=BG)
        content.pack(fill="both", expand=True, padx=20, pady=(14, 0))

        note_bg = AMBER_SOFT if warning else BLUE_SOFT
        note_fg = "#8A5A00" if warning else TEXT_2
        note_card = RoundedFrame(content, radius=14, fill=note_bg, outline="",
                                 bg=BG, padding=5)
        note_card.pack(fill="x")
        tk.Label(note_card.content, text=note, bg=note_bg, fg=note_fg, font=ui_font(9),
                 justify="left", anchor="w", wraplength=600).pack(
            fill="x", padx=12, pady=8)

        form_card = RoundedFrame(content, radius=RADIUS_LG, fill=CARD,
                                 outline=BORDER, bg=BG)
        form_card.pack(fill="both", expand=True, pady=(12, 0))
        form = tk.Frame(form_card.content, bg=CARD)
        form.pack(fill="both", expand=True, padx=18, pady=(14, 6))
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="NapCat HTTP 地址", style="CardMuted.TLabel").grid(
            row=0, column=0, sticky="w", pady=4)
        self.url_var = tk.StringVar(value=history_api_url)
        ttk.Entry(form, textvariable=self.url_var).grid(
            row=0, column=1, columnspan=2, sticky="ew", padx=(8, 0), pady=4)

        ttk.Label(form, text="HTTP Access Token", style="CardMuted.TLabel").grid(
            row=1, column=0, sticky="w", pady=4)
        self.token_var = tk.StringVar(value=token_hint or "")
        ttk.Entry(form, textvariable=self.token_var, show="•").grid(
            row=1, column=1, columnspan=2, sticky="ew", padx=(8, 0), pady=4)
        ttk.Label(form, text="若 NapCat HTTP Server 未设置 Token，可留空。",
                  style="CardMuted.TLabel").grid(row=2, column=1, sticky="w", padx=(8, 0))

        ttk.Label(form, text="会话类型", style="CardMuted.TLabel").grid(
            row=3, column=0, sticky="w", pady=(12, 4))
        self.kind_var = tk.StringVar(value="private")
        kinds = tk.Frame(form, bg=CARD)
        kinds.grid(row=3, column=1, columnspan=2, sticky="w", padx=(8, 0), pady=(12, 4))
        ttk.Radiobutton(kinds, text="好友私聊", value="private", variable=self.kind_var,
                        command=self._on_kind_change).pack(side="left")
        ttk.Radiobutton(kinds, text="群聊", value="group", variable=self.kind_var,
                        command=self._on_kind_change).pack(side="left", padx=(16, 0))

        self.target_label = ttk.Label(form, text="QQ 号 / 好友", style="CardMuted.TLabel")
        self.target_label.grid(row=4, column=0, sticky="w", pady=4)
        self.target_var = tk.StringVar()
        self.target_box = ttk.Combobox(form, textvariable=self.target_var, values=(),
                                       state="normal")
        self.target_box.grid(row=4, column=1, sticky="ew", padx=(8, 0), pady=4)
        self.load_btn = RoundedButton(form, text="读取列表", kind="ghost", height=32,
                                      padx=13, command=self._load_contacts)
        self.load_btn.grid(row=4, column=2, sticky="e", padx=(8, 0), pady=4)

        ttk.Label(form, text="导入条数", style="CardMuted.TLabel").grid(
            row=5, column=0, sticky="w", pady=4)
        self.count_var = tk.StringVar(value="20")
        ttk.Spinbox(form, from_=1, to=200, textvariable=self.count_var, width=8).grid(
            row=5, column=1, sticky="w", padx=(8, 0), pady=4)
        mode_text = "本地规则（不调用模型）" if self.mode == "rules" else (
            f"远程 API（{self.model or '未填写模型'}）" if is_remote_url(self.endpoint)
            else f"本地大模型（{self.model or '未填写模型'}）")
        ttk.Label(form, text=f"分析方式：{mode_text}", style="CardMuted.TLabel").grid(
            row=5, column=2, sticky="e", pady=4)

        tk.Frame(form_card.content, bg="#F0F0F2", height=1).pack(fill="x")
        buttons = tk.Frame(form_card.content, bg=CARD)
        buttons.pack(fill="x", padx=18, pady=12)
        self.import_btn = RoundedButton(buttons, text="开始导入", kind="primary",
                                        command=self._start_import)
        self.import_btn.pack(side="left")
        RoundedButton(buttons, text="关闭", kind="ghost",
                      command=self._close).pack(side="right")

        self.status_var = tk.StringVar(value="可以直接输入 QQ 号/群号，也可以先读取列表。")
        ttk.Label(self, textvariable=self.status_var, style="Muted.TLabel",
                  wraplength=620, justify="left").pack(
            fill="x", padx=22, pady=(10, 12))

    def _base_url(self):
        try:
            base = validate_local_http_url(self.url_var.get())
        except ValueError as exc:
            messagebox.showerror("地址无效", str(exc), parent=self)
            return None
        self.on_url_change(base)
        if self.on_http_token:
            self.on_http_token(self.token_var.get())
        return base

    def _target_id(self) -> str:
        match = re.search(r"\d+", self.target_var.get().strip())
        return match.group(0) if match else ""

    def _on_kind_change(self):
        self.target_var.set("")
        private = self.kind_var.get() == "private"
        self.target_label.configure(text="QQ 号 / 好友：" if private else "群号 / 群名：")
        self.target_box.configure(values=self._contact_values())

    def _contact_values(self) -> list[str]:
        if self.kind_var.get() == "private":
            return [f"{item.get('user_id')} · {item.get('remark') or item.get('nickname') or ''}"
                    for item in self.contacts["private"]]
        return [f"{item.get('group_id')} · {item.get('group_name') or ''}"
                for item in self.contacts["group"]]

    def _load_contacts(self):
        if self.running:
            return
        base = self._base_url()
        if not base:
            return
        self.load_btn.configure(state="disabled")
        self.status_var.set("正在从本机 NapCat 读取好友和群列表…")
        token = self.token_var.get()
        threading.Thread(target=self._load_worker, args=(base, token), daemon=True).start()

    def _load_worker(self, base, token):
        try:
            client = NapCatClient(base, token)
            friends = client.list_friends()
            groups = client.list_groups()
        except Exception as exc:
            self.events.put(("list_error", str(exc)[:180]))
            return
        self.events.put(("contacts", friends, groups))

    def _start_import(self):
        if self.running:
            return
        base = self._base_url()
        if not base:
            return
        chat_id = self._target_id()
        if not chat_id:
            messagebox.showerror("缺少会话", "请选择或输入好友 QQ 号 / 群号。", parent=self)
            return
        try:
            count = int(self.count_var.get())
        except (TypeError, ValueError):
            messagebox.showerror("条数无效", "导入条数必须是 1 到 200 之间的整数。", parent=self)
            return
        count = max(1, min(count, 200))
        if self.mode == "api":
            if not self.endpoint:
                messagebox.showerror("缺少 API 地址", "请先在主窗口填写 API Endpoint。", parent=self)
                return
            if is_remote_url(self.endpoint) and not self.allow_remote:
                messagebox.showerror("需要知情确认", "当前端点是远程地址。请先在主窗口勾选“允许远程 API”。", parent=self)
                return
            try:
                self.endpoint = validate_api_endpoint(self.endpoint, allow_remote=self.allow_remote)
            except ValueError as exc:
                messagebox.showerror("API 地址无效", str(exc), parent=self)
                return
            if is_remote_url(self.endpoint) and not self.api_key:
                messagebox.showerror("缺少 API Key", "远程 API 必须填写 API Key。", parent=self)
                return
            if not self.model:
                messagebox.showerror("缺少模型", "大模型 API 模式需要填写模型名称。", parent=self)
                return
        self.running = True
        self.import_btn.configure(state="disabled")
        self.load_btn.configure(state="disabled")
        self.status_var.set("正在读取历史消息…")
        threading.Thread(
            target=self._import_worker,
            args=(base, self.token_var.get(), self.kind_var.get(), chat_id, count),
            daemon=True,
        ).start()

    def _import_worker(self, base, token, kind, chat_id, count):
        try:
            client = NapCatClient(base, token)
            if kind == "private":
                items = client.fetch_friend_history(chat_id, count)
            else:
                items = client.fetch_group_history(chat_id, count)
        except Exception as exc:
            self.events.put(("import_error", str(exc)[:180], 0))
            return
        total = len(items)
        if total == 0:
            self.events.put(("done", 0, 0, 0, 0, 0))
            return
        inserted = duplicates = failed = candidates = 0
        for index, item in enumerate(items, 1):
            if self.closed:
                return
            self.events.put(("progress", f"正在分析 {index}/{total}…"))
            try:
                context = message_context(item["event"])
                if self.mode == "api":
                    analysis = classify_with_api(item["text"], self.endpoint, self.model, self.api_key,
                                                 allow_remote=self.allow_remote, context=context)
                else:
                    analysis = classify_message(item["text"], context)
                if insert_event(item["event"], item["text"], analysis):
                    inserted += 1
                    if analysis.get("task_candidate"):
                        candidates += 1
                else:
                    duplicates += 1
            except Exception as exc:
                failed += 1
                self.events.put(("import_error", str(exc)[:180], inserted))
                return
        self.events.put(("done", inserted, duplicates, failed, candidates, total))

    def _poll(self):
        if self.closed:
            return
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == "contacts":
                    self.contacts["private"] = [item for item in event[1] if isinstance(item, dict)]
                    self.contacts["group"] = [item for item in event[2] if isinstance(item, dict)]
                    self.target_box.configure(values=self._contact_values())
                    if not self.running:
                        self.load_btn.configure(state="normal")
                    self.status_var.set(
                        f"已读取 {len(self.contacts['private'])} 位好友、{len(self.contacts['group'])} 个群。")
                elif event[0] == "list_error":
                    if not self.running:
                        self.load_btn.configure(state="normal")
                    self.status_var.set(f"读取列表失败：{event[1]}")
                elif event[0] == "progress":
                    self.status_var.set(event[1])
                elif event[0] == "done":
                    self._finish(*event[1:])
                elif event[0] == "import_error":
                    self._finish_error(event[1], event[2])
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _finish(self, inserted, duplicates, failed, candidates, total):
        self.running = False
        self.import_btn.configure(state="normal")
        self.load_btn.configure(state="normal")
        if total == 0:
            self.status_var.set("没有读取到可导入的文本消息。")
        else:
            self.status_var.set(
                f"导入完成：新增 {inserted} 条，跳过重复 {duplicates} 条，失败 {failed} 条；新增待审核 {candidates} 条。")
        if self.on_imported:
            self.on_imported()

    def _finish_error(self, message, inserted):
        self.running = False
        self.import_btn.configure(state="normal")
        self.load_btn.configure(state="normal")
        suffix = f"已导入 {inserted} 条，数据保留。" if inserted else "未导入新消息。"
        self.status_var.set(f"导入中断：{message}；{suffix}")
        if self.on_imported:
            self.on_imported()

    def _close(self):
        if self.running:
            if not messagebox.askyesno("停止导入", "导入仍在进行，关闭会停止后续导入，已导入的数据会保留。确认关闭？", parent=self):
                return
        self.closed = True
        self.destroy()
