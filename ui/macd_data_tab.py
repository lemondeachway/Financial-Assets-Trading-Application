import tkinter as tk
from tkinter import ttk
from typing import Any


def build_macd_data_tab(app: Any, notebook) -> None:
    frame = ttk.Frame(notebook)
    notebook.add(frame, text="MACD Data")
    toggle_frame = ttk.Frame(frame)
    toggle_frame.pack(side=tk.TOP, fill=tk.X, padx=6, pady=(6,0))
    toggle_button = ttk.Button(toggle_frame, text="Hide RSI overlay", command=app._toggle_rsi_overlay)
    toggle_button.pack(side=tk.LEFT)
    app.rsi_toggle_button = toggle_button
    columns = ("time", "price", "dif", "dea", "hist", "atr", "vol", "rsi", "stoch")
    tree = ttk.Treeview(frame, columns=columns, show="headings", height=18)
    tree.heading("time", text="Time")
    tree.heading("price", text="Price")
    tree.heading("dif", text="DIF")
    tree.heading("dea", text="DEA")
    tree.heading("hist", text="Hist")
    tree.heading("atr", text="ATR")
    tree.heading("vol", text="ATR Vol%")
    tree.heading("rsi", text="RSI")
    tree.heading("stoch", text="Stoch %K")
    tree.column("time", width=140, anchor=tk.W)
    tree.column("price", width=90, anchor=tk.E)
    tree.column("dif", width=90, anchor=tk.E)
    tree.column("dea", width=90, anchor=tk.E)
    tree.column("hist", width=90, anchor=tk.E)
    tree.column("atr", width=90, anchor=tk.E)
    tree.column("vol", width=90, anchor=tk.E)
    tree.column("rsi", width=90, anchor=tk.E)
    tree.column("stoch", width=90, anchor=tk.E)
    vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    vsb.pack(side=tk.RIGHT, fill=tk.Y)
    app.macd_tree = tree
