from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .api_config import API_PRESETS
from .config import data_dir
from .theme import (BLUE, BLUE_HOVER, BORDER, CARD, DANGER, TEXT, TEXT_2, TEXT_3,
                    ToggleChip, RoundedButton, RoundedLabel, ui_font)
from .version import __version__

DRAWER_WIDTH = 440
TABS = (
    ("connection", "连接"),
    ("model", "模型"),
    ("update", "更新"),
    ("data", "数据"),
)


class ScrollableFrame(tk.Frame):
    def __init__(self, parent, bg=CARD):
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.inner.bind("<Configure>", lambda _event: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda event: self.canvas.itemconfigure(
            self._window, width=event.width))
        self.bind("<Enter>", lambda _event: self.canvas.bind_all("<MouseWheel>", self._scroll))
        self.bind("<Leave>", lambda _event: self.canvas.unbind_all("<MouseWheel>"))

    def _scroll(self, event):
        self.canvas.yview_scroll(int(-event.delta / 120), "units")


class SettingsDrawer(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        self.app = app
        self._visible = False
        self._animating = False
        self._offset = 0
        self._target = 0
        self._tab = "connection"
        self._frames = {}
        self._tab_buttons = {}
        self._build()

    # ---------- layout ----------

    def _build(self):
        header = tk.Frame(self, bg=CARD)
        header.pack(fill="x", padx=22, pady=(20, 10))
        tk.Label(header, text="设置", font=ui_font(16, "bold"), bg=CARD, fg=TEXT).pack(side="left")
        tk.Label(header, text=f"v{__version__}", font=ui_font(8), bg=CARD,
                 fg=TEXT_3).pack(side="left", padx=(10, 0), pady=(5, 0))
        close = RoundedButton(header, text="×", kind="ghost", height=30, padx=10,
                              command=self.close)
        close.pack(side="right")

        self.conn_badge = RoundedLabel(header, textvariable=self.app.conn_var, fill=CARD,
                                       fg=TEXT_2, dot_color=BLUE, padx=8, pady=4, bg=CARD)
        self.conn_badge.pack(side="right", padx=(0, 10))

        line = tk.Frame(self, bg=BORDER, height=1)
        line.pack(fill="x")

        tabs = tk.Frame(self, bg=CARD)
        tabs.pack(fill="x", padx=14, pady=(10, 0))
        for key, label in TABS:
            button = RoundedButton(tabs, text=label, kind="ghost", height=30, padx=12,
                                   command=lambda name=key: self.show_tab(name))
            button.pack(side="left", padx=(0, 4))
            self._tab_buttons[key] = button

        self.scroll = ScrollableFrame(self, bg=CARD)
        self.scroll.pack(fill="both", expand=True, padx=0, pady=(8, 0))
        for key, _label in TABS:
            frame = tk.Frame(self.scroll.inner, bg=CARD)
            self._frames[key] = frame
        self._build_connection(self._frames["connection"])
        self._build_model(self._frames["model"])
        self._build_update(self._frames["update"])
        self._build_data(self._frames["data"])
        self.show_tab("connection")

        footer = tk.Frame(self, bg=CARD)
        footer.pack(fill="x", padx=22, pady=14)
        RoundedButton(footer, text="保存设置", kind="primary", height=34,
                      command=self.app.save_settings_from_drawer).pack(side="left")
        RoundedButton(footer, text="保存并连接", kind="soft", height=34,
                      command=self.app.save_and_connect).pack(side="left", padx=(8, 0))
        RoundedButton(footer, text="关闭", kind="ghost", height=34,
                      command=self.close).pack(side="right")

    def _section(self, parent, title, hint=""):
        tk.Label(parent, text=title, font=ui_font(11, "bold"), bg=CARD,
                 fg=TEXT, anchor="w").pack(fill="x", pady=(14, 2))
        if hint:
            tk.Label(parent, text=hint, font=ui_font(8), bg=CARD, fg=TEXT_3,
                     anchor="w", justify="left", wraplength=380).pack(fill="x", pady=(0, 6))

    def _label(self, parent, text):
        tk.Label(parent, text=text, font=ui_font(9), bg=CARD, fg=TEXT_2,
                 anchor="w").pack(fill="x", pady=(8, 3))

    def _entry(self, parent, variable, show=None):
        entry = ttk.Entry(parent, textvariable=variable, show=show)
        entry.pack(fill="x")
        return entry

    def _hint(self, parent, text, color=TEXT_3):
        label = tk.Label(parent, text=text, font=ui_font(8), bg=CARD, fg=color,
                         anchor="w", justify="left", wraplength=380)
        label.pack(fill="x", pady=(4, 0))
        return label

    def _toggle(self, parent, text, variable, command=None):
        chip = ToggleChip(parent, text, variable, command=command)
        chip.pack(anchor="w", pady=3)
        return chip

    # ---------- connection ----------

    def _build_connection(self, parent):
        body = tk.Frame(parent, bg=CARD)
        body.pack(fill="both", expand=True, padx=22, pady=(0, 20))
        self._section(body, "NapCat 启动与登录",
                      "Inbox 可隐藏启动 NapCat，并在应用内展示扫码登录界面。")
        self._label(body, "NapCat 安装目录")
        root_row = tk.Frame(body, bg=CARD)
        root_row.pack(fill="x")
        ttk.Entry(root_row, textvariable=self.app.napcat_root_var).pack(
            side="left", fill="x", expand=True)
        RoundedButton(root_row, text="检测", kind="ghost", height=30, padx=10,
                      command=self.app.auto_detect_napcat_root).pack(side="right", padx=(6, 0))
        self._label(body, "WebUI 地址")
        webui_row = tk.Frame(body, bg=CARD)
        webui_row.pack(fill="x")
        ttk.Entry(webui_row, textvariable=self.app.napcat_webui_url_var).pack(
            side="left", fill="x", expand=True)
        RoundedButton(webui_row, text="读取 Token", kind="soft", height=30, padx=10,
                      command=self.app.auto_read_webui_token).pack(side="right", padx=(6, 0))
        self._label(body, "WebUI Token（留空则自动读取本机配置）")
        ttk.Entry(body, textvariable=self.app.napcat_webui_token_var, show="•").pack(fill="x")
        self._toggle(body, "启动时自动拉起 NapCat", self.app.auto_launch_napcat_var)
        self._toggle(body, "有已保存账号时免扫码快速登录", self.app.auto_quick_login_var)
        RoundedButton(body, text="启动并登录 NapCat", kind="primary", height=34,
                      command=lambda: self.app.start_napcat_and_login(False)).pack(
            anchor="w", pady=(8, 0))
        self._hint(body, "扫码仍由你用手机 QQ 完成；程序只展示二维码与登录状态，不保存账号密码。")

        self._section(body, "NapCat 连接", "只允许本机地址；Token 使用 Windows DPAPI 加密保存。")
        self._label(body, "WebSocket 地址")
        self.ws_entry = self._entry(body, self.app.url_var)
        self._label(body, "Access Token（可留空）")
        self.token_entry = self._entry(body, self.app.token_var, show="•")
        self._hint(body, "NapCat 未设置 Token 时可以留空；填写后会加密保存在本机。")
        self._section(body, "接收范围")
        self._toggle(body, "接收群消息", self.app.group_var)
        self._toggle(body, "启动时自动连接", self.app.auto_connect_var)
        self._toggle(body, "启动时同步今天消息", self.app.auto_sync_var)
        self._hint(body, "群消息默认关闭。打开后，普通群聊只做本地降噪，只有候选/待回复文本才会进入分析。")

    # ---------- model ----------

    def _build_model(self, parent):
        body = tk.Frame(parent, bg=CARD)
        body.pack(fill="both", expand=True, padx=22, pady=(0, 20))
        self._section(body, "分析方式", "本地规则不调用模型；本机模型只访问 127.0.0.1。")
        mode_row = tk.Frame(body, bg=CARD)
        mode_row.pack(fill="x", pady=(2, 8))
        tk.Radiobutton(mode_row, text="本地规则", value="rules", variable=self.app.mode_var,
                       command=self.app.on_mode_change, bg=CARD, fg=TEXT, selectcolor=CARD,
                       activebackground=CARD, activeforeground=TEXT, highlightthickness=0,
                       font=ui_font(9)).pack(side="left")
        tk.Radiobutton(mode_row, text="大模型 API", value="api", variable=self.app.mode_var,
                       command=self.app.on_mode_change, bg=CARD, fg=TEXT, selectcolor=CARD,
                       activebackground=CARD, activeforeground=TEXT, highlightthickness=0,
                       font=ui_font(9)).pack(side="left", padx=(18, 0))

        self.api_fields = tk.Frame(body, bg=CARD)
        self.api_fields.pack(fill="x")
        self._label(self.api_fields, "预设")
        self.preset_box = ttk.Combobox(self.api_fields, textvariable=self.app.api_preset_var,
                                       state="readonly", values=tuple(API_PRESETS) + ("自定义",))
        self.preset_box.pack(fill="x")
        self.preset_box.bind("<<ComboboxSelected>>", lambda _event: self.app.apply_api_preset())
        self._label(self.api_fields, "API Endpoint")
        self.endpoint_entry = self._entry(self.api_fields, self.app.api_endpoint_var)
        self._label(self.api_fields, "模型名称")
        model_row = tk.Frame(self.api_fields, bg=CARD)
        model_row.pack(fill="x")
        self.model_box = ttk.Combobox(model_row, textvariable=self.app.api_model_var,
                                      state="normal")
        self.model_box.pack(side="left", fill="x", expand=True)
        self.fetch_models_btn = RoundedButton(model_row, text="拉取模型", kind="soft",
                                              height=32, padx=10,
                                              command=lambda: self.app.test_api_connection(True))
        self.fetch_models_btn.pack(side="right", padx=(8, 0))
        self._label(self.api_fields, "API Key")
        key_row = tk.Frame(self.api_fields, bg=CARD)
        key_row.pack(fill="x")
        self.key_entry = ttk.Entry(key_row, textvariable=self.app.api_key_var, show="•")
        self.key_entry.pack(side="left", fill="x", expand=True)
        self.clear_key_btn = RoundedButton(key_row, text="清除 Key", kind="ghost",
                                           height=32, padx=10,
                                           command=self.app.clear_api_key)
        self.clear_key_btn.pack(side="right", padx=(8, 0))
        self._hint(self.api_fields, "已保存的 Key 不会回显；留空表示保持不变。远程端点必须填写 Key。")
        self._toggle(self.api_fields, "我知晓远程 API 会把消息文本发送给该服务商",
                     self.app.remote_consent_var, command=self.app.on_mode_change)
        probe_row = tk.Frame(self.api_fields, bg=CARD)
        probe_row.pack(fill="x", pady=(10, 0))
        self.test_api_btn = RoundedButton(probe_row, text="测试连接", kind="primary",
                                          height=34, command=lambda: self.app.test_api_connection(False))
        self.test_api_btn.pack(side="left")
        self.probe_status = tk.Label(probe_row, text="", font=ui_font(8), bg=CARD,
                                     fg=TEXT_3, anchor="w", justify="left", wraplength=250)
        self.probe_status.pack(side="left", fill="x", expand=True, padx=(10, 0))
        self._hint(self.api_fields, "测试连接只读取模型列表，不发送聊天文本，不会产生分析费用。")
        self.rules_hint = tk.Frame(body, bg=CARD)
        tk.Label(self.rules_hint, text="本地规则模式", font=ui_font(9, "bold"),
                 bg=CARD, fg=TEXT, anchor="w").pack(fill="x")
        tk.Label(self.rules_hint,
                 text="不调用模型、零 API 费用，日常分拣够用；需要语义理解时再切换到大模型 API。",
                 font=ui_font(8), bg=CARD, fg=TEXT_3, anchor="w", justify="left",
                 wraplength=380).pack(fill="x", pady=(3, 0))
        self.refresh_mode()

    # ---------- update ----------

    def _build_update(self, parent):
        body = tk.Frame(parent, bg=CARD)
        body.pack(fill="both", expand=True, padx=22, pady=(0, 20))
        self._section(body, "版本", "更新只从本项目的 GitHub Releases 获取，不经过第三方服务。")
        version_row = tk.Frame(body, bg=CARD)
        version_row.pack(fill="x")
        tk.Label(version_row, text=f"当前版本 v{__version__}", font=ui_font(10, "bold"),
                 bg=CARD, fg=TEXT).pack(side="left")
        self.update_status = tk.Label(body, text="尚未检查更新。", font=ui_font(8), bg=CARD,
                                      fg=TEXT_3, anchor="w", justify="left", wraplength=380)
        self.update_status.pack(fill="x", pady=(8, 0))
        self.update_notes = tk.Label(body, text="", font=ui_font(8), bg=CARD, fg=TEXT_2,
                                     anchor="w", justify="left", wraplength=380)
        self.update_notes.pack(fill="x", pady=(6, 0))
        actions = tk.Frame(body, bg=CARD)
        actions.pack(fill="x", pady=(10, 0))
        self.check_update_btn = RoundedButton(actions, text="检查更新", kind="primary",
                                              height=34, command=self.app.check_updates_manual)
        self.check_update_btn.pack(side="left")
        self.apply_update_btn = RoundedButton(actions, text="立即重启并更新", kind="soft",
                                              height=34, state="disabled",
                                              command=self.app.apply_update_now)
        self.apply_update_btn.pack(side="left", padx=(8, 0))

        self._section(body, "自动更新", "小版本自动下载并在下次启动应用；大版本只提示。")
        self._toggle(body, "启动时检查更新", self.app.auto_check_updates_var)
        self._toggle(body, "自动下载更新", self.app.auto_download_updates_var)
        self._toggle(body, "下次启动自动应用", self.app.auto_apply_updates_var)
        self._hint(body, "开发目录（存在 .git）不会自动覆盖；更新包会校验 SHA256，并在替换前备份旧版本。")
        self._hint(body, "更新检查会访问 GitHub，但不会发送聊天记录、Token 或 API Key。")

    # ---------- data ----------

    def _build_data(self, parent):
        body = tk.Frame(parent, bg=CARD)
        body.pack(fill="both", expand=True, padx=22, pady=(0, 20))
        self._section(body, "本地数据", "消息、待办和课程作业只保存在本机 SQLite。")
        self._label(body, "数据目录")
        path_label = tk.Label(body, text=str(data_dir()), font=ui_font(9), bg=CARD,
                              fg=TEXT_2, anchor="w", justify="left", wraplength=380)
        path_label.pack(fill="x")
        self._hint(body, "API Key、NapCat Token 与学习通接入令牌使用 Windows DPAPI 加密保存在 secrets.dat。")
        self._section(body, "导入")
        RoundedButton(body, text="导入历史消息…", kind="ghost", height=34,
                      command=self.app.open_import_dialog).pack(anchor="w", pady=(2, 0))
        self._hint(body, "只在点击后读取本机 NapCat HTTP 接口中你指定会话的最近消息。")
        self._section(body, "清理")
        RoundedButton(body, text="清除已保存凭据", kind="ghost", height=34,
                      command=self.app.clear_credentials).pack(anchor="w", pady=(2, 6))
        RoundedButton(body, text="清空本地数据…", kind="danger", height=34,
                      command=self.app.clear_data).pack(anchor="w")
        self._hint(body, "清除凭据不会删除消息与待办；清空本地数据不可撤销。")
        self._section(body, "隐私")
        link = tk.Label(body, text="查看完整隐私说明", font=ui_font(9, "bold"),
                        bg=CARD, fg=BLUE_HOVER, cursor="hand2", anchor="w")
        link.pack(fill="x", pady=(2, 0))
        link.bind("<Button-1>", lambda _event: self.app.show_privacy())

    # ---------- state ----------

    def show_tab(self, name):
        if name not in self._frames:
            return
        self._tab = name
        for key, frame in self._frames.items():
            if key == name:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()
        for key, button in self._tab_buttons.items():
            button.configure(text=dict(TABS)[key])
            button.configure(kind="primary" if key == name else "ghost")
        self.scroll.canvas.yview_moveto(0)

    def refresh_mode(self):
        api_mode = self.app.mode_var.get() == "api"
        if api_mode:
            self.api_fields.pack(fill="x")
            self.rules_hint.pack_forget()
        else:
            self.api_fields.pack_forget()
            self.rules_hint.pack(fill="x", pady=(8, 0))
        for button in (self.fetch_models_btn, self.test_api_btn, self.clear_key_btn):
            button.configure(state="normal" if api_mode else "disabled")

    def set_probe_running(self):
        self.probe_status.configure(text="正在测试连接…", fg=TEXT_3)
        for button in (self.fetch_models_btn, self.test_api_btn):
            button.configure(state="disabled")

    def set_probe_result(self, result):
        color = BLUE_HOVER if result.ok else DANGER
        self.probe_status.configure(text=result.message, fg=color)
        if result.models:
            self.model_box.configure(values=result.models)
            if not self.app.api_model_var.get().strip():
                self.app.api_model_var.set(result.models[0])
        self.refresh_mode()

    def set_update_status(self, text, color=TEXT_3):
        self.update_status.configure(text=text, fg=color)

    def set_update_info(self, info, staged=False):
        self.update_notes.configure(text=info.notes[:1200] if info.notes else "")
        if staged:
            self.set_update_status(f"v{info.version} 已下载，下次启动自动应用。", BLUE_HOVER)
            self.apply_update_btn.configure(state="normal")
        else:
            self.set_update_status(f"发现新版本 v{info.version}。", BLUE_HOVER)

    def set_update_checked(self):
        self.update_notes.configure(text="")
        self.apply_update_btn.configure(state="disabled")
        self.set_update_status("已是最新版本。", TEXT_2)

    def set_update_error(self, message):
        self.set_update_status(f"检查更新失败：{message}", DANGER)

    def open(self):
        if self._visible:
            return
        self._visible = True
        self._offset = 0
        self.place(relx=1.0, rely=0, relheight=1.0, width=DRAWER_WIDTH, x=0)
        self.lift()
        self._slide_to(-DRAWER_WIDTH)
        self.app.settings_toggle_btn.configure(text="收起设置")
        self.refresh_mode()
        pending = self.app.update_service.refresh_pending()
        if pending is not None:
            self.set_update_info(pending.info, staged=True)

    def close(self):
        if not self._visible:
            return
        self._visible = False
        self._slide_to(0, hide=True)
        self.app.settings_toggle_btn.configure(text="设置")

    def toggle(self):
        if self._visible:
            self.close()
        else:
            self.open()

    def _slide_to(self, target, hide=False):
        self._target = target
        if self._animating:
            return
        self._animating = True

        def tick():
            if abs(self._offset - self._target) <= 24:
                self._offset = self._target
                self.place_configure(x=self._offset)
                self._animating = False
                if hide and not self._visible:
                    self.place_forget()
                return
            step = 48 if self._target > self._offset else -48
            self._offset += step
            self.place_configure(x=self._offset)
            self.after(12, tick)

        tick()
