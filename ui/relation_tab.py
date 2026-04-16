"""
Helpers for the Relation tab actions and UI.
"""
from typing import Any
from tkinter import ttk, messagebox
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from app import plotting


def build_relation_tab(app: Any, analysis_notebook) -> None:
    """
    Build the Relation subtab inside the provided analysis notebook.
    """
    analysis_relation_tab = ttk.Frame(analysis_notebook)
    analysis_notebook.add(analysis_relation_tab, text="Relation")

    relation_top = ttk.LabelFrame(analysis_relation_tab, text="Axes & Points")
    relation_top.pack(side="top", fill="x", padx=6, pady=6)

    ttk.Label(relation_top, text="X label").pack(side="left", padx=(6, 2))
    ttk.Entry(relation_top, textvariable=app.rel_x_label_var, width=12).pack(side="left", padx=(0, 8))
    ttk.Label(relation_top, text="Y label").pack(side="left", padx=(6, 2))
    ttk.Entry(relation_top, textvariable=app.rel_y_label_var, width=12).pack(side="left", padx=(0, 8))
    ttk.Button(relation_top, text="Apply Axes", command=app._redraw_relation_plot).pack(side="left", padx=6)

    point_frame = ttk.Frame(relation_top)
    point_frame.pack(side="top", fill="x", padx=6, pady=(6, 2))
    ttk.Label(point_frame, text="Name").pack(side="left", padx=(0, 2))
    ttk.Entry(point_frame, textvariable=app.rel_point_name_var, width=12).pack(side="left", padx=(0, 6))
    ttk.Label(point_frame, text="X").pack(side="left", padx=(0, 2))
    ttk.Entry(point_frame, textvariable=app.rel_point_x_var, width=8).pack(side="left", padx=(0, 6))
    ttk.Label(point_frame, text="Y").pack(side="left", padx=(0, 2))
    ttk.Entry(point_frame, textvariable=app.rel_point_y_var, width=8).pack(side="left", padx=(0, 6))
    ttk.Button(point_frame, text="Add/Update Point", command=app._relation_add_point).pack(side="left", padx=6)
    ttk.Button(point_frame, text="Clear Points", command=app._relation_clear_points).pack(side="left", padx=6)

    # Relation plot
    rel_plot_frame = ttk.Frame(analysis_relation_tab)
    rel_plot_frame.pack(side="top", fill="both", expand=True, padx=6, pady=6)
    app.rel_fig = Figure(figsize=(5, 4), dpi=100)
    app.rel_ax = app.rel_fig.add_subplot(111)
    app.rel_canvas = FigureCanvasTkAgg(app.rel_fig, master=rel_plot_frame)
    app.rel_canvas.draw()
    app.rel_canvas.get_tk_widget().pack(side="top", fill="both", expand=True)


def add_point(app: Any) -> None:
    """
    Add or replace a named point on the relation scatter plot.
    """
    name = app.rel_point_name_var.get().strip() or f"P{len(app.relation_points)+1}"
    try:
        x_val = float(app.rel_point_x_var.get().strip())
        y_val = float(app.rel_point_y_var.get().strip())
    except ValueError:
        messagebox.showerror("Relation", "X and Y must be numeric.")
        return
    # Replace if same name exists
    app.relation_points = [(n, x, y) for (n, x, y) in app.relation_points if n != name]
    app.relation_points.append((name, x_val, y_val))
    redraw(app)


def clear_points(app: Any) -> None:
    """
    Clear all relation points and refresh the plot.
    """
    app.relation_points.clear()
    redraw(app)


def redraw(app: Any) -> None:
    """
    Redraw the relation scatter plot using current state on the app.
    """
    if getattr(app, "rel_ax", None) is None or getattr(app, "rel_canvas", None) is None:
        return
    plotting.draw_relation(
        app.rel_ax,
        app.relation_points,
        app.rel_x_label_var.get().strip(),
        app.rel_y_label_var.get().strip(),
    )
    app.rel_canvas.draw_idle()
