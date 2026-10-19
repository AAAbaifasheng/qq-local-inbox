from __future__ import annotations
import math
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

# Bilibili accents, softened with the neutral palette and radii of vibe-hub.
BLUE = "#00AEEC"
BLUE_HOVER = "#00A1D6"
BLUE_SOFT = "#E9F8FE"
PINK = "#FB7299"
PINK_HOVER = "#E45C86"
PINK_SOFT = "#FFF1F6"
BG = "#F7F8FA"
CARD = "#FFFFFF"
CARD_ALT = "#FAFBFC"
BORDER = "#E8E9EC"
BORDER_HOVER = "#D6D9DE"
TEXT = "#23262C"
TEXT_2 = "#5F646E"
TEXT_3 = "#8E949E"
SUCCESS = "#21A96B"
WARNING = "#FF8A00"
DANGER = "#F56C6C"
AMBER_SOFT = "#FFF8EC"
RED_SOFT = "#FFF2F1"
FONT = "Microsoft YaHei UI"
RADIUS_SM = 10
RADIUS = 14
RADIUS_LG = 18


def ui_font(size=10, weight="normal"):
    return (FONT, size, weight)


def configure_styles(root):
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(".", font=ui_font(10), background=BG, foreground=TEXT)
    style.configure("TFrame", background=BG)
    style.configure("Card.TFrame", background=CARD)
    style.configure("TLabel", background=BG, foreground=TEXT)
    style.configure("Muted.TLabel", background=BG, foreground=TEXT_2)
    style.configure("Card.TLabel", background=CARD, foreground=TEXT)
    style.configure("CardMuted.TLabel", background=CARD, foreground=TEXT_2)

    style.configure(
        "TButton", background=CARD, foreground=TEXT, borderwidth=1, relief="solid",
        bordercolor=BORDER, lightcolor=CARD, darkcolor=CARD, padding=(14, 7),
        focusthickness=0, focuscolor=BLUE_SOFT,
    )
    style.map(
        "TButton",
        background=[("pressed", "#EDEFF1"), ("active", BG), ("disabled", "#F5F6F7")],
        foreground=[("disabled", TEXT_3)],
        bordercolor=[("active", BORDER_HOVER)],
        lightcolor=[("active", BG), ("pressed", "#EDEFF1")],
        darkcolor=[("active", BG), ("pressed", "#EDEFF1")],
    )
    style.configure(
        "Ghost.TButton", background=CARD, foreground=TEXT_2, borderwidth=1, relief="solid",
        bordercolor=BORDER, lightcolor=CARD, darkcolor=CARD, padding=(14, 7),
        focusthickness=0, focuscolor=BLUE_SOFT,
    )
    style.map(
        "Ghost.TButton",
        background=[("active", CARD_ALT), ("pressed", "#EDEFF1"), ("disabled", "#FAFAFB")],
        foreground=[("active", TEXT), ("disabled", TEXT_3)],
        bordercolor=[("active", BORDER_HOVER), ("disabled", BORDER)],
        lightcolor=[("active", CARD_ALT), ("pressed", "#EDEFF1"), ("disabled", "#FAFAFB")],
        darkcolor=[("active", CARD_ALT), ("pressed", "#EDEFF1"), ("disabled", "#FAFAFB")],
    )
    style.configure(
        "Primary.TButton", background=BLUE, foreground="#FFFFFF", borderwidth=0, relief="flat",
        lightcolor=BLUE, darkcolor=BLUE, padding=(16, 8), focusthickness=0, focuscolor=BLUE_SOFT,
    )
    style.map(
        "Primary.TButton",
        background=[("pressed", BLUE_HOVER), ("active", BLUE_HOVER), ("disabled", "#BFEAF8")],
        foreground=[("disabled", "#FFFFFF")],
        lightcolor=[("active", BLUE_HOVER), ("pressed", BLUE_HOVER)],
        darkcolor=[("active", BLUE_HOVER), ("pressed", BLUE_HOVER)],
    )
    style.configure(
        "Pink.TButton", background=PINK, foreground="#FFFFFF", borderwidth=0, relief="flat",
        lightcolor=PINK, darkcolor=PINK, padding=(16, 8), focusthickness=0, focuscolor=PINK_SOFT,
    )
    style.map(
        "Pink.TButton",
        background=[("pressed", PINK_HOVER), ("active", PINK_HOVER), ("disabled", "#FBD1DE")],
        foreground=[("disabled", "#FFFFFF")],
        lightcolor=[("active", PINK_HOVER), ("pressed", PINK_HOVER)],
        darkcolor=[("active", PINK_HOVER), ("pressed", PINK_HOVER)],
    )
    style.configure(
        "Soft.TButton", background=BLUE_SOFT, foreground=BLUE_HOVER, borderwidth=0, relief="flat",
        lightcolor=BLUE_SOFT, darkcolor=BLUE_SOFT, padding=(14, 8), focusthickness=0,
    )
    style.map(
        "Soft.TButton",
        background=[("pressed", "#D2F0FA"), ("active", "#D8F2FC"), ("disabled", "#F2F8FA")],
        foreground=[("disabled", TEXT_3)],
        lightcolor=[("active", "#D8F2FC"), ("pressed", "#D2F0FA")],
        darkcolor=[("active", "#D8F2FC"), ("pressed", "#D2F0FA")],
    )
    style.configure(
        "DangerGhost.TButton", background=CARD, foreground=DANGER, borderwidth=1, relief="solid",
        bordercolor=BORDER, lightcolor=CARD, darkcolor=CARD, padding=(14, 7), focusthickness=0,
    )
    style.map(
        "DangerGhost.TButton",
        background=[("active", RED_SOFT), ("pressed", "#FFE4E1"), ("disabled", "#FAFAFB")],
        foreground=[("disabled", TEXT_3)],
        bordercolor=[("active", "#F8C9C4"), ("disabled", BORDER)],
        lightcolor=[("active", RED_SOFT), ("pressed", "#FFE4E1"), ("disabled", "#FAFAFB")],
        darkcolor=[("active", RED_SOFT), ("pressed", "#FFE4E1"), ("disabled", "#FAFAFB")],
    )

    style.configure(
        "TCheckbutton", background=CARD, foreground=TEXT_2, font=ui_font(9),
        indicatorcolor=CARD, focuscolor=BLUE_SOFT, padding=(0, 2),
    )
    style.map(
        "TCheckbutton",
        background=[("active", CARD)],
        foreground=[("active", TEXT)],
        indicatorcolor=[("selected", BLUE)],
    )
    style.configure(
        "TRadiobutton", background=CARD, foreground=TEXT_2, font=ui_font(9),
        indicatorcolor=CARD, focuscolor=BLUE_SOFT, padding=(0, 2),
    )
    style.map(
        "TRadiobutton",
        background=[("active", CARD)],
        foreground=[("active", TEXT), ("selected", TEXT)],
        indicatorcolor=[("selected", BLUE)],
    )

    style.configure(
        "TEntry", fieldbackground="#F7F8FA", foreground=TEXT, bordercolor="#ECEEF0",
        lightcolor="#ECEEF0", darkcolor="#ECEEF0", insertcolor=TEXT, padding=(10, 6),
        selectbackground=BLUE_SOFT, selectforeground=TEXT,
    )
    style.map(
        "TEntry",
        bordercolor=[("focus", BLUE)],
        lightcolor=[("focus", BLUE)],
        darkcolor=[("focus", BLUE)],
    )
    style.configure(
        "TCombobox", fieldbackground="#F7F8FA", background="#F7F8FA", foreground=TEXT,
        bordercolor="#ECEEF0", lightcolor="#ECEEF0", darkcolor="#ECEEF0", arrowcolor=TEXT_2,
        padding=(9, 5), selectbackground=BLUE_SOFT, selectforeground=TEXT,
    )
    style.map(
        "TCombobox",
        bordercolor=[("focus", BLUE), ("hover", BORDER_HOVER)],
        lightcolor=[("focus", BLUE)],
        darkcolor=[("focus", BLUE)],
        fieldbackground=[("readonly", "#F7F8FA"), ("disabled", "#F2F3F5")],
        foreground=[("readonly", TEXT)],
    )
    style.configure("TSpinbox", fieldbackground="#F7F8FA", foreground=TEXT,
                    bordercolor="#ECEEF0", lightcolor="#ECEEF0", darkcolor="#ECEEF0",
                    arrowcolor=TEXT_2, padding=(8, 4))
    style.map("TSpinbox", bordercolor=[("focus", BLUE)], lightcolor=[("focus", BLUE)],
              darkcolor=[("focus", BLUE)])

    style.configure(
        "Treeview", background=CARD, fieldbackground=CARD, foreground=TEXT,
        rowheight=34, borderwidth=0, relief="flat", font=ui_font(10),
    )
    style.map(
        "Treeview",
        background=[("selected", BLUE_SOFT)],
        foreground=[("selected", TEXT)],
    )
    style.configure(
        "Treeview.Heading", background=CARD_ALT, foreground=TEXT_2, font=ui_font(9, "bold"),
        relief="flat", borderwidth=0, lightcolor=CARD_ALT, darkcolor=CARD_ALT,
        bordercolor=BORDER, padding=(8, 9),
    )
    style.map("Treeview.Heading", background=[("active", "#F1F3F5")],
              lightcolor=[("active", "#F1F3F5")], darkcolor=[("active", "#F1F3F5")])

    for orient in ("Vertical", "Horizontal"):
        style.configure(
            f"{orient}.TScrollbar", gripcount=0, arrowsize=11,
            background="#D5D9DD", troughcolor=CARD, bordercolor=CARD,
            lightcolor="#D5D9DD", darkcolor="#D5D9DD",
        )
        style.map(
            f"{orient}.TScrollbar",
            background=[("active", "#BFC5CB"), ("pressed", "#BFC5CB")],
            lightcolor=[("active", "#BFC5CB")],
            darkcolor=[("active", "#BFC5CB")],
        )

    style.configure("TSeparator", background=BORDER)
    return style


def _widget_bg(widget, fallback=BG):
    try:
        return widget.cget("bg") or fallback
    except tk.TclError:
        return fallback


def _round_rect_points(x1, y1, x2, y2, radius):
    r = max(0.0, min(float(radius), (x2 - x1) / 2.0, (y2 - y1) / 2.0))
    return (
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    )


def _draw_round_rect(canvas, x1, y1, x2, y2, radius, fill, outline=""):
    canvas.create_polygon(
        _round_rect_points(x1, y1, x2, y2, radius), smooth=True,
        splinesteps=36, fill=fill, outline=outline, width=1,
    )


class RoundedFrame(tk.Frame):
    """Card surface with rounded corners; put children in `.content`."""

    def __init__(self, parent, *, radius=RADIUS, fill=CARD, outline=BORDER,
                 bg=None, padding=0, shadow=False, **kwargs):
        parent_bg = bg if bg is not None else _widget_bg(parent)
        super().__init__(parent, bg=parent_bg, **kwargs)
        self._radius = radius
        self._fill = fill
        self._outline = outline
        self._shadow = shadow
        inset = max(padding, math.ceil(radius * 0.3) if outline else max(padding, 1))
        self._inset = inset
        self._canvas = tk.Canvas(self, bg=parent_bg, highlightthickness=0, bd=0)
        self._canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.content = tk.Frame(self, bg=fill)
        self.content.pack(fill="both", expand=True, padx=inset, pady=inset)
        self.bind("<Configure>", lambda _event: self._redraw())
        self._redraw()

    def set_outline(self, color):
        self._outline = color
        self._redraw()

    def _redraw(self):
        width = self.winfo_width()
        height = self.winfo_height()
        if width < 4 or height < 4:
            return
        canvas = self._canvas
        canvas.delete("all")
        if self._shadow:
            _draw_round_rect(canvas, 1, 2, width - 1, height, self._radius,
                             "#EFF1F4", "")
        _draw_round_rect(canvas, 0.5, 0.5, width - 0.5, height - 0.5,
                         self._radius, self._fill, self._outline)


BUTTON_KINDS = {
    "primary": dict(
        fill=BLUE, hover="#00A1D6", pressed="#0093C4", text="#FFFFFF", border="",
        disabled_fill="#EAF7FC", disabled_border="", disabled_text="#A7C8D4"),
    "pink": dict(
        fill=PINK, hover="#F26390", pressed="#E05280", text="#FFFFFF", border="",
        disabled_fill="#FDEEF3", disabled_border="", disabled_text="#D8A9B8"),
    "soft": dict(
        fill=BLUE_SOFT, hover="#DDF3FC", pressed="#CFEDF9", text=BLUE_HOVER, border="",
        disabled_fill="#F4FAFC", disabled_border="", disabled_text="#AFCBD5"),
    "ghost": dict(
        fill=CARD, hover="#F4F4F5", pressed="#EDEFF2", text=TEXT_2, border=BORDER,
        disabled_fill="#FAFAFB", disabled_border="#F0F0F2", disabled_text="#B3B8C0"),
    "danger": dict(
        fill=CARD, hover=RED_SOFT, pressed="#FFE4E1", text=DANGER, border=BORDER,
        disabled_fill="#FAFAFB", disabled_border="#F0F0F2", disabled_text="#D8B4B1"),
}


class RoundedButton(tk.Canvas):
    """Canvas button with a rounded surface and a ttk-like API."""

    def __init__(self, parent, text="", command=None, kind="ghost", radius=RADIUS_SM,
                 padx=16, height=34, state="normal", bg=None, font=None, **kwargs):
        self._kind = kind
        self._theme = BUTTON_KINDS.get(kind, BUTTON_KINDS["ghost"])
        self._text = text
        self._command = command
        self._state = state
        self._radius = radius
        self._padx = padx
        self._height = height
        self._hover = False
        self._pressed = False
        self._focused = False
        self._font = tkfont.Font(font=font or ui_font(
            10, "bold" if kind in {"primary", "pink"} else "normal"))
        width = self._font.measure(text) + padx * 2
        super().__init__(parent, width=width, height=height,
                         bg=bg if bg is not None else _widget_bg(parent),
                         highlightthickness=0, bd=0, takefocus=1,
                         cursor="hand2" if state != "disabled" else "arrow", **kwargs)
        self.bind("<Configure>", lambda _event: self._redraw())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<FocusOut>", self._on_focus_out)
        self.bind("<space>", self._on_key)
        self.bind("<Return>", self._on_key)
        self._redraw()

    def configure(self, cnf=None, **kwargs):
        if cnf is not None:
            if not isinstance(cnf, dict):
                return super().configure(cnf)
            kwargs = {**cnf, **kwargs}
        state = kwargs.pop("state", None)
        text = kwargs.pop("text", None)
        command = kwargs.pop("command", None)
        changed = False
        if state is not None:
            self._state = state
            super().configure(cursor="hand2" if state != "disabled" else "arrow")
            changed = True
        if text is not None and text != self._text:
            self._text = text
            self._resize()
            changed = True
        if command is not None:
            self._command = command
        if changed:
            self._redraw()
        if kwargs:
            super().configure(**kwargs)

    config = configure

    def _resize(self):
        width = self._font.measure(self._text) + self._padx * 2
        tk.Canvas.configure(self, width=width, height=self._height)
        self._redraw()

    def _colors(self):
        theme = self._theme
        if self._state == "disabled":
            return (theme["disabled_fill"], theme["disabled_border"],
                    theme["disabled_text"])
        if self._pressed:
            return theme["pressed"], theme["border"], theme["text"]
        if self._hover:
            return theme["hover"], theme["border"], theme["text"]
        return theme["fill"], theme["border"], theme["text"]

    def _redraw(self):
        width = self.winfo_width() or int(self["width"])
        height = self.winfo_height() or int(self["height"])
        fill, border, text_color = self._colors()
        self.delete("all")
        _draw_round_rect(self, 1, 1, width - 1, height - 1,
                         self._radius, fill, border)
        if self._focused and self._state != "disabled":
            _draw_round_rect(self, 2.5, 2.5, width - 2.5, height - 2.5,
                             self._radius - 1, "", "#9AD9EF")
        self.create_text(width / 2, height / 2, text=self._text,
                         fill=text_color, font=self._font)

    def invoke(self):
        if self._state != "disabled" and self._command:
            self._command()

    def _on_enter(self, _event):
        self._hover = True
        self._redraw()

    def _on_leave(self, _event):
        self._hover = False
        self._pressed = False
        self._redraw()

    def _on_press(self, _event):
        if self._state != "disabled":
            self.focus_set()
            self._pressed = True
            self._redraw()

    def _on_release(self, event):
        was_pressed = self._pressed
        self._pressed = False
        self._redraw()
        inside = (0 <= event.x <= self.winfo_width()
                  and 0 <= event.y <= self.winfo_height())
        if was_pressed and inside:
            self.invoke()

    def _on_focus_in(self, _event):
        self._focused = True
        self._redraw()

    def _on_focus_out(self, _event):
        self._focused = False
        self._redraw()

    def _on_key(self, _event):
        self.invoke()


class RoundedLabel(tk.Canvas):
    """Pill-shaped label, optionally with a small status dot."""

    def __init__(self, parent, text="", textvariable=None, fill=BLUE_SOFT,
                 fg=BLUE_HOVER, padx=10, pady=4, font=None, dot_color=None,
                 bg=None, **kwargs):
        self._font = tkfont.Font(font=font or ui_font(9))
        self._fill = fill
        self._fg = fg
        self._padx = padx
        self._pady = pady
        self._dot_color = dot_color
        self._variable = textvariable
        self._text = textvariable.get() if textvariable is not None else text
        self._height = max(self._font.metrics("linespace") + pady * 2, 22)
        super().__init__(parent, width=1, height=self._height,
                         bg=bg if bg is not None else _widget_bg(parent),
                         highlightthickness=0, bd=0, **kwargs)
        if textvariable is not None:
            textvariable.trace_add("write", self._on_variable)
        self.bind("<Configure>", lambda _event: self._redraw())
        self._resize()

    def configure(self, cnf=None, **kwargs):
        if cnf is not None:
            if not isinstance(cnf, dict):
                return super().configure(cnf)
            kwargs = {**cnf, **kwargs}
        text = kwargs.pop("text", None)
        if text is not None:
            self._text = text
            self._resize()
        if kwargs:
            super().configure(**kwargs)

    config = configure

    def set_dot_color(self, color):
        self._dot_color = color
        self._resize()

    def set_text(self, text):
        self._text = text
        self._resize()

    def _on_variable(self, *_args):
        self._text = self._variable.get()
        self._resize()

    def _resize(self):
        dot_width = 12 if self._dot_color else 0
        width = self._font.measure(self._text) + self._padx * 2 + dot_width
        tk.Canvas.configure(self, width=max(width, 1), height=self._height)
        self._redraw()

    def _redraw(self):
        width = self.winfo_width() or int(self["width"])
        height = self._height
        self.delete("all")
        _draw_round_rect(self, 0.5, 0.5, width - 0.5, height - 0.5,
                         height / 2, self._fill, "")
        x = self._padx
        if self._dot_color:
            diameter = 6
            cy = height / 2
            self.create_oval(x, cy - diameter / 2, x + diameter, cy + diameter / 2,
                             fill=self._dot_color, outline="")
            x += diameter + 6
        self.create_text(x, height / 2, text=self._text, anchor="w",
                         fill=self._fg, font=self._font)


class ToggleChip(tk.Canvas):
    """Rounded toggle chip backed by a BooleanVar."""

    def __init__(self, parent, text, variable, command=None, bg=None,
                 font=None, height=28, padx=10):
        self._variable = variable
        self._command = command
        self._text = text
        self._font = tkfont.Font(font=font or ui_font(9))
        self._height = height
        self._padx = padx
        self._hover = False
        self._focused = False
        width = self._font.measure(text) + padx * 2 + 18
        super().__init__(parent, width=width, height=height,
                         bg=bg if bg is not None else _widget_bg(parent),
                         highlightthickness=0, bd=0, takefocus=1, cursor="hand2")
        variable.trace_add("write", self._on_variable)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<FocusOut>", self._on_focus_out)
        self.bind("<space>", self._on_key)
        self.bind("<Return>", self._on_key)
        self._redraw()

    def _on_variable(self, *_args):
        self._redraw()

    def _on_enter(self, _event):
        self._hover = True
        self._redraw()

    def _on_leave(self, _event):
        self._hover = False
        self._redraw()

    def _on_click(self, _event):
        self.focus_set()
        self._variable.set(not bool(self._variable.get()))
        if self._command:
            self._command()

    def _on_focus_in(self, _event):
        self._focused = True
        self._redraw()

    def _on_focus_out(self, _event):
        self._focused = False
        self._redraw()

    def _on_key(self, _event):
        self._on_click(None)

    def _redraw(self):
        width = self.winfo_width() or int(self["width"])
        height = self._height
        selected = bool(self._variable.get())
        if selected:
            fill, border, fg = BLUE_SOFT, "", BLUE_HOVER
        else:
            fill, border, fg = CARD, BORDER, TEXT_2
        if self._hover:
            fill = "#DDF3FC" if selected else CARD_ALT
        self.delete("all")
        _draw_round_rect(self, 0.5, 0.5, width - 0.5, height - 0.5,
                         height / 2, fill, border)
        x = self._padx
        if selected:
            cy = height / 2
            cx = x + 5
            self.create_line(cx - 4, cy, cx - 1, cy + 3, cx + 4, cy - 4,
                             fill=fg, width=2, capstyle="round", joinstyle="round")
        x += 16
        self.create_text(x, height / 2, text=self._text, anchor="w",
                         fill=fg, font=self._font)
        if self._focused:
            _draw_round_rect(self, 2, 2, width - 2, height - 2,
                             height / 2 - 1, "", "#9AD9EF")


class RoundedBar(tk.Canvas):
    def __init__(self, parent, width=20, height=4, fill=BLUE, bg=None):
        super().__init__(parent, width=width, height=height,
                         bg=bg if bg is not None else _widget_bg(parent),
                         highlightthickness=0, bd=0)
        self._fill = fill
        self._width = width
        self._height = height
        self.bind("<Configure>", lambda _event: self._redraw())
        self._redraw()

    def set_fill(self, color):
        self._fill = color
        self._redraw()

    def _redraw(self):
        self.delete("all")
        _draw_round_rect(self, 0.5, 0.5, self._width - 0.5, self._height - 0.5,
                         self._height / 2, self._fill, "")


class NavBar(tk.Frame):
    """Horizontal page switcher in the style of Bilibili's channel nav."""

    def __init__(self, parent, on_change=None):
        super().__init__(parent, bg=CARD)
        self.on_change = on_change
        self.items = {}
        self.active = None
        self.inner = tk.Frame(self, bg=CARD)
        self.inner.pack(side="left", padx=(20, 0))
        tk.Frame(self, bg="#F0F0F2", height=1).pack(side="bottom", fill="x")

    def add_page(self, key, title, page):
        item = tk.Frame(self.inner, bg=CARD)
        item.pack(side="left", padx=(0, 2))
        label = tk.Label(item, text=title, font=ui_font(10), bg=CARD, fg=TEXT_2,
                         padx=14, pady=11, cursor="hand2")
        label.pack(fill="x")
        underline = RoundedBar(item, width=20, height=4, fill=CARD, bg=CARD)
        underline.pack(anchor="center", pady=(0, 7))
        for widget in (item, label, underline):
            widget.bind("<Button-1>", lambda _event, name=key: self.select(name))
            widget.bind("<Enter>", lambda _event, name=key: self._hover(name, True))
            widget.bind("<Leave>", lambda _event, name=key: self._hover(name, False))
        self.items[key] = {"label": label, "underline": underline, "page": page, "item": item}
        if self.active is None:
            self.select(key)

    def _hover(self, key, entering):
        if key == self.active:
            return
        label = self.items[key]["label"]
        label.configure(fg=BLUE if entering else TEXT_2)

    def select(self, key):
        if key not in self.items:
            return
        self.active = key
        for name, entry in self.items.items():
            active = name == key
            entry["label"].configure(fg=BLUE if active else TEXT_2,
                                     font=ui_font(10, "bold") if active else ui_font(10))
            entry["underline"].set_fill(BLUE if active else CARD)
            if active:
                entry["page"].pack(fill="both", expand=True)
            else:
                entry["page"].pack_forget()
        if self.on_change:
            self.on_change(key)

    def set_text(self, key, text):
        if key in self.items:
            self.items[key]["label"].configure(text=text)
