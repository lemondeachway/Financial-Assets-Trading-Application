"""
Helpers for the Test tab (order simulation + cursor display).
"""
import tkinter as tk
from tkinter import ttk
from datetime import datetime
from typing import Any


def append_test_log(app: Any, msg: str) -> None:
    """Append a timestamped line to the test log widget if present."""
    if not hasattr(app, "test_log") or app.test_log is None:
        return
    ts = datetime.now().strftime("%H:%M:%S")
    app.test_log.insert(tk.END, f"[{ts}] {msg}\n")
    app.test_log.see(tk.END)


def run_trading_movement_test(app: Any) -> None:
    """
    Create in-tab buttons for trading actions to verify click handling without affecting live logic.
    """
    if not hasattr(app, "test_area") or app.test_area is None:
        return
    # clear previous widgets
    for child in app.test_area.winfo_children():
        child.destroy()

    # Output buttons: click to verify auto-clicker reaches them (manual or by automation)
    out_btn_frame = ttk.Frame(app.test_area)
    out_btn_frame.pack(side=tk.TOP, fill=tk.X, padx=6, pady=6)
    ttk.Button(out_btn_frame, text="Output Open Long", command=lambda: append_test_log(app, "Output: Open Long clicked")).pack(
        side=tk.LEFT, padx=4, pady=2
    )
    ttk.Button(out_btn_frame, text="Output Open Short", command=lambda: append_test_log(app, "Output: Open Short clicked")).pack(
        side=tk.LEFT, padx=4, pady=2
    )
    ttk.Button(out_btn_frame, text="Output Close", command=lambda: append_test_log(app, "Output: Close clicked")).pack(
        side=tk.LEFT, padx=4, pady=2
    )

    log_frame = ttk.Frame(app.test_area)
    log_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=6, pady=6)

    app.test_log = tk.Text(log_frame, height=12, wrap="word")
    app.test_log.pack(fill=tk.BOTH, expand=True)
    append_test_log(app, "Trading movement test initialized.")

    # Cursor coords display in Test tab
    if not hasattr(app, "test_cursor_label"):
        app.test_cursor_label = ttk.Label(app.test_area, text="Cursor: x=-- y=--")
        app.test_cursor_label.pack(side=tk.BOTTOM, anchor="w", padx=6, pady=4)


def update_cursor_coords(app: Any, pyautogui_available: bool, pyautogui_module=None) -> None:
    """
    Refresh cursor coordinates for both order tab and test tab.
    """
    if not pyautogui_available or pyautogui_module is None:
        return
    try:
        x, y = pyautogui_module.position()
        if hasattr(app, "cursor_label") and app.cursor_label is not None:
            app.cursor_label.config(text=f"Cursor: x={x} y={y}")
        if hasattr(app, "test_cursor_label") and app.test_cursor_label is not None:
            app.test_cursor_label.config(text=f"Cursor: x={x} y={y}")
    except Exception:
        pass
    try:
        app.root.after(200, lambda: update_cursor_coords(app, pyautogui_available, pyautogui_module))
    except Exception:
        pass


def build_test_tab(app: Any, notebook) -> None:
    """
    Build the Test tab with an Order subtab and bind the test area.
    """
    test_tab = ttk.Frame(notebook)
    notebook.add(test_tab, text="Test")

    test_notebook = ttk.Notebook(test_tab)
    test_notebook.pack(fill="both", expand=True)

    trade_tab = ttk.Frame(test_notebook)
    test_notebook.add(trade_tab, text="Order")

    ttk.Label(
        trade_tab,
        text="Use this tab to run ad-hoc test programs. The first test creates in-tab buttons\n"
             "for trading actions so you can verify click handling without affecting live logic.",
        justify=tk.LEFT,
        wraplength=700,
    ).pack(side="top", anchor="w", padx=8, pady=8)

    ttk.Button(trade_tab, text="Order", command=app._run_trading_movement_test).pack(
        side="top", anchor="w", padx=8, pady=(0, 8)
    )

    container = ttk.Frame(trade_tab)
    container.pack(side="top", fill="both", expand=True, padx=8, pady=4)

    app.test_area = ttk.LabelFrame(container, text="Test Output")
    app.test_area.pack(side="left", fill="both", expand=True)

    app.test_log = tk.Text(app.test_area, height=6, wrap="word")
    app.test_log.pack(fill="both", expand=True, padx=6, pady=6)
