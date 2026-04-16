"""
Helpers for building the Contract tab UI (NR and CL data/info).
"""
import tkinter as tk
from tkinter import ttk
from typing import Any


def build_contract_tab(app: Any, notebook) -> None:
    """
    Build the Contract tab (NR + CL subtabs) and attach widgets to the app.
    """
    contract_tab = ttk.Frame(notebook)
    notebook.add(contract_tab, text="Contract")

    contract_notebook = ttk.Notebook(contract_tab)
    contract_notebook.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

    futures_tab = ttk.Frame(contract_notebook)
    contract_notebook.add(futures_tab, text="Futures")
    futures_notebook = ttk.Notebook(futures_tab)
    futures_notebook.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

    nr_outer_tab = ttk.Frame(futures_notebook)
    futures_notebook.add(nr_outer_tab, text="NR")

    nr_notebook = ttk.Notebook(nr_outer_tab)
    nr_notebook.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

    nr_tab = ttk.Frame(nr_notebook)
    nr_notebook.add(nr_tab, text="Data")

    btn_bar = ttk.Frame(nr_tab)
    btn_bar.pack(side=tk.TOP, fill=tk.X, padx=4, pady=(4, 2))

    app.start_button = ttk.Button(btn_bar, text="Start", command=app.start_feed, style="Dark.TButton")
    app.start_button.pack(side=tk.LEFT, padx=4)

    app.stop_button = ttk.Button(btn_bar, text="Stop", command=app.stop_feed, style="Dark.TButton")
    app.stop_button.pack(side=tk.LEFT, padx=4)

    settings_bar = ttk.LabelFrame(nr_tab, text="Data Settings")
    settings_bar.pack(side=tk.TOP, fill=tk.X, padx=4, pady=(2, 6))

    ttk.Label(settings_bar, text="Symbol").pack(side=tk.LEFT, padx=(4, 2))
    ttk.Entry(settings_bar, textvariable=app.symbol_var, width=10, style="Dark.TEntry").pack(side=tk.LEFT, padx=(0, 6))

    ttk.Label(settings_bar, text="URL").pack(side=tk.LEFT, padx=(4, 2))
    ttk.Entry(settings_bar, textvariable=app.url_var, width=36, style="Dark.TEntry").pack(side=tk.LEFT, padx=(0, 6))

    ttk.Label(settings_bar, text="Interval (s)").pack(side=tk.LEFT, padx=(4, 2))
    ttk.Entry(settings_bar, textvariable=app.interval_var, width=8, style="Dark.TEntry").pack(side=tk.LEFT, padx=(0, 6))

    ttk.Button(settings_bar, text="Apply", command=app.apply_data_settings, style="Dark.TButton").pack(side=tk.LEFT, padx=4)

    sim_frame = ttk.Frame(nr_tab)
    sim_frame.pack(side=tk.TOP, fill=tk.X, padx=4, pady=(0, 6))
    ttk.Checkbutton(sim_frame, text="Simulated feed", variable=app.sim_mode_var, style="Dark.TCheckbutton").pack(
        side=tk.LEFT, padx=(0, 8)
    )
    ttk.Button(sim_frame, text="Load sim CSV", command=app._choose_sim_csv, style="Dark.TButton").pack(side=tk.LEFT, padx=4)
    ttk.Label(sim_frame, text="Speed x").pack(side=tk.LEFT, padx=(8, 2))
    ttk.Entry(sim_frame, textvariable=app.sim_speed_var, width=6, style="Dark.TEntry").pack(side=tk.LEFT, padx=(0, 4))
    ttk.Label(sim_frame, text="Base").pack(side=tk.LEFT, padx=(8, 2))
    ttk.Entry(sim_frame, textvariable=app.sim_base_price_var, width=8, style="Dark.TEntry").pack(side=tk.LEFT, padx=(0, 4))
    ttk.Label(sim_frame, text="ATR").pack(side=tk.LEFT, padx=(8, 2))
    ttk.Entry(sim_frame, textvariable=app.sim_atr_var, width=8, style="Dark.TEntry").pack(side=tk.LEFT, padx=(0, 4))
    ttk.Label(sim_frame, text="Jump p").pack(side=tk.LEFT, padx=(8, 2))
    ttk.Entry(sim_frame, textvariable=app.sim_jump_prob_var, width=5, style="Dark.TEntry").pack(side=tk.LEFT, padx=(0, 4))
    ttk.Label(sim_frame, text="Jump sz").pack(side=tk.LEFT, padx=(8, 2))
    ttk.Entry(sim_frame, textvariable=app.sim_jump_scale_var, width=6, style="Dark.TEntry").pack(side=tk.LEFT, padx=(0, 4))
    ttk.Checkbutton(sim_frame, text="Randomize", variable=app.sim_random_var, style="Dark.TCheckbutton").pack(side=tk.LEFT, padx=(8, 2))

    # CSV save path selector
    path_row = ttk.Frame(nr_tab)
    path_row.pack(side=tk.TOP, fill=tk.X, padx=4, pady=(0, 6))
    ttk.Label(path_row, text="Save to").pack(side=tk.LEFT, padx=(0, 4))
    ttk.Entry(path_row, textvariable=app.csv_dir_var, width=40, style="Dark.TEntry").pack(side=tk.LEFT, padx=(0, 4), fill=tk.X, expand=True)
    ttk.Button(path_row, text="Browse", command=app._choose_csv_dir, style="Dark.TButton").pack(side=tk.LEFT, padx=4)

    tick_frame = ttk.LabelFrame(nr_tab, text="Last Price")
    tick_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    columns = ("time", "last")
    app.tree = ttk.Treeview(tick_frame, columns=columns, show="headings", height=6)
    app.tree.heading("time", text="Time")
    app.tree.heading("last", text="Last Price")

    app.tree.column("time", width=180, anchor=tk.W)
    app.tree.column("last", width=90, anchor=tk.E)

    vsb_left = ttk.Scrollbar(tick_frame, orient="vertical", command=app.tree.yview)
    app.tree.configure(yscrollcommand=vsb_left.set)

    app.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    vsb_left.pack(side=tk.RIGHT, fill=tk.Y)

    app.raw_fields_label = ttk.Label(nr_tab, text="Raw fields: --", anchor="w")
    app.raw_fields_label.pack(side=tk.TOP, fill=tk.X, padx=6, pady=(4, 2))

    # Contract -> NR -> Info subtab
    info_subtab = ttk.Frame(nr_notebook)
    nr_notebook.add(info_subtab, text="Info")

    info_frame = ttk.LabelFrame(info_subtab, text="Contract Info")
    info_frame.pack(side=tk.TOP, fill=tk.X, padx=8, pady=8)

    app.contract_symbol_label = ttk.Label(
        info_frame, text=f"Symbol: {getattr(app, 'symbol', '')}", anchor="w"
    )
    app.contract_symbol_label.pack(side=tk.TOP, anchor="w", padx=6, pady=2)

    fee_row = ttk.Frame(info_frame)
    fee_row.pack(side=tk.TOP, fill=tk.X, padx=6, pady=2)
    ttk.Label(fee_row, text="Trade fee").pack(side=tk.LEFT, padx=(0, 6))
    app.trade_fee_var = tk.StringVar(value=str(getattr(app, "trade_fee", 0.0)))
    ttk.Entry(fee_row, textvariable=app.trade_fee_var, width=10, style="Dark.TEntry").pack(side=tk.LEFT)

    tick_row = ttk.Frame(info_frame)
    tick_row.pack(side=tk.TOP, fill=tk.X, padx=6, pady=2)
    ttk.Label(tick_row, text="Tick size").pack(side=tk.LEFT, padx=(0, 6))
    app.tick_size_var = tk.StringVar(value=str(getattr(app, "tick_size", 5.0)))
    ttk.Entry(tick_row, textvariable=app.tick_size_var, width=10, style="Dark.TEntry").pack(side=tk.LEFT)

    lev_row = ttk.Frame(info_frame)
    lev_row.pack(side=tk.TOP, fill=tk.X, padx=6, pady=2)
    ttk.Label(lev_row, text="Contract multiplier").pack(side=tk.LEFT, padx=(0, 6))
    app.leverage_var = tk.StringVar(value=str(getattr(app, "leverage", 10.0)))
    ttk.Entry(lev_row, textvariable=app.leverage_var, width=10, style="Dark.TEntry").pack(side=tk.LEFT)

    margin_row = ttk.Frame(info_frame)
    margin_row.pack(side=tk.TOP, fill=tk.X, padx=6, pady=2)
    ttk.Label(margin_row, text="Equity").pack(side=tk.LEFT, padx=(0, 6))
    app.equity_var = tk.StringVar(value=str(getattr(app, "equity", 0.0)))
    ttk.Entry(margin_row, textvariable=app.equity_var, width=12, style="Dark.TEntry").pack(side=tk.LEFT)

    qty_row = ttk.Frame(info_frame)
    qty_row.pack(side=tk.TOP, fill=tk.X, padx=6, pady=2)
    ttk.Label(qty_row, text="Order quantity").pack(side=tk.LEFT, padx=(0, 6))
    app.order_qty_var = tk.StringVar(value=str(getattr(app, "order_qty", 1)))
    ttk.Entry(qty_row, textvariable=app.order_qty_var, width=10, style="Dark.TEntry").pack(side=tk.LEFT)

    ratio_row = ttk.Frame(info_frame)
    ratio_row.pack(side=tk.TOP, fill=tk.X, padx=6, pady=2)
    ttk.Label(ratio_row, text="Long margin ratio").pack(side=tk.LEFT, padx=(0, 6))
    app.long_margin_ratio_var = tk.StringVar(value=str(getattr(app, "long_margin_ratio", 0.14)))
    ttk.Entry(ratio_row, textvariable=app.long_margin_ratio_var, width=8, style="Dark.TEntry").pack(side=tk.LEFT)
    ttk.Label(ratio_row, text="Short margin ratio").pack(side=tk.LEFT, padx=(10, 6))
    app.short_margin_ratio_var = tk.StringVar(value=str(getattr(app, "short_margin_ratio", 0.14)))
    ttk.Entry(ratio_row, textvariable=app.short_margin_ratio_var, width=8, style="Dark.TEntry").pack(side=tk.LEFT)

    init_row = ttk.Frame(info_frame)
    init_row.pack(side=tk.TOP, fill=tk.X, padx=6, pady=2)
    app.long_init_margin_var = tk.StringVar(value="--")
    app.short_init_margin_var = tk.StringVar(value="--")
    ttk.Label(init_row, text="Long initial margin/contract").pack(side=tk.LEFT, padx=(0, 6))
    ttk.Label(init_row, textvariable=app.long_init_margin_var).pack(side=tk.LEFT)
    ttk.Label(init_row, text="Short initial margin/contract").pack(side=tk.LEFT, padx=(12, 6))
    ttk.Label(init_row, textvariable=app.short_init_margin_var).pack(side=tk.LEFT)

    fee_mode_row = ttk.Frame(info_frame)
    fee_mode_row.pack(side=tk.TOP, fill=tk.X, padx=6, pady=2)
    ttk.Label(fee_mode_row, text="Fee mode").pack(side=tk.LEFT, padx=(0, 6))
    app.trade_fee_mode_var = tk.StringVar(value=getattr(app, "trade_fee_mode", "fixed"))
    fee_mode_combo = ttk.Combobox(
        fee_mode_row,
        textvariable=app.trade_fee_mode_var,
        values=("fixed", "percent"),
        width=10,
        state="readonly",
        style="Dark.TCombobox",
    )
    fee_mode_combo.pack(side=tk.LEFT, padx=(0, 8))
    ttk.Label(fee_mode_row, text="Percent (when percent mode)").pack(side=tk.LEFT, padx=(0, 6))
    app.trade_fee_pct_var = tk.StringVar(value=str(getattr(app, "trade_fee_pct", 0.0)))
    ttk.Entry(fee_mode_row, textvariable=app.trade_fee_pct_var, width=10, style="Dark.TEntry").pack(side=tk.LEFT)
    ttk.Checkbutton(
        fee_mode_row,
        text="No close-today fee",
        variable=app.no_close_today_fee_var,
        style="Dark.TCheckbutton",
    ).pack(side=tk.LEFT, padx=(12, 0))

    ttk.Button(info_frame, text="Apply", command=app.apply_contract_info, style="Dark.TButton").pack(side=tk.TOP, anchor="w", padx=6, pady=4)

    cl_outer_tab = ttk.Frame(futures_notebook)
    futures_notebook.add(cl_outer_tab, text="CL")

    cl_notebook = ttk.Notebook(cl_outer_tab)
    cl_notebook.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

    cl_data_tab = ttk.Frame(cl_notebook)
    cl_notebook.add(cl_data_tab, text="Data")

    cl_btn_bar = ttk.Frame(cl_data_tab)
    cl_btn_bar.pack(side=tk.TOP, fill=tk.X, padx=4, pady=(4, 2))
    app.start_button_cl = ttk.Button(cl_btn_bar, text="Start", command=app.start_feed_cl, style="Dark.TButton")
    app.start_button_cl.pack(side=tk.LEFT, padx=4)
    app.stop_button_cl = ttk.Button(cl_btn_bar, text="Stop", command=app.stop_feed_cl, style="Dark.TButton")
    app.stop_button_cl.pack(side=tk.LEFT, padx=4)

    cl_settings_bar = ttk.LabelFrame(cl_data_tab, text="Data Settings")
    cl_settings_bar.pack(side=tk.TOP, fill=tk.X, padx=4, pady=(2, 6))
    ttk.Label(cl_settings_bar, text="Symbol").pack(side=tk.LEFT, padx=(4, 2))
    ttk.Entry(cl_settings_bar, textvariable=app.symbol_cl_var, width=10, style="Dark.TEntry").pack(side=tk.LEFT, padx=(0, 6))
    ttk.Label(cl_settings_bar, text="URL").pack(side=tk.LEFT, padx=(4, 2))
    ttk.Entry(cl_settings_bar, textvariable=app.url_cl_var, width=36, style="Dark.TEntry").pack(side=tk.LEFT, padx=(0, 6))
    ttk.Label(cl_settings_bar, text="Interval (s)").pack(side=tk.LEFT, padx=(4, 2))
    ttk.Entry(cl_settings_bar, textvariable=app.interval_cl_var, width=8, style="Dark.TEntry").pack(side=tk.LEFT, padx=(0, 6))
    ttk.Button(cl_settings_bar, text="Apply", command=app.apply_data_settings_cl, style="Dark.TButton").pack(side=tk.LEFT, padx=4)

    cl_path_row = ttk.Frame(cl_data_tab)
    cl_path_row.pack(side=tk.TOP, fill=tk.X, padx=4, pady=(0, 6))
    ttk.Label(cl_path_row, text="Save to").pack(side=tk.LEFT, padx=(0, 4))
    ttk.Entry(cl_path_row, textvariable=app.csv_dir_cl_var, width=40, style="Dark.TEntry").pack(side=tk.LEFT, padx=(0, 4), fill=tk.X, expand=True)
    ttk.Button(cl_path_row, text="Browse", command=app._choose_csv_dir_cl, style="Dark.TButton").pack(side=tk.LEFT, padx=4)

    cl_tick_frame = ttk.LabelFrame(cl_data_tab, text="Last Price")
    cl_tick_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
    cl_columns = ("time", "last")
    app.tree_cl = ttk.Treeview(cl_tick_frame, columns=cl_columns, show="headings", height=6)
    app.tree_cl.heading("time", text="Time")
    app.tree_cl.heading("last", text="Last Price")
    app.tree_cl.column("time", width=180, anchor=tk.W)
    app.tree_cl.column("last", width=90, anchor=tk.E)
    vsb_cl = ttk.Scrollbar(cl_tick_frame, orient="vertical", command=app.tree_cl.yview)
    app.tree_cl.configure(yscrollcommand=vsb_cl.set)
    app.tree_cl.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    vsb_cl.pack(side=tk.RIGHT, fill=tk.Y)
    app.raw_fields_label_cl = ttk.Label(cl_data_tab, text="Raw fields: --", anchor="w")
    app.raw_fields_label_cl.pack(side=tk.TOP, fill=tk.X, padx=6, pady=(4, 2))

    cl_info_tab = ttk.Frame(cl_notebook)
    cl_notebook.add(cl_info_tab, text="Info")
    cl_info_frame = ttk.LabelFrame(cl_info_tab, text="Contract Info (CL)")
    cl_info_frame.pack(side=tk.TOP, fill=tk.X, padx=8, pady=8)
    ttk.Label(cl_info_frame, text="Symbol: CL", anchor="w").pack(side=tk.TOP, anchor="w", padx=6, pady=2)
    ttk.Label(cl_info_frame, text="Tick size: 0.001", anchor="w").pack(side=tk.TOP, anchor="w", padx=6, pady=2)

    options_tab = ttk.Frame(contract_notebook)
    contract_notebook.add(options_tab, text="Options")

    chain_frame = ttk.LabelFrame(options_tab, text="Option Chain")
    chain_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 4))
    chain_controls = ttk.Frame(chain_frame)
    chain_controls.pack(side=tk.TOP, fill=tk.X, padx=6, pady=4)
    ttk.Label(chain_controls, text="Product").pack(side=tk.LEFT, padx=(0, 2))
    ttk.Entry(chain_controls, textvariable=app.option_product_var, width=6, style="Dark.TEntry").pack(side=tk.LEFT, padx=(0, 6))
    ttk.Label(chain_controls, text="Exchange").pack(side=tk.LEFT, padx=(0, 2))
    ttk.Entry(chain_controls, textvariable=app.option_exchange_var, width=10, style="Dark.TEntry").pack(side=tk.LEFT, padx=(0, 6))
    ttk.Label(chain_controls, text="Pinzhong").pack(side=tk.LEFT, padx=(0, 2))
    ttk.Entry(chain_controls, textvariable=app.option_pinzhong_var, width=12, style="Dark.TEntry").pack(side=tk.LEFT, padx=(0, 6))
    ttk.Button(chain_controls, text="Fetch Chain", command=app._fetch_option_chain, style="Dark.TButton").pack(side=tk.RIGHT)
    chain_text_frame = ttk.Frame(chain_frame)
    chain_text_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))
    chain_vsb = ttk.Scrollbar(chain_text_frame, orient="vertical")
    chain_hsb = ttk.Scrollbar(chain_text_frame, orient="horizontal")
    app.option_chain_text = tk.Text(chain_text_frame, height=6, wrap="none", state="disabled")
    chain_vsb.config(command=app.option_chain_text.yview)
    chain_hsb.config(command=app.option_chain_text.xview)
    app.option_chain_text.config(yscrollcommand=chain_vsb.set, xscrollcommand=chain_hsb.set)
    app.option_chain_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    chain_vsb.pack(side=tk.RIGHT, fill=tk.Y)
    chain_hsb.pack(side=tk.BOTTOM, fill=tk.X)

    quote_frame = ttk.LabelFrame(options_tab, text="Option Quote")
    quote_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
    quote_controls = ttk.Frame(quote_frame)
    quote_controls.pack(side=tk.TOP, fill=tk.X, padx=6, pady=4)
    ttk.Label(quote_controls, text="Symbol").pack(side=tk.LEFT, padx=(0, 2))
    ttk.Entry(quote_controls, textvariable=app.option_quote_symbol_var, width=16, style="Dark.TEntry").pack(side=tk.LEFT, padx=(0, 6))
    ttk.Button(quote_controls, text="Fetch Quote", command=app._fetch_option_quote, style="Dark.TButton").pack(side=tk.RIGHT)
    quote_text_frame = ttk.Frame(quote_frame)
    quote_text_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))
    quote_vsb = ttk.Scrollbar(quote_text_frame, orient="vertical")
    app.option_quote_text = tk.Text(quote_text_frame, height=4, wrap="none", state="disabled")
    quote_vsb.config(command=app.option_quote_text.yview)
    app.option_quote_text.config(yscrollcommand=quote_vsb.set)
    app.option_quote_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    quote_vsb.pack(side=tk.RIGHT, fill=tk.Y)

    # Force layout for the new widgets so the Futures tab is preloaded.
    def _preload_futures(event=None) -> None:
        try:
            futures_notebook.update_idletasks()
            futures_tab.update_idletasks()
            contract_notebook.update_idletasks()
            if hasattr(app, "root") and app.root is not None:
                app.root.update_idletasks()
        except Exception:
            pass

    _preload_futures()
    contract_notebook.bind("<<NotebookTabChanged>>", lambda event: _preload_futures() if contract_notebook.select() == str(futures_tab) else None)
