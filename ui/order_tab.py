"""
Helpers for building the Order (autoclicker) tab.
"""
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable


def build_order_tab(app: Any, notebook) -> None:
    """
    Build the Order tab UI, wiring to the app's autoclicker methods/state.
    """
    autoc_tab = ttk.Frame(notebook)
    notebook.add(autoc_tab, text="Order")

    info = (
        "Order watcher watches the 'commands' folder for cmd_*.txt files and\n"
        "executes OPEN_LONG / OPEN_SHORT / CLOSE_LONG / CLOSE_SHORT via human-like clicks.\n"
        "Edit coordinates and options below, then Start."
    )
    ttk.Label(autoc_tab, text=info, justify=tk.LEFT, wraplength=700).pack(side=tk.TOP, anchor="w", padx=8, pady=8)

    cfg = ttk.LabelFrame(autoc_tab, text="Coordinates")
    cfg.pack(side=tk.TOP, fill=tk.X, padx=8, pady=4)

    layout_names = list(getattr(app, "order_layouts", {}).keys())
    if layout_names:
        layout_frame = ttk.Frame(cfg)
        layout_frame.pack(side=tk.TOP, fill=tk.X, padx=4, pady=2)
        ttk.Label(layout_frame, text="Layout", width=12).pack(side=tk.LEFT)
        initial = layout_names[0]
        app.order_layout_var = tk.StringVar(value=initial)

        def _select_layout(value: str) -> None:
            app.apply_order_layout(value)

        layout_menu = ttk.OptionMenu(
            layout_frame,
            app.order_layout_var,
            app.order_layout_var.get(),
            *layout_names,
            command=_select_layout,
        )
        layout_menu.pack(side=tk.LEFT)
        ttk.Button(layout_frame, text="Apply", command=lambda: _select_layout(app.order_layout_var.get())).pack(
            side=tk.LEFT, padx=6
        )
    def coord_row(parent, label: str, getter: Callable, setter: Callable, attr_name: str) -> None:
        row = ttk.Frame(parent)
        row.pack(side=tk.TOP, fill=tk.X, padx=4, pady=2)
        ttk.Label(row, text=label, width=12).pack(side=tk.LEFT)
        varx = tk.StringVar(value=str(getter()[0]))
        vary = tk.StringVar(value=str(getter()[1]))
        entx = ttk.Entry(row, textvariable=varx, width=8)
        entx.pack(side=tk.LEFT, padx=(0, 4))
        enty = ttk.Entry(row, textvariable=vary, width=8)
        enty.pack(side=tk.LEFT, padx=(0, 4))

        def apply():
            try:
                setter((int(float(varx.get())), int(float(vary.get()))))
            except ValueError:
                pass

        ttk.Button(row, text="Set", command=apply, width=6).pack(side=tk.LEFT, padx=2)
        app.order_coord_vars[attr_name] = (varx, vary)

    coord_row(cfg, "Open Long", lambda: app.open_long_pos, lambda v: setattr(app, "open_long_pos", v), "open_long_pos")
    coord_row(cfg, "Open Short", lambda: app.open_short_pos, lambda v: setattr(app, "open_short_pos", v), "open_short_pos")
    coord_row(cfg, "Close", lambda: app.close_pos, lambda v: setattr(app, "close_pos", v), "close_pos")
    coord_row(cfg, "Cursor Home", lambda: app.default_cursor_pos, lambda v: setattr(app, "default_cursor_pos", v), "default_cursor_pos")

    if layout_names:
        app.apply_order_layout(app.order_layout_var.get())

    opts = ttk.LabelFrame(autoc_tab, text="Options")
    opts.pack(side=tk.TOP, fill=tk.X, padx=8, pady=4)
    app.dry_run_var = tk.BooleanVar(value=getattr(app, "dry_run", False))
    ttk.Checkbutton(
        opts,
        text="Dry Run (no real clicks)",
        variable=app.dry_run_var,
        command=lambda: setattr(app, "dry_run", app.dry_run_var.get()),
    ).pack(side=tk.LEFT, padx=6)
    app.human_move_var = tk.BooleanVar(value=getattr(app, "human_move", False))
    ttk.Checkbutton(
        opts,
        text="Human-like movement",
        variable=app.human_move_var,
        command=lambda: setattr(app, "human_move", app.human_move_var.get()),
    ).pack(side=tk.LEFT, padx=6)

    btn_row = ttk.Frame(autoc_tab)
    btn_row.pack(side=tk.TOP, fill=tk.X, padx=8, pady=6)
    ttk.Button(btn_row, text="Start Order", command=app.start_autoclicker).pack(side=tk.LEFT, padx=6)
    ttk.Button(btn_row, text="Stop", command=app.stop_autoclicker).pack(side=tk.LEFT, padx=6)

    # Live cursor coordinates
    app.cursor_label = ttk.Label(autoc_tab, text="Cursor: x=-- y=--")
    app.cursor_label.pack(side=tk.TOP, anchor="w", padx=8, pady=(0, 6))
    app._update_cursor_coords()
