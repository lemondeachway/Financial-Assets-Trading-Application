"""
Helpers for building the Trend tab (NR, CL, Backtest Trend charts).
"""
import tkinter as tk
from tkinter import ttk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from app import plotting
from ui import theme


def build_trend_tab(app, notebook) -> None:
    """
    Build the Trend tab with NR/CL charts and backtest trend notebooks.
    Expects app to provide: _refresh_macd_mode and chart data lists.
    """
    palette = getattr(app, "theme", theme.get_active_theme())
    chart_tab = ttk.Frame(notebook)
    notebook.add(chart_tab, text="Trend")

    chart_notebook = ttk.Notebook(chart_tab)
    chart_notebook.pack(fill=tk.BOTH, expand=True)

    # NR realtime tab
    realtime_tab = ttk.Frame(chart_notebook)
    chart_notebook.add(realtime_tab, text="NR")

    chart_header_frame = ttk.Frame(realtime_tab)
    chart_header_frame.pack(side=tk.TOP, fill=tk.X)

    chart_frame = ttk.Frame(realtime_tab)
    chart_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=0, pady=0)

    # Use constrained layout and let the frame propagate so the plots can occupy almost all available space.
    app.fig = Figure(figsize=(12, 7), dpi=100, constrained_layout=True)
    app.ax, app.ax_macd = app.fig.subplots(
        2,
        1,
        sharex=True,
        gridspec_kw={"height_ratios": plotting.PRICE_MACD_HEIGHT_RATIOS},
    )
    app.ax.set_title("Last Price")
    app.ax.set_ylabel("Price")
    app.ax_macd.set_ylabel("MACD")
    app.ax_macd.set_xlabel("Time")
    app.canvas = FigureCanvasTkAgg(app.fig, master=chart_frame)
    app.canvas.draw()
    widget = app.canvas.get_tk_widget()
    widget.configure(bg=palette.chart_face, highlightthickness=0, borderwidth=0)
    widget.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=0, pady=0)

    macd_frame = ttk.Frame(chart_header_frame)
    macd_frame.pack(side=tk.LEFT, padx=4)
    ttk.Label(macd_frame, text="MACD TF:").pack(side=tk.LEFT, padx=(0, 2))
    macd_combo = ttk.Combobox(
        macd_frame,
        width=6,
        state="readonly",
        values=("Tick", "1m", "3m", "5m", "10m", "15m"),
        textvariable=app.macd_mode_var,
    )
    macd_combo.pack(side=tk.LEFT)
    macd_combo.bind("<<ComboboxSelected>>", lambda e: app._refresh_macd_mode())

    # CL tab
    cl_tab = ttk.Frame(chart_notebook)
    chart_notebook.add(cl_tab, text="CL")

    cl_header_frame = ttk.Frame(cl_tab)
    cl_header_frame.pack(side=tk.TOP, fill=tk.X)

    cl_chart_frame = ttk.Frame(cl_tab)
    cl_chart_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=0, pady=0)

    app.fig_cl = Figure(figsize=(12, 7), dpi=100, constrained_layout=True)
    app.ax_cl, app.ax_cl_macd = app.fig_cl.subplots(
        2,
        1,
        sharex=True,
        gridspec_kw={"height_ratios": plotting.PRICE_MACD_HEIGHT_RATIOS},
    )
    app.ax_cl.set_title("Last Price")
    app.ax_cl.set_ylabel("Price")
    app.ax_cl_macd.set_ylabel("MACD")
    app.ax_cl_macd.set_xlabel("Time")

    app.canvas_cl = FigureCanvasTkAgg(app.fig_cl, master=cl_chart_frame)
    app.canvas_cl.draw()
    widget_cl = app.canvas_cl.get_tk_widget()
    widget_cl.configure(bg=palette.chart_face, highlightthickness=0, borderwidth=0)
    widget_cl.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=0, pady=0)

    # Backtest Trend subtab (shows backtest trend chart)
    bt_trend_tab = ttk.Frame(chart_notebook)
    chart_notebook.add(bt_trend_tab, text="Backtest Trend")

    bt_tabs = ttk.Notebook(bt_trend_tab)
    bt_tabs.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

    mech_tabs_frame = ttk.Frame(bt_tabs)
    bt_tabs.add(mech_tabs_frame, text="Quick Backtest Trend")
    app.bt_mech_notebook = ttk.Notebook(mech_tabs_frame)
    app.bt_mech_notebook.pack(fill=tk.BOTH, expand=True)

    stream_tabs_frame = ttk.Frame(bt_tabs)
    bt_tabs.add(stream_tabs_frame, text="Streaming Backtest Trend")
    app.bt_stream_notebook = ttk.Notebook(stream_tabs_frame)
    app.bt_stream_notebook.pack(fill=tk.BOTH, expand=True)

    # Preloaded CSV tab
    preload_tab = ttk.Frame(chart_notebook)
    chart_notebook.add(preload_tab, text="Preload")

    preload_header_frame = ttk.Frame(preload_tab)
    preload_header_frame.pack(side=tk.TOP, fill=tk.X)
    app.preload_label_var = tk.StringVar(value="Preloaded data: pending")
    ttk.Label(preload_header_frame, textvariable=app.preload_label_var).pack(side=tk.LEFT, padx=8, pady=4)
    crosshair_lbl = ttk.Label(preload_header_frame, textvariable=app.preload_crosshair_label_var)
    crosshair_lbl.pack(side=tk.RIGHT, padx=8, pady=4)
    progress = ttk.Progressbar(preload_header_frame, mode="indeterminate", length=120)
    progress.pack(side=tk.RIGHT, padx=8, pady=4)
    app.preload_progressbar = progress

    preload_chart_frame = ttk.Frame(preload_tab)
    preload_chart_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=0, pady=0)
    app.preload_fig = Figure(figsize=(12, 7), dpi=100, constrained_layout=True)
    app.preload_ax, app.preload_ax_macd = app.preload_fig.subplots(
        2,
        1,
        sharex=True,
        gridspec_kw={"height_ratios": plotting.PRICE_MACD_HEIGHT_RATIOS},
    )
    app.preload_ax.set_title("Preloaded Last Price")
    app.preload_ax.set_ylabel("Price")
    app.preload_ax_macd.set_ylabel("MACD")
    app.preload_ax_macd.set_xlabel("Time")
    app.preload_canvas = FigureCanvasTkAgg(app.preload_fig, master=preload_chart_frame)
    app.preload_canvas.draw()
    preload_widget = app.preload_canvas.get_tk_widget()
    preload_widget.configure(bg=palette.chart_face, highlightthickness=0, borderwidth=0)
    preload_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=0, pady=0)
    if hasattr(app, "_preload_zoom_cid") and app._preload_zoom_cid is not None:
        try:
            app.preload_canvas.mpl_disconnect(app._preload_zoom_cid)
        except Exception:
            pass
    app._preload_zoom_cid = app.preload_canvas.mpl_connect("scroll_event", app._zoom_preload_chart)
    app.preload_canvas.mpl_connect("button_press_event", app._toggle_preload_crosshair)
    # pan events
    if hasattr(app, "_preload_pan_cid"):
        for key in ("press", "motion", "release"):
            cid = app._preload_pan_cid.get(key)
            if cid is not None:
                try:
                    app.preload_canvas.mpl_disconnect(cid)
                except Exception:
                    pass
    app._preload_pan_cid["press"] = app.preload_canvas.mpl_connect("button_press_event", app._pan_preload_start)
    app._preload_pan_cid["motion"] = app.preload_canvas.mpl_connect("motion_notify_event", app._pan_preload_motion)
    app._preload_pan_cid["release"] = app.preload_canvas.mpl_connect("button_release_event", app._pan_preload_end)
    app.preload_canvas.mpl_connect("motion_notify_event", app._update_preload_crosshair)
    preload_widget.bind("<Command-i>", lambda e: app._zoom_preload_shortcut(1 / 1.2, e))
    preload_widget.bind("<Command-o>", lambda e: app._zoom_preload_shortcut(1.2, e))

    def _tab_changed(event):
        selected = event.widget.tab(event.widget.select(), "text")
        is_preload = selected == "Preload"
        app.preload_tab_active = is_preload
        if not is_preload:
            app._hide_preload_crosshair()

    chart_notebook.bind("<<NotebookTabChanged>>", _tab_changed)
    app.preload_tab_active = False
    preload_widget.bind("<Left>", lambda e: app._pan_preload_keyboard(-1))
    preload_widget.bind("<Right>", lambda e: app._pan_preload_keyboard(1))
    preload_widget.focus_set()
    app.load_preload_series()
    app.draw_preload_chart()
