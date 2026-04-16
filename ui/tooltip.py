"""
Simple tooltip helper for Tk widgets.
"""
import tkinter as tk
from typing import Optional
from ui import theme


class ToolTip:
    def __init__(self, widget: tk.Widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self.tipwindow: Optional[tk.Toplevel] = None
        widget.bind("<Enter>", self.show_tip)
        widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None) -> None:
        if self.tipwindow or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        palette = theme.get_active_theme()
        label = tk.Label(
            tw,
            text=self.text,
            justify=tk.LEFT,
            background=palette.tooltip_bg,
            foreground=palette.tooltip_fg,
            relief=tk.SOLID,
            borderwidth=1,
            font=("TkDefaultFont", 11, "bold"),
        )
        label.pack(ipadx=6, ipady=4)

    def hide_tip(self, event=None) -> None:
        tw = self.tipwindow
        self.tipwindow = None
        if tw is not None:
            tw.destroy()
