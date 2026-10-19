from __future__ import annotations
import tkinter as tk
from datetime import date
from tkinter import ttk
from .store import dashboard_counts, list_priority_items
from .timeparse import format_due_display
from .theme import (AMBER_SOFT, BG, BLUE, BLUE_HOVER, BLUE_SOFT, BORDER, CARD,
                    DANGER, PINK, PINK_SOFT, RADIUS_LG, RED_SOFT, TEXT, TEXT_2,
                    TEXT_3, WARNING, RoundedButton, RoundedFrame, RoundedLabel,
                    ui_font)

WEEKDAYS = ("一", "二", "三", "四", "五", "六", "日")


class DashboardFrame(tk.Frame):
    def __init__(self, parent, on_detail, on_confirm, on_dismiss, on_complete):
        super().__init__(parent, bg=BG)
        self.on_detail = on_detail
        self.on_confirm = on_confirm
        self.on_dismiss = on_dismiss
        self.on_complete = on_complete
        self.selected = None
        self.card_vars = {}
        self._build()
        self.refresh()

    def _build(self):
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", pady=(0, 16))
        title_row = tk.Frame(header, bg=BG)
        title_row.pack(fill="x")
        tk.Label(title_row, text="事务中心", font=ui_font(20, "bold"),
                 bg=BG, fg=TEXT).pack(side="left")
        self.date_var = tk.StringVar()
        tk.Label(title_row, textvariable=self.date_var, font=ui_font(9),
                 bg=BG, fg=TEXT_3).pack(side="left", padx=(12, 0), pady=(8, 0))
        self.today_messages_var = tk.StringVar(value="今日消息 0 条")
        self.today_chip = RoundedLabel(title_row, textvariable=self.today_messages_var,
                                       fill=BLUE_SOFT, fg=BLUE_HOVER, bg=BG,
                                       padx=10, pady=5)
        self.today_chip.pack(side="right")
        sub_row = tk.Frame(header, bg=BG)
        sub_row.pack(fill="x", pady=(6, 0))
        tk.Label(sub_row, text="只列需要你处理的事", font=ui_font(9),
                 bg=BG, fg=TEXT_2).pack(side="left", pady=(3, 0))
        RoundedLabel(sub_row, text="本地分拣 · 人工确认", fill=PINK_SOFT, fg=PINK,
                     bg=BG, padx=9, pady=4).pack(side="left", padx=(12, 0))

        cards = tk.Frame(self, bg=BG)
        cards.pack(fill="x", pady=(0, 16))
        specs = (
            ("today_todos", "今日待办", "已确认且截止日期为今天",
             BLUE, BLUE_SOFT, "今"),
            ("pending_replies", "待回复", "需要你回应的活跃事项",
             PINK, PINK_SOFT, "回"),
            ("competitions_projects", "比赛与项目", "进行中的比赛、项目事项",
             WARNING, AMBER_SOFT, "赛"),
            ("pending_invites", "待确认邀约", "尚未确认的见面邀约",
             BLUE_HOVER, "#EDF2FE", "约"),
        )
        for index, (key, title, hint, accent_color, tint, glyph) in enumerate(specs):
            cards.columnconfigure(index, weight=1, uniform="stat")
            outer = RoundedFrame(cards, radius=16, fill=CARD, outline=BORDER, bg=BG)
            outer.grid(row=0, column=index, sticky="nsew",
                       padx=(0, 12) if index < len(specs) - 1 else 0)
            body = tk.Frame(outer.content, bg=CARD)
            body.pack(fill="both", expand=True, padx=15, pady=(13, 11))
            head = tk.Frame(body, bg=CARD)
            head.pack(fill="x")
            tk.Label(head, text=title, font=ui_font(9), bg=CARD,
                     fg=TEXT_2).pack(side="left")
            bubble = RoundedFrame(head, radius=9, fill=tint, outline="", bg=CARD)
            bubble.pack(side="right")
            tk.Label(bubble.content, text=glyph, font=ui_font(9, "bold"),
                     bg=tint, fg=accent_color).pack(padx=4, pady=1)
            value = tk.StringVar(value="0")
            self.card_vars[key] = value
            tk.Label(body, textvariable=value, font=ui_font(24, "bold"),
                     bg=CARD, fg=TEXT).pack(anchor="w", pady=(4, 0))
            tk.Label(body, text=hint, font=ui_font(8), bg=CARD,
                     fg=TEXT_3).pack(anchor="w")
            for widget in (outer, body):
                widget.bind("<Enter>", lambda _event, frame=outer, color=accent_color:
                            frame.set_outline(color))
                widget.bind("<Leave>", lambda _event, frame=outer:
                            frame.set_outline(BORDER))

        section = RoundedFrame(self, radius=RADIUS_LG, fill=CARD,
                               outline=BORDER, bg=BG)
        section.pack(fill="both", expand=True)
        content = section.content
        head = tk.Frame(content, bg=CARD)
        head.pack(fill="x", padx=18, pady=(14, 10))
        tk.Label(head, text="优先处理", font=ui_font(13, "bold"),
                 bg=CARD, fg=TEXT).pack(side="left")
        self.count_var = tk.StringVar(value="0 条")
        self.count_chip = RoundedLabel(head, textvariable=self.count_var, fill=BG,
                                       fg=TEXT_2, bg=CARD, padx=9, pady=3)
        self.count_chip.pack(side="left", padx=(9, 0))
        tk.Label(head, text="按优先级排序，最多 12 条", font=ui_font(9),
                 bg=CARD, fg=TEXT_3).pack(side="right")

        separator = tk.Frame(content, bg="#F0F0F2", height=1)
        separator.pack(fill="x")

        actions = tk.Frame(content, bg=CARD)
        actions.pack(fill="x", padx=18, pady=(10, 10))
        self.detail_btn = RoundedButton(actions, text="查看详情", kind="ghost",
                                        command=self._detail, state="disabled")
        self.confirm_btn = RoundedButton(actions, text="确认加入待办", kind="primary",
                                         command=self._confirm, state="disabled")
        self.dismiss_btn = RoundedButton(actions, text="忽略此候选", kind="danger",
                                         command=self._dismiss, state="disabled")
        self.complete_btn = RoundedButton(actions, text="标记完成", kind="primary",
                                          command=self._complete, state="disabled")
        for button in (self.detail_btn, self.confirm_btn, self.dismiss_btn, self.complete_btn):
            button.pack(side="left", padx=(0, 8))
        tk.Label(actions, text="待确认事项不会自动进入待办", font=ui_font(8),
                 bg=CARD, fg=TEXT_3).pack(side="right")

        holder = tk.Frame(content, bg=CARD)
        holder.pack(fill="both", expand=True, padx=(18, 8), pady=(0, 14))
        columns = ("priority", "state", "contact", "category", "title", "due")
        self.tree = ttk.Treeview(holder, columns=columns, show="headings",
                                 selectmode="browse", height=6)
        headings = (("priority", "优先级", 62, False), ("state", "状态", 72, False),
                    ("contact", "联系人/群", 175, False), ("category", "分类", 150, False),
                    ("title", "事项", 300, True), ("due", "截止/提示", 185, False))
        for column, text, width, stretch in headings:
            self.tree.heading(column, text=text)
            self.tree.column(column, width=width, minwidth=50, stretch=stretch)
        self.tree.tag_configure("P0", foreground=DANGER)
        self.tree.tag_configure("P1", foreground=WARNING)
        self.tree.tag_configure("pending", background=AMBER_SOFT)
        self.tree.tag_configure("overdue", background=RED_SOFT)
        scrollbar = ttk.Scrollbar(holder, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        holder.rowconfigure(0, weight=1)
        holder.columnconfigure(0, weight=1)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", lambda _event: self._detail())

        self.empty_state = tk.Frame(holder, bg=CARD)
        tk.Label(self.empty_state, text="今天没有需要处理的事务", font=ui_font(12, "bold"),
                 bg=CARD, fg=TEXT_2).pack()
        tk.Label(self.empty_state, text="新消息会出现在这里；也可以先同步今天的消息",
                 font=ui_font(9), bg=CARD, fg=TEXT_3).pack(pady=(6, 0))

    def refresh(self):
        counts = dashboard_counts()
        for key, value in self.card_vars.items():
            value.set(str(counts.get(key, 0)))
        today = date.today()
        self.date_var.set(f"{today.month}月{today.day}日 · 星期{WEEKDAYS[today.weekday()]}")
        self.today_messages_var.set(f"今日消息 {counts.get('today_messages', 0)} 条")
        today_iso = today.isoformat()
        for item in self.tree.get_children():
            self.tree.delete(item)
        items = list_priority_items(12)
        for row in items:
            status = row["status"]
            tags = [row["priority"]]
            if status == "pending_review":
                tags.append("pending")
            due_text = format_due_display(row["due_date"], row["due_display"], row["due_hint"])
            if row["due_date"] and row["due_date"] < today_iso:
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
        self.count_var.set(f"{len(items)} 条")
        if items:
            self.empty_state.place_forget()
        else:
            self.empty_state.place(relx=0.5, rely=0.5, anchor="center")
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
