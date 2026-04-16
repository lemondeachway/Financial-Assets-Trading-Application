"""
Helpers for building the Position tab UI.
"""
import tkinter as tk
from tkinter import ttk
from typing import Any


def build_position_tab(app: Any, notebook) -> None:
    """
    Build the Position tab UI and bind controls to the app.
    """
    control_tab = ttk.Frame(notebook)
    notebook.add(control_tab, text="Position")

    state_frame = ttk.LabelFrame(control_tab, text="Position State")
    state_frame.pack(side=tk.TOP, fill=tk.X, padx=0, pady=(0, 4))

    app.position_label = ttk.Label(state_frame, text="Hold positions: 0 (long: 0, short: 0)")
    app.position_label.pack(side=tk.TOP, anchor="w", padx=4, pady=2)

    app.settlement_label = ttk.Label(state_frame, text="Settlement (net): 0")
    app.settlement_label.pack(side=tk.TOP, anchor="w", padx=4, pady=2)
    app.equity_label = ttk.Label(state_frame, text="Equity: 0")
    app.equity_label.pack(side=tk.TOP, anchor="w", padx=4, pady=2)

    trade_btn_frame = ttk.LabelFrame(control_tab, text="Trading Controls")
    trade_btn_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 4))

    ttk.Button(trade_btn_frame, text="Open Long", command=lambda: app.open_long(owner="MANUAL")).pack(side=tk.LEFT, padx=4, pady=2)
    ttk.Button(trade_btn_frame, text="Open Short", command=lambda: app.open_short(owner="MANUAL")).pack(side=tk.LEFT, padx=4, pady=2)
    ttk.Button(trade_btn_frame, text="Close Long", command=lambda: app.close_long(owner="MANUAL")).pack(side=tk.LEFT, padx=4, pady=2)
    ttk.Button(trade_btn_frame, text="Close Short", command=lambda: app.close_short(owner="MANUAL")).pack(side=tk.LEFT, padx=4, pady=2)

    # Position Information
    pos_frame = ttk.LabelFrame(control_tab, text="Position Information")
    pos_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(0, 4))

    pos_columns = ("action", "qty", "time", "price", "diff")
    app.pos_tree = ttk.Treeview(pos_frame, columns=pos_columns, show="headings", height=6)
    app.pos_tree.heading("action", text="Action")
    app.pos_tree.heading("qty", text="Qty")
    app.pos_tree.heading("time", text="Time")
    app.pos_tree.heading("price", text="Last")
    app.pos_tree.heading("diff", text="Diff")

    app.pos_tree.column("action", width=90, anchor=tk.W)
    app.pos_tree.column("qty", width=50, anchor=tk.E)
    app.pos_tree.column("time", width=180, anchor=tk.W)
    app.pos_tree.column("price", width=90, anchor=tk.E)
    app.pos_tree.column("diff", width=90, anchor=tk.E)

    vsb_pos = ttk.Scrollbar(pos_frame, orient="vertical", command=app.pos_tree.yview)
    app.pos_tree.configure(yscrollcommand=vsb_pos.set)

    app.pos_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    vsb_pos.pack(side=tk.RIGHT, fill=tk.Y)
