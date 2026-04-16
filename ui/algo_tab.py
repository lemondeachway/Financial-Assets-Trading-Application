"""
Helpers for building the Algorithm tab UI (parameter editors).
"""
import tkinter as tk
from tkinter import ttk
from typing import Any, List, Tuple


def build_algo_tab(app: Any, notebook) -> None:
    """
    Build the Algorithm tab with M1/M2 parameter and formula editors.
    Relies on app._build_algo_tab to render individual sub-tabs.
    """
    algo_tab = ttk.Frame(notebook)
    notebook.add(algo_tab, text="Algorithm")

    algo_notebook = ttk.Notebook(algo_tab)
    algo_notebook.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

    app._build_algo_tab(algo_notebook, "M1", [
        ("Window", "me1_window", int),
        ("Band", "me1_band", float),
        ("Stop", "me1_stop", float),
    ], "me1_formula", ["me1_prev_dist", "me1_prices"])

    app._build_algo_tab(algo_notebook, "M2", [
        ("Window", "me2_window", int),
        ("Band", "me2_band", float),
        ("Stop", "me2_stop", float),
    ], "me2_formula", ["me2_prev_dist", "me2_prices"])

    # M3: MACD+ATR params
    app._build_algo_tab(algo_notebook, "M3", [
        ("Point value", ("macd_atr_params", "point_value"), float),
        ("Tick size", ("macd_atr_params", "tick_size"), float),
        ("Risk per trade", ("macd_atr_params", "risk_per_trade"), float),
        ("k_SL", ("macd_atr_params", "k_SL"), float),
        ("k_TP", ("macd_atr_params", "k_TP"), float),
        ("ATR min factor", ("macd_atr_params", "atr_min_factor"), float),
        ("ATR max factor", ("macd_atr_params", "atr_max_factor"), float),
        ("Max bars", ("macd_atr_params", "max_bars_in_trade"), int),
        ("Daily loss frac", ("macd_atr_params", "daily_loss_frac"), float),
        ("ATR window", ("macd_atr_params", "atr_window"), int),
        ("Initial equity", ("macd_atr_params", "initial_equity"), float),
    ], None, [])

    # M4: MACD mode
    build_m4_tab(app, algo_notebook)


def build_algo_subtab(app: Any, notebook: ttk.Notebook, title: str,
                      fields: List[Tuple[str, Any, type]], formula_attr: str,
                      state_vars: List[str]) -> None:
    """
    Standalone helper mirroring app._build_algo_tab for reuse if needed.
    """
    tab = ttk.Frame(notebook)
    notebook.add(tab, text=title)

    form_frame = ttk.LabelFrame(tab, text="Parameters")
    form_frame.pack(side=tk.TOP, fill=tk.X, padx=4, pady=4)

    entries: List[Tuple[ttk.Entry, str, type]] = []
    for label, attr, typ in fields:
        row = ttk.Frame(form_frame)
        row.pack(side=tk.TOP, fill=tk.X, padx=4, pady=2)
        ttk.Label(row, text=label, width=14).pack(side=tk.LEFT)
        if isinstance(attr, tuple):
            container_name, key = attr
            container = getattr(app, container_name)
            val = container.get(key)
        else:
            val = getattr(app, attr)
        var = tk.StringVar(value=str(val))
        ent = ttk.Entry(row, textvariable=var, width=12)
        ent.pack(side=tk.LEFT)
        entries.append((ent, attr, typ))

    def apply_params() -> None:
        for ent, attr, typ in entries:
            txt = ent.get().strip()
            try:
                val = typ(txt)
                if isinstance(attr, tuple):
                    container_name, key = attr
                    container = getattr(app, container_name)
                    container[key] = val
                else:
                    setattr(app, attr, val)
            except Exception:
                ent.delete(0, tk.END)
                if isinstance(attr, tuple):
                    container_name, key = attr
                    container = getattr(app, container_name)
                    ent.insert(0, str(container.get(key)))
                else:
                    ent.insert(0, str(getattr(app, attr)))

    ttk.Button(form_frame, text="Apply Params", command=apply_params).pack(side=tk.LEFT, padx=6, pady=4)

    info_frame = ttk.LabelFrame(tab, text="Current Parameters / Variables")
    info_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=4, pady=4)
    info_txt = tk.Text(info_frame, height=6, wrap="word")
    info_txt.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

    def fmt_value(name: Any) -> str:
        if isinstance(name, tuple):
            container_name, key = name
            container = getattr(app, container_name, {})
            val = container.get(key)
            return f"{container_name}[{key}]: {val}"
        val = getattr(app, name, None)
        if isinstance(val, list):
            return f"{name}: len={len(val)} values={val[-5:]}" if val else f"{name}: []"
        return f"{name}: {val}"

    def refresh_info() -> None:
        lines = [fmt_value(attr) for _, attr, _ in fields]
        lines += [fmt_value(name) for name in state_vars]
        info_txt.configure(state="normal")
        info_txt.delete("1.0", tk.END)
        info_txt.insert("1.0", "\n".join(lines))
        info_txt.configure(state="disabled")

    ttk.Button(info_frame, text="Refresh", command=refresh_info).pack(side=tk.BOTTOM, anchor="e", padx=6, pady=4)
    refresh_info()

    if formula_attr:
        formula_frame = ttk.LabelFrame(tab, text="Formula")
        formula_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=4, pady=4)
        txt = tk.Text(formula_frame, height=6, wrap="word")
        txt.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        txt.insert("1.0", getattr(app, formula_attr))

        def apply_formula() -> None:
            setattr(app, formula_attr, txt.get("1.0", tk.END).strip())

        ttk.Button(formula_frame, text="Apply Formula", command=apply_formula).pack(side=tk.BOTTOM, anchor="e", padx=6, pady=4)


def build_m4_tab(app: Any, notebook: ttk.Notebook) -> None:
    """
    Custom sub-tab for M4 with risk toggles (TP/SL) and parameters.
    """
    tab = ttk.Frame(notebook)
    notebook.add(tab, text="M4")

    form_frame = ttk.LabelFrame(tab, text="Parameters")
    form_frame.pack(side=tk.TOP, fill=tk.X, padx=4, pady=4)

    fields: List[Tuple[str, tuple[str, str], type]] = [
        ("Ensure window", ("m4_params", "ensure_window"), int),
        ("Take profit", ("m4_params", "take_profit"), float),
        ("Stop loss", ("m4_params", "stop_loss"), float),
    ]
    entries: List[Tuple[ttk.Entry, tuple[str, str], type]] = []
    for label, attr, typ in fields:
        row = ttk.Frame(form_frame)
        row.pack(side=tk.TOP, fill=tk.X, padx=4, pady=2)
        ttk.Label(row, text=label, width=14).pack(side=tk.LEFT)
        container_name, key = attr
        container = getattr(app, container_name)
        val = container.get(key)
        var = tk.StringVar(value=str(val))
        ent = ttk.Entry(row, textvariable=var, width=12)
        ent.pack(side=tk.LEFT)
        entries.append((ent, attr, typ))

    def apply_params() -> None:
        for ent, attr, typ in entries:
            txt = ent.get().strip()
            try:
                val = typ(txt)
                container_name, key = attr
                container = getattr(app, container_name)
                container[key] = val
            except Exception:
                container_name, key = attr
                container = getattr(app, container_name)
                ent.delete(0, tk.END)
                ent.insert(0, str(container.get(key)))

    ttk.Button(form_frame, text="Apply Params", command=apply_params).pack(side=tk.LEFT, padx=6, pady=4)

    risk_frame = ttk.LabelFrame(tab, text="Risk Management")
    risk_frame.pack(side=tk.TOP, fill=tk.X, padx=4, pady=4)
    ttk.Checkbutton(risk_frame, text="Enable Take Profit", variable=app.m4_use_take_profit).pack(
        side=tk.TOP, anchor="w", padx=6, pady=2
    )
    ttk.Checkbutton(risk_frame, text="Enable Stop Loss", variable=app.m4_use_stop_loss).pack(
        side=tk.TOP, anchor="w", padx=6, pady=2
    )
    ttk.Label(risk_frame, text="Stop loss accepts negative values.", foreground="#666666").pack(
        side=tk.TOP, anchor="w", padx=8, pady=(0, 2)
    )

    info_frame = ttk.LabelFrame(tab, text="Current Parameters / Variables")
    info_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=4, pady=4)
    info_txt = tk.Text(info_frame, height=6, wrap="word")
    info_txt.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

    def fmt_value(attr: tuple[str, str]) -> str:
        container_name, key = attr
        container = getattr(app, container_name, {})
        val = container.get(key)
        return f"{container_name}[{key}]: {val}"

    def refresh_info() -> None:
        lines = [fmt_value(attr) for _, attr, _ in fields]
        lines.append(f"m4_state: {getattr(app, 'm4_state', {})}")
        lines.append(f"TP enabled: {getattr(app, 'm4_use_take_profit', None).get() if getattr(app, 'm4_use_take_profit', None) else False}")
        lines.append(f"SL enabled: {getattr(app, 'm4_use_stop_loss', None).get() if getattr(app, 'm4_use_stop_loss', None) else False}")
        info_txt.configure(state="normal")
        info_txt.delete("1.0", tk.END)
        info_txt.insert("1.0", "\n".join(lines))
        info_txt.configure(state="disabled")

    ttk.Button(info_frame, text="Refresh", command=refresh_info).pack(side=tk.BOTTOM, anchor="e", padx=6, pady=4)
    refresh_info()
