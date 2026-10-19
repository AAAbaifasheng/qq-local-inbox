from __future__ import annotations
import tkinter as tk
from datetime import date
from tkinter import ttk
from .store import dashboard_counts, list_priority_items

PAGE_BG = "#f4f5f7"
CARD_BG = "#ffffff"
BORDER = "#e3e5e8"
TEXT = "#1f2329"
MUTED = "#6b7078"
FONT = "Microsoft YaHei UI"

class DashboardFrame(tk.Frame):
    def __init__(self, parent, on_detail, on_confirm, on_dismiss, on_complete):
        super().__init__(parent, bg=PAGE_BG)
        self.on_detail = on_detail
        self.on_confirm = on_confirm
        self.on_dismiss = on_dismiss
        self.on_complete = on_complete
        self.selected = None
        self.card_vars = {}
        self._build()
        self.refresh()

    def _build(self):
        header = tk.Frame(self, bg=PAGE_BG)
        header.pack(fill="x", padx=12, pady=(12, 10))
        tk.Label(header, text="我的事务中心", font=(FONT, 17, "bold"),
                 bg=PAGE_BG, fg=TEXT).pack(side="left")
        tk.Label(header, text="只列需要你处理的事", font=(FONT, 9),
                 bg=PAGE_BG, fg=MUTED).pack(side="left", padx=(10, 0), pady=(6, 0))
        self.today_messages_var = tk.StringVar(value="今日消息 0 条")
        tk.Label(header, textvariable=self.today_messages_var, font=(FONT, 9),
                 bg=PAGE_BG, fg=MUTED).pack(side="left", padx=(12, 0), pady=(6, 0))
        tk.Label(header, text="本地分拣 · 人工确认", font=(FONT, 9),
                 bg="#eef3ff", fg="#3b6ef6", padx=9, pady=3).pack(side="right")

        cards = tk.Frame(self, bg=PAGE_BG)
        cards.pack(fill="x", padx=12)
        cards.columnconfigure(0, weight=1)
        cards.columnconfigure(1, weight=1)
        specs = (
            ("today_todos", "今日待办", "已确认且截止日期为今天"),
            ("pending_replies", "待回复", "需要你回应的活跃事项"),
            ("competitions_projects", "比赛与项目", "进行中的比赛、项目事项"),
            ("pending_invites", "待确认邀约", "尚未确认的见面邀约"),
        )
        for index, (key, title, hint) in enumerate(specs):
            card = tk.Frame(cards, bg=CARD_BG, highlightthickness=1, highlightbackground=BORDER)
            card.grid(row=index // 2, column=index % 2, sticky="nsew",
                      padx=(0, 10) if index % 2 == 0 else (0, 0), pady=(0, 10))
            row = tk.Frame(card, bg=CARD_BG)
            row.pack(fill="x", padx=14, pady=(9, 0))
            tk.Label(row, text=title, font=(FONT, 10), bg=CARD_BG, fg=MUTED).pack(side="left", pady=(6, 0))
            value = tk.StringVar(value="0")
            self.card_vars[key] = value
            tk.Label(row, textvariable=value, font=(FONT, 22, "bold"), bg=CARD_BG, fg=TEXT).pack(side="right")
            tk.Label(card, text=hint, font=(FONT, 8), bg=CARD_BG, fg=MUTED).pack(anchor="w", padx=14, pady=(0, 8))

        section = tk.Frame(self, bg=CARD_BG, highlightthickness=1, highlightbackground=BORDER)
        section.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        head = tk.Frame(section, bg=CARD_BG)
        head.pack(fill="x", padx=14, pady=(12, 4))
        tk.Label(head, text="优先处理", font=(FONT, 12, "bold"), bg=CARD_BG, fg=TEXT).pack(side="left")
        self.hint_label = tk.Label(head, text="按优先级排序，最多 12 条", font=(FONT, 8), bg=CARD_BG, fg=MUTED)
        self.hint_label.pack(side="right")

        actions = tk.Frame(section, bg=CARD_BG)
        actions.pack(side="bottom", fill="x", padx=14, pady=(6, 12))
        self.detail_btn = ttk.Button(actions, text="查看详情", command=self._detail, state="disabled")
        self.confirm_btn = ttk.Button(actions, text="确认加入待办", command=self._confirm, state="disabled")
        self.dismiss_btn = ttk.Button(actions, text="忽略此候选", command=self._dismiss, state="disabled")
        self.complete_btn = ttk.Button(actions, text="标记完成", command=self._complete, state="disabled")
        for button in (self.detail_btn, self.confirm_btn, self.dismiss_btn, self.complete_btn):
            button.pack(side="left", padx=(0, 6))
        tk.Label(actions, text="待确认事项不会自动进入待办", font=(FONT, 8),
                 bg=CARD_BG, fg=MUTED).pack(side="right")

        holder = tk.Frame(section, bg=CARD_BG)
        holder.pack(fill="both", expand=True, padx=12)
        columns = ("priority", "state", "contact", "category", "title", "due")
        self.tree = ttk.Treeview(holder, columns=columns, show="headings", selectmode="browse", height=6)
        headings = (("priority", "优先级", 65, False), ("state", "状态", 70, False),
                    ("contact", "联系人/群", 170, False), ("category", "分类", 150, False),
                    ("title", "事项", 330, True), ("due", "截止/提示", 180, False))
        for column, text, width, stretch in headings:
            self.tree.heading(column, text=text)
            self.tree.column(column, width=width, minwidth=50, stretch=stretch)
        self.tree.tag_configure("P0", foreground="#c0392b")
        self.tree.tag_configure("P1", foreground="#b45309")
        self.tree.tag_configure("pending", background="#fff8e1")
        self.tree.tag_configure("overdue", background="#fee2e2")
        scrollbar = ttk.Scrollbar(holder, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        holder.rowconfigure(0, weight=1)
        holder.columnconfigure(0, weight=1)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", lambda _event: self._detail())

    def refresh(self):
        counts = dashboard_counts()
        for key, value in self.card_vars.items():
            value.set(str(counts.get(key, 0)))
        self.today_messages_var.set(f"今日消息 {counts.get('today_messages', 0)} 条")
        today = date.today().isoformat()
        for item in self.tree.get_children():
            self.tree.delete(item)
        items = list_priority_items(12)
        for row in items:
            status = row["status"]
            tags = [row["priority"]]
            if status == "pending_review":
                tags.append("pending")
            due_text = row["due_display"] or row["due_hint"] or "待核对"
            if row["due_date"] and row["due_date"] < today:
                due_text = "逾期 · " + due_text
                tags.append("overdue")
            self.tree.insert("", "end", iid=f"{status}:{row['id']}", tags=tuple(tags), values=(
                row["priority"],
                "待确认" if status == "pending_review" else "已确认",
                row["chat_label"],
                row["category"],
                row["title"][:120],
                due_text,
            ))
        self.selected = None
        self._update_buttons()

    def _on_select(self, _event=None):
        selection = self.tree.selection()
        if not selection:
            self.selected = None
        else:
            status, todo_id = selection[0].split(":", 1)
            self.selected = (status, int(todo_id))
        self._update_buttons()

    def _update_buttons(self):
        if self.selected is None:
            self.detail_btn.configure(state="disabled")
            self.confirm_btn.configure(state="disabled")
            self.dismiss_btn.configure(state="disabled")
            self.complete_btn.configure(state="disabled")
            return
        status, _todo_id = self.selected
        self.detail_btn.configure(state="normal")
        pending = status == "pending_review"
        self.confirm_btn.configure(state="normal" if pending else "disabled")
        self.dismiss_btn.configure(state="normal" if pending else "disabled")
        self.complete_btn.configure(state="normal" if status == "confirmed" else "disabled")

    def _detail(self):
        if self.selected:
            self.on_detail(*self.selected)

    def _confirm(self):
        if self.selected:
            self.on_confirm(self.selected[1])

    def _dismiss(self):
        if self.selected:
            self.on_dismiss(self.selected[1])

    def _complete(self):
        if self.selected:
            self.on_complete(self.selected[1])
