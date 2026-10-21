from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
import webbrowser

import qrcode

from .theme import BLUE_HOVER, BORDER, CARD, DANGER, SUCCESS, TEXT, TEXT_2, TEXT_3, WARNING, RoundedButton, ui_font

QR_BOX = 264


class NapCatLoginDialog(tk.Toplevel):
    """Shows NapCat's QQ login QR code inside the app; the user still scans with their phone."""

    def __init__(self, parent, webui, on_logged_in, on_cancel=None):
        super().__init__(parent)
        self.webui = webui
        self.on_logged_in = on_logged_in
        self.on_cancel = on_cancel
        self.closed = False
        self._queue: queue.Queue = queue.Queue()
        self._refresh_requested = False
        self._quick_uin = None
        self.title("登录 QQ · NapCat")
        self.geometry("430x620")
        self.configure(bg=CARD)
        self.resizable(False, False)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self._build()
        self._start_worker()
        self.after(250, self._drain)

    def _build(self):
        head = tk.Frame(self, bg=CARD)
        head.pack(fill="x", padx=24, pady=(20, 6))
        tk.Label(head, text="扫码登录 QQ", font=ui_font(15, "bold"), bg=CARD,
                 fg=TEXT).pack(anchor="w")
        tk.Label(head, text="二维码来自本机 NapCat；请用手机 QQ 扫码，程序不会代替你登录。",
                 font=ui_font(8), bg=CARD, fg=TEXT_3, anchor="w", justify="left",
                 wraplength=380).pack(anchor="w", pady=(4, 0))

        self.qr_frame = tk.Frame(self, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        self.qr_frame.pack(pady=(10, 6))
        self.qr_canvas = tk.Canvas(self.qr_frame, width=QR_BOX, height=QR_BOX,
                                   bg="white", highlightthickness=0)
        self.qr_canvas.pack(padx=8, pady=8)
        self.qr_hint = tk.Label(self.qr_canvas, text="正在获取二维码…", font=ui_font(9),
                                bg="white", fg=TEXT_3)
        self.qr_hint.place(relx=0.5, rely=0.5, anchor="center")

        self.status_label = tk.Label(self, text="等待 NapCat 返回二维码…", font=ui_font(9),
                                     bg=CARD, fg=TEXT_2, anchor="w", justify="left",
                                     wraplength=380)
        self.status_label.pack(fill="x", padx=24, pady=(4, 8))

        self.quick_frame = tk.Frame(self, bg=CARD)
        self.quick_label = tk.Label(self.quick_frame, text="已保存账号可免扫码：",
                                    font=ui_font(8), bg=CARD, fg=TEXT_3, anchor="w")
        self.quick_label.pack(anchor="w")
        self.quick_buttons = tk.Frame(self.quick_frame, bg=CARD)
        self.quick_buttons.pack(anchor="w")

        actions = tk.Frame(self, bg=CARD)
        actions.pack(fill="x", padx=24, pady=(6, 20))
        RoundedButton(actions, text="刷新二维码", kind="soft", height=34,
                      command=self.request_refresh).pack(side="left")
        RoundedButton(actions, text="重试", kind="ghost", height=34,
                      command=self._retry).pack(side="left", padx=(8, 0))
        link = tk.Label(actions, text="打开 NapCat 控制台", font=ui_font(8, "bold"),
                        bg=CARD, fg=BLUE_HOVER, cursor="hand2")
        link.pack(side="right")
        link.bind("<Button-1>", lambda _event: webbrowser.open(f"{self.webui.base}/webui"))
        RoundedButton(actions, text="取消", kind="ghost", height=34,
                      command=self._cancel).pack(side="right", padx=(0, 10))

    # ---------- worker ----------

    def _start_worker(self):
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        try:
            qr = self.webui.get_qrcode()
        except Exception as exc:
            self._queue.put(("error", str(exc)))
            return
        self._queue.put(("qr", qr))
        self._load_quick_accounts()
        while not self.closed:
            if self._refresh_requested:
                self._refresh_requested = False
                try:
                    url, _restarting = self.webui.refresh_qrcode()
                    if url:
                        self._queue.put(("qr", url))
                except Exception as exc:
                    self._queue.put(("error", str(exc)))
            if self._quick_uin:
                uin, self._quick_uin = self._quick_uin, None
                try:
                    self.webui.set_quick_login(uin)
                    self._queue.put(("info", "正在使用已保存账号快速登录…"))
                except Exception as exc:
                    self._queue.put(("error", str(exc)))
            try:
                status = self.webui.check_status()
            except Exception as exc:
                self._queue.put(("error", str(exc)))
                time.sleep(2)
                continue
            self._queue.put(("status", status))
            if status.is_login:
                self._queue.put(("logged_in", None))
                return
            time.sleep(2)

    def _load_quick_accounts(self):
        try:
            accounts = self.webui.quick_login_list()
        except Exception:
            accounts = []
        self._queue.put(("accounts", accounts))

    # ---------- ui events ----------

    def request_refresh(self):
        self._refresh_requested = True

    def _retry(self):
        self.status_label.configure(text="正在重新连接 NapCat…", fg=TEXT_2)
        self._start_worker()

    def request_quick_login(self, uin: str):
        self._quick_uin = uin

    def _drain(self):
        if self.closed:
            return
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                if kind == "qr":
                    self._render_qr(payload)
                elif kind == "accounts":
                    self._render_accounts(payload)
                elif kind == "info":
                    self.status_label.configure(text=payload, fg=TEXT_2)
                elif kind == "error":
                    self.status_label.configure(text=payload, fg=DANGER)
                elif kind == "status":
                    self._render_status(payload)
                elif kind == "logged_in":
                    self._finish()
                    return
        except queue.Empty:
            pass
        self.after(250, self._drain)

    def _render_qr(self, value: str):
        self.qr_canvas.delete("all")
        self.qr_hint.place_forget()
        if not value:
            self.qr_hint.place(relx=0.5, rely=0.5, anchor="center")
            return
        qr = qrcode.QRCode(border=1)
        qr.add_data(value)
        qr.make(fit=True)
        matrix = qr.get_matrix()
        cells = len(matrix)
        cell = max(2, QR_BOX // (cells + 2))
        offset = (QR_BOX - cell * cells) // 2
        for row_index, row in enumerate(matrix):
            for col_index, dark in enumerate(row):
                if dark:
                    x0 = offset + col_index * cell
                    y0 = offset + row_index * cell
                    self.qr_canvas.create_rectangle(x0, y0, x0 + cell, y0 + cell,
                                                    fill="black", outline="black")
        self.status_label.configure(text="请用手机版 QQ 扫描二维码，并在手机上确认登录。", fg=TEXT_2)

    def _render_accounts(self, accounts):
        for child in self.quick_buttons.winfo_children():
            child.destroy()
        if not accounts:
            self.quick_frame.pack_forget()
            return
        self.quick_frame.pack(fill="x", padx=24, pady=(0, 4))
        for account in accounts[:4]:
            RoundedButton(self.quick_buttons, text=account["nick"], kind="ghost", height=30,
                          padx=10,
                          command=lambda uin=account["uin"]: self.request_quick_login(uin)
                          ).pack(side="left", padx=(0, 6))

    def _render_status(self, status):
        if status.is_login:
            self.status_label.configure(text="登录成功，正在进入事务中心…", fg=SUCCESS)
            return
        phase = status.phase
        if status.error:
            text = status.error
            color = DANGER
            if ("过期" in text or "失效" in text) and not self._refresh_requested:
                self._refresh_requested = True
                text = "二维码已过期，正在刷新…"
                color = WARNING
        elif phase == "qrcode_scanned":
            text, color = "已扫码，请在手机上确认登录。", WARNING
        elif phase == "reconnecting":
            text, color = "登录中，请稍候…", WARNING
        elif phase == "ready":
            text, color = "登录成功，正在进入事务中心…", SUCCESS
        else:
            text, color = "请用手机版 QQ 扫描二维码，并在手机上确认登录。", TEXT_2
        self.status_label.configure(text=text, fg=color)

    def _finish(self):
        self.closed = True
        callback = self.on_logged_in
        self.destroy()
        if callback:
            callback()

    def _cancel(self):
        self.closed = True
        callback = self.on_cancel
        self.destroy()
        if callback:
            callback()
