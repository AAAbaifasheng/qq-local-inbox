from __future__ import annotations
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk
from .theme import (BG, BLUE, BLUE_HOVER, BLUE_SOFT, BORDER, CARD, RADIUS_LG,
                    TEXT, TEXT_2, TEXT_3, RoundedBar, RoundedButton, RoundedFrame,
                    RoundedLabel, ui_font)


class ChaoxingAccessDialog(tk.Toplevel):
    """Shows the userscript and explains the loopback-only bridge."""

    def __init__(self, parent, script_text: str, port: int, running: bool,
                 error: str = "", on_reset_token=None):
        super().__init__(parent)
        self.title("接入学习通 · 只读桥")
        self.geometry("820x680")
        self.minsize(720, 580)
        self.configure(bg=BG)
        self.transient(parent)
        self.script_text = script_text
        self.port = port
        self.running = running
        self.error = error
        self.on_reset_token = on_reset_token
        self.closed = False
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.bind("<Escape>", lambda _event: self._close())

    def _build(self):
        accent_row = tk.Frame(self, bg=CARD)
        accent_row.pack(fill="x", pady=(10, 0))
        RoundedBar(accent_row, width=44, height=4, fill=BLUE, bg=CARD).pack(anchor="center")

        header = tk.Frame(self, bg=CARD)
        header.pack(fill="x")
        title_box = tk.Frame(header, bg=CARD)
        title_box.pack(side="left", padx=22, pady=(12, 12))
        tk.Label(title_box, text="接入学习通", font=ui_font(16, "bold"),
                 bg=CARD, fg=TEXT).pack(anchor="w")
        tk.Label(title_box, text="油猴脚本只读作业列表 → 本机接收服务",
                 font=ui_font(8), bg=CARD, fg=TEXT_3).pack(anchor="w", pady=(3, 0))
        RoundedLabel(header, text="只读 · 本机", fill=BLUE_SOFT, fg=BLUE_HOVER,
                     bg=CARD, padx=10, pady=4).pack(side="right", padx=22, pady=16)

        content = tk.Frame(self, bg=BG)
        content.pack(fill="both", expand=True, padx=20, pady=(14, 0))

        self.note_card = RoundedFrame(content, radius=14, fill=BLUE_SOFT, outline="",
                                      bg=BG, padding=5)
        self.note_card.pack(fill="x")
        self.note_label = tk.Label(
            self.note_card.content, bg=BLUE_SOFT, fg=TEXT_2, font=ui_font(9),
            justify="left", anchor="w", wraplength=700,
            text=("不保存学习通账号或密码，不读取 Cookie，不下载附件，不自动提交。"
                  "脚本只把作业标题、课程名、截止时间、平台状态和作业链接发送到本机。"))
        self.note_label.pack(fill="x", padx=12, pady=8)

        status_card = RoundedFrame(content, radius=12, fill=CARD, outline=BORDER, bg=BG)
        status_card.pack(fill="x", pady=(10, 0))
        self.status_label = tk.Label(
            status_card.content, bg=CARD, fg=TEXT_2, font=ui_font(9),
            justify="left", anchor="w", wraplength=700)
        self.status_label.pack(fill="x", padx=14, pady=9)
        self._render_status()

        guide = RoundedFrame(content, radius=RADIUS_LG, fill=CARD, outline=BORDER, bg=BG)
        guide.pack(fill="both", expand=True, pady=(10, 0))
        body = tk.Frame(guide.content, bg=CARD)
        body.pack(fill="both", expand=True, padx=16, pady=12)

        tk.Label(body, text="使用步骤", font=ui_font(11, "bold"),
                 bg=CARD, fg=TEXT).pack(anchor="w")
        steps = (
            "1. 给浏览器安装 Tampermonkey 或 Violentmonkey。\n"
            "2. 点“复制脚本”，在脚本管理器里新建脚本，粘贴并保存。\n"
            "3. 打开学习通并登录，进入课程作业页；“我学的课”页面可用“全部课程”。\n"
            "4. 网页右下角出现“QQ Local Inbox”面板后，点“同步当前页”。\n"
            "5. 回到本程序“课程作业”页查看，确认后才进入待办。"
        )
        tk.Label(body, text=steps, font=ui_font(9), bg=CARD, fg=TEXT_2,
                 justify="left", anchor="w").pack(fill="x", pady=(6, 10))

        actions = tk.Frame(body, bg=CARD)
        actions.pack(fill="x", pady=(0, 8))
        RoundedButton(actions, text="复制脚本", kind="primary", height=34, padx=16,
                      command=self._copy_script).pack(side="left")
        RoundedButton(actions, text="打开学习通", kind="ghost", height=34, padx=14,
                      command=self._open_chaoxing).pack(side="left", padx=(8, 0))
        RoundedButton(actions, text="重置接入令牌", kind="danger", height=34, padx=14,
                      command=self._reset_token).pack(side="left", padx=(8, 0))
        RoundedButton(actions, text="关闭", kind="ghost", height=34, padx=14,
                      command=self._close).pack(side="right")

        tk.Label(body, text="完整脚本（包含仅限本机的接入令牌，请勿分享）",
                 font=ui_font(9, "bold"), bg=CARD, fg=TEXT).pack(anchor="w", pady=(4, 4))
        holder = RoundedFrame(body, radius=12, fill=CARD, outline=BORDER, bg=CARD)
        holder.pack(fill="both", expand=True)
        self.script_box = tk.Text(
            holder.content, wrap="none", font=("Consolas", 9), bg=CARD, fg=TEXT,
            relief="flat", bd=0, padx=10, pady=8, insertbackground=TEXT,
            selectbackground=BLUE_SOFT, selectforeground=TEXT)
        yscroll = ttk.Scrollbar(holder.content, orient="vertical", command=self.script_box.yview)
        xscroll = ttk.Scrollbar(holder.content, orient="horizontal", command=self.script_box.xview)
        self.script_box.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.script_box.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        holder.content.rowconfigure(0, weight=1)
        holder.content.columnconfigure(0, weight=1)
        self._render_script()

    def _render_status(self):
        if self.running:
            text = (f"本机接收服务已启动：127.0.0.1:{self.port}\n"
                    "仅接受带令牌的本机请求；作业内容只写入本机 SQLite。")
            color = TEXT_2
        else:
            text = (f"本机接收服务未启动。{self.error or ''}\n"
                    "端口可能被占用；关闭占用程序后重启本程序，或重新复制脚本以使用新端口。")
            color = "#8A5A00"
        self.status_label.configure(text=text, fg=color)

    def _render_script(self):
        self.script_box.configure(state="normal")
        self.script_box.delete("1.0", "end")
        self.script_box.insert("1.0", self.script_text)
        self.script_box.configure(state="disabled")

    def _copy_script(self):
        self.clipboard_clear()
        self.clipboard_append(self.script_text)
        self.update()
        self.status_label.configure(
            text=(f"脚本已复制到剪贴板。打开 Tampermonkey 新建脚本并粘贴保存。\n"
                  f"本机接收地址：127.0.0.1:{self.port}"),
            fg=TEXT_2)

    @staticmethod
    def _open_chaoxing():
        webbrowser.open("https://i.chaoxing.com/")

    def _reset_token(self):
        if self.on_reset_token is None:
            return
        if not messagebox.askyesno(
                "重置接入令牌",
                "重置后，旧脚本会立即失效；需要在 Tampermonkey 中重新粘贴新脚本。确认继续？",
                parent=self):
            return
        try:
            script_text, port, running, error = self.on_reset_token()
        except Exception as exc:
            messagebox.showerror("重置失败", str(exc)[:200], parent=self)
            return
        self.script_text = script_text
        self.port = port
        self.running = running
        self.error = error
        self._render_script()
        self._render_status()
        self.status_label.configure(
            text=(f"已重置接入令牌。旧脚本已失效，请重新复制并粘贴新脚本。\n"
                  f"本机接收地址：127.0.0.1:{port}"),
            fg=TEXT_2)

    def _close(self):
        self.closed = True
        self.destroy()
