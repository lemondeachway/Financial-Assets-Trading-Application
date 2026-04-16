"""
Helpers for building the Analysis tab (Index + Relation subtabs).
"""
from typing import Any
from tkinter import ttk
import tkinter as tk
from ui import relation_tab


def build_analysis_tab(app: Any, notebook) -> None:
    """
    Build the Analysis tab with Index and Relation subtabs.
    """
    analysis_tab = ttk.Frame(notebook)
    notebook.add(analysis_tab, text="Analysis")

    analysis_notebook = ttk.Notebook(analysis_tab)
    analysis_notebook.pack(fill="both", expand=True, padx=4, pady=4)

    # Analysis -> Index subtab
    analysis_index_tab = ttk.Frame(analysis_notebook)
    analysis_notebook.add(analysis_index_tab, text="Index")

    desc = (
        "Load futures last-price CSVs to view quick stats (count, min/max, range, mean/median, stdev,\n"
        "5th/95th percentiles) and understand how every file spans the three futures sessions\n"
        "— morning, afternoon, and night."
    )
    ttk.Label(analysis_index_tab, text=desc, justify="left", wraplength=800).pack(side="top", anchor="w", padx=8, pady=8)

    ttk.Button(analysis_index_tab, text="Load CSV for analysis", command=app.load_analysis_csv).pack(
        side="top", anchor="w", padx=8, pady=(0, 8)
    )

    app.analysis_text = tk.Text(analysis_index_tab, height=12, wrap="word")
    app.analysis_text.pack(fill="both", expand=True, padx=8, pady=8)

    # Analysis -> Relation subtab
    relation_tab.build_relation_tab(app, analysis_notebook)
