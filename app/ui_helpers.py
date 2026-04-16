"""
Small Tk helper functions shared across the UI.
"""
import tkinter as tk
from typing import Any, List, Tuple
from datetime import datetime


def logic_time_display(t_str: str) -> str:
    """
    Show only intraday time (HH:MM:SS); fallback to original string.
    """
    try:
        return datetime.strptime(t_str, "%Y-%m-%d %H:%M:%S").strftime("%H:%M:%S")
    except Exception:
        parts = t_str.split()
        return parts[-1] if parts else t_str


def clear_tree(tree: tk.Widget) -> None:
    try:
        for item in tree.get_children():
            tree.delete(item)
    except Exception:
        pass
