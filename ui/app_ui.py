"""
Top-level UI builder for RealTickApp.
"""
import tkinter as tk
from tkinter import ttk
from ui import trend_tab, position_tab, strategy_tab, contract_tab, order_tab, backtest_tab, test_tab, analysis_tab
from ui import macd_data_tab
from ui import algo_tab
from ui import theme


def build_ui(app) -> None:
    """
    Build the main UI: status bar, clock, notebook tabs.
    """
    app.root.title("Psephos")
    style = ttk.Style()
    palette = getattr(app, "theme", None) or theme.palette_for(theme.detect_system_theme())
    theme.apply_ttk_theme(app.root, style, palette)

    control_frame = ttk.Frame(app.root)
    control_frame.pack(side=tk.TOP, fill=tk.X, padx=8, pady=4)

    if getattr(app, "status_label", None) is None:
        app.status_label = ttk.Label(app.root)
    app.clock_label = None
    app.status_info_label = None

    main_frame = ttk.Frame(app.root)
    main_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=4)
    app.main_frame = main_frame

    notebook = ttk.Notebook(main_frame)
    notebook.pack(fill=tk.BOTH, expand=True)
    app.main_notebook = notebook

    # Tab 1: Trend chart
    trend_tab.build_trend_tab(app, notebook)

    # Tab 2: Position controls
    position_tab.build_position_tab(app, notebook)

    # Tab 3: Strategy
    strategy_tab.build_strategy_tab(app, notebook, app.tooltip_cls)

    # Tab 4: Contract
    contract_tab.build_contract_tab(app, notebook)

    # Tab 5: Algorithm – per-mechanism parameter & formula editors
    algo_tab.build_algo_tab(app, notebook)

    # Tab 6: Order
    order_tab.build_order_tab(app, notebook)

    # Tab 7: Backtest
    backtest_tab.build_backtest_tab(app, notebook)

    # Tab 8: Test
    test_tab.build_test_tab(app, notebook)

    # Tab 9: Analysis
    analysis_tab.build_analysis_tab(app, notebook)

    # Tab 10: MACD Data viewer
    macd_data_tab.build_macd_data_tab(app, notebook)
