"""
Helpers for building the Backtest tab UI (quick and streaming).
"""
import tkinter as tk
from tkinter import ttk
from typing import Any


def build_backtest_tab(app: Any, notebook) -> None:
    """
    Build the Backtest tab with quick and streaming sections.
    """
    backtest_tab = ttk.Frame(notebook)
    notebook.add(backtest_tab, text="Backtest")

    quick_frame = ttk.LabelFrame(backtest_tab, text="Quick Backtest")
    quick_frame.pack(side=tk.TOP, fill=tk.X, padx=8, pady=6)
    ttk.Label(quick_frame, text="Load full CSV(s) and evaluate mechanisms quickly.").pack(side=tk.LEFT, padx=6, pady=4)
    step_frame = ttk.Frame(quick_frame)
    step_frame.pack(side=tk.LEFT, padx=6, pady=4)
    ttk.Label(step_frame, text="Step (data_point):").pack(side=tk.LEFT, padx=(0, 4))
    ttk.Combobox(
        step_frame,
        width=6,
        state="readonly",
        values=("1", "5", "10", "20", "50"),
        textvariable=app.backtest_step_var,
    ).pack(side=tk.LEFT)
    ttk.Button(quick_frame, text="Run Quick Backtest", command=app.quick_backtest_multi).pack(side=tk.LEFT, padx=6, pady=4)
    app.quick_results_frame = ttk.LabelFrame(backtest_tab, text="Quick Backtest Results")
    app.quick_results_frame.pack(side=tk.TOP, fill=tk.X, padx=8, pady=4)

    stream_frame = ttk.LabelFrame(backtest_tab, text="Streaming Backtest")
    stream_frame.pack(side=tk.TOP, fill=tk.X, padx=8, pady=6)
    ttk.Label(stream_frame, text="Simulate CSV as flowing data with progress.").pack(side=tk.TOP, anchor="w", padx=6, pady=(4, 2))

    ctrl_row = ttk.Frame(stream_frame)
    ctrl_row.pack(side=tk.TOP, fill=tk.X, padx=6, pady=4)
    ttk.Label(ctrl_row, text="Step Delay (s):").pack(side=tk.LEFT, padx=(0, 4))
    app.stream_delay_var = tk.StringVar(value=str(app.interval))
    ttk.Entry(ctrl_row, textvariable=app.stream_delay_var, width=8).pack(side=tk.LEFT, padx=(0, 8))
    ttk.Label(ctrl_row, text="Speed x").pack(side=tk.LEFT, padx=(4, 4))
    app.stream_speed_var = tk.StringVar(value="100")
    ttk.Entry(ctrl_row, textvariable=app.stream_speed_var, width=8).pack(side=tk.LEFT, padx=(0, 8))
    ttk.Button(ctrl_row, text="Start Streaming Backtest", command=app.start_stream_backtest).pack(side=tk.LEFT, padx=4)
    ttk.Button(ctrl_row, text="Stop", command=app.stop_stream_backtest).pack(side=tk.LEFT, padx=4)

    progress_row = ttk.Frame(stream_frame)
    progress_row.pack(side=tk.TOP, fill=tk.X, padx=6, pady=(4, 6))
    app.stream_progress = ttk.Scale(progress_row, from_=0, to=0, orient="horizontal", command=app._seek_stream_progress)
    app.stream_progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
    app.stream_progress_label = ttk.Label(progress_row, text="0/0")
    app.stream_progress_label.pack(side=tk.LEFT)
