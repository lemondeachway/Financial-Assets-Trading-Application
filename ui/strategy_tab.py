"""
Helpers for building the Strategy tab UI (toggles, sim P&L, logic log).
"""
import tkinter as tk
from tkinter import ttk
from typing import Any, Type


def build_strategy_tab(app: Any, notebook, tooltip_cls: Type) -> None:
    """
    Build the Strategy tab and attach state onto the app instance.
    """
    strategy_tab = ttk.Frame(notebook)
    notebook.add(strategy_tab, text="Strategy")

    # Use default ttk Checkbutton style (no custom toggle styling)

    toggles_frame = ttk.LabelFrame(strategy_tab, text="Strategy Toggles")
    toggles_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 4), padx=4)

    # Real toggles
    app.use_me3 = tk.BooleanVar(value=False)
    app.use_me8 = tk.BooleanVar(value=False)
    app.use_me_macd_atr = tk.BooleanVar(value=False)
    app.use_alt_settlement_var = tk.BooleanVar(value=False)
    # Sim toggles
    app.use_me3_sim = tk.BooleanVar(value=False)
    app.use_me8_sim = tk.BooleanVar(value=False)
    app.enable_command_output = tk.BooleanVar(value=False)

    ttk.Label(toggles_frame, text="Live", font=("", 10, "bold")).grid(row=0, column=0, sticky="w", padx=4, pady=(2, 1))
    ttk.Label(toggles_frame, text="Sim", font=("", 10, "bold")).grid(row=0, column=1, sticky="w", padx=4, pady=(2, 1))

    cb_me3 = ttk.Checkbutton(toggles_frame, text="M1: Mean Revert", variable=app.use_me3)
    cb_me3.grid(row=1, column=0, sticky="w", padx=6, pady=1)
    cb_me3_sim = ttk.Checkbutton(toggles_frame, text="M1 (Sim)", variable=app.use_me3_sim)
    cb_me3_sim.grid(row=1, column=1, sticky="w", padx=6, pady=1)

    cb_me8 = ttk.Checkbutton(toggles_frame, text="M2: Inverse MR", variable=app.use_me8)
    cb_me8.grid(row=2, column=0, sticky="w", padx=6, pady=1)
    cb_me8_sim = ttk.Checkbutton(toggles_frame, text="M2 (Sim)", variable=app.use_me8_sim)
    cb_me8_sim.grid(row=2, column=1, sticky="w", padx=6, pady=1)

    cb_me_macd_atr = ttk.Checkbutton(toggles_frame, text="M3: MACD+ATR Trend", variable=app.use_me_macd_atr)
    cb_me_macd_atr.grid(row=3, column=0, sticky="w", padx=6, pady=1)
    cb_me4 = ttk.Checkbutton(toggles_frame, text="M4: MACD Mode", variable=app.use_me4)
    cb_me4.grid(row=4, column=0, sticky="w", padx=6, pady=1)
    cb_alt_settlement = ttk.Checkbutton(
        toggles_frame,
        text="Alt settlement calc",
        variable=app.use_alt_settlement_var,
        command=getattr(app, "_toggle_alt_settlement", lambda: None),
    )
    cb_alt_settlement.grid(row=5, column=0, sticky="w", padx=6, pady=1)
    alt_factor_frame = ttk.Frame(toggles_frame)
    alt_factor_frame.grid(row=6, column=0, sticky="w", padx=6, pady=1)
    ttk.Label(alt_factor_frame, text="Alt settle ticks").pack(side=tk.LEFT)
    ttk.Entry(
        alt_factor_frame,
        textvariable=app.alt_settlement_tick_factor_var,
        width=6,
        style="Dark.TEntry",
    ).pack(side=tk.LEFT, padx=(4, 0))

    cb_cmd = ttk.Checkbutton(
        toggles_frame,
        text="Execute orders",
        variable=app.enable_command_output,
        style="TCheckbutton",
    )
    cb_cmd.grid(row=3, column=1, sticky="w", padx=6, pady=1)

    # Tooltips for mechanism explanations
    tooltip_cls(
        cb_me3,
        "Mechanism 1 – Mean Reversion:\n"
        "- Track simple moving average (SMA) of last N prices.\n"
        "- Open long when price is far BELOW SMA by a band.\n"
        "- Open short when price is far ABOVE SMA by a band.\n"
        "- Close when price returns to SMA or hits stop-loss."
    )
    tooltip_cls(
        cb_me8,
        "Mechanism 2 – Inverse Mean Reversion:\n"
        "- Same inputs as M1 (window, band, stop).\n"
        "- Opens SHORT when price is below SMA by the band; opens LONG when price is above.\n"
        "- Closes when price returns to SMA or hits stop in the opposite direction."
    )
    tooltip_cls(
        cb_me_macd_atr,
        "Mechanism 3 – MACD + ATR trend/momentum:\n"
        "- Uses MACD(12,26,9) hist cross with DIF sign, ATR filter around median.\n"
        "- Stop/TP based on ATR multiples; holds up to max bars.\n"
        "- Position sizing simplified to 1 contract per signal."
    )
    tooltip_cls(
        cb_cmd,
        "When enabled, every open/close trade writes a small command file\n"
        "into a 'commands' folder next to lpc.py.\n"
        "External tools on Windows can watch that folder and simulate mouse clicks.\n"
        "Backtests automatically suppress command writing."
    )

    # Sim P&L summary
    sim_frame = ttk.LabelFrame(strategy_tab, text="Sim P&L")
    sim_frame.pack(side=tk.TOP, fill=tk.X, padx=4, pady=4)
    app.sim_labels = {}
    for mech in ["M1", "M2"]:
        lbl = ttk.Label(sim_frame, text=f"{mech}: 0.00")
        lbl.pack(side=tk.LEFT, padx=4)
        app.sim_labels[mech] = lbl

    # Strategy logic log area
    logic_frame = ttk.LabelFrame(strategy_tab, text="Strategy Logic")
    logic_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(0, 4))

    logic_columns = ("time", "mechanism", "message")
    app.logic_tree = ttk.Treeview(logic_frame, columns=logic_columns, show="headings", height=4)
    app.logic_tree.heading("time", text="Time")
    app.logic_tree.heading("mechanism", text="Mech")
    app.logic_tree.heading("message", text="Logic")

    app.logic_tree.column("time", width=140, anchor=tk.W, stretch=False)
    app.logic_tree.column("mechanism", width=60, anchor=tk.W, stretch=False)
    app.logic_tree.column("message", width=420, anchor=tk.W, stretch=True)

    vsb_logic = ttk.Scrollbar(logic_frame, orient="vertical", command=app.logic_tree.yview)
    app.logic_tree.configure(yscrollcommand=vsb_logic.set)

    app.logic_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    vsb_logic.pack(side=tk.RIGHT, fill=tk.Y)
