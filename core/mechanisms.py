"""
Mechanism logic wrappers for M1/M2/M4.
"""
from typing import Any
from core import algorithms_strat, algorithms
import math

_M4_DEFAULT_STATE = {
    "mode": "observation",
    "counter": 0,        # validation counter for main modes
    "hold_counter": 0,   # validation counter inside holding modes
    "obs_pos": 0,        # consecutive DIF>0 & DEA>0 while observing
    "obs_neg": 0,        # consecutive DIF<0 & DEA<0 while observing
}


def _m4_log(app: Any, message: str) -> None:
    """Log a line to the Strategy Logic tab for M4."""
    try:
        app._log_logic("M4", message)
    except Exception:
        pass


def _reset_m4_state(app: Any, mode: str = "observation", counter: int = 0, log: str | None = None) -> None:
    """
    Reset M4 state to a given mode and counter, preserving a single active mode.
    Optionally log the transition.
    """
    try:
        state = getattr(app, "m4_state", {}) or {}
        state.update(_M4_DEFAULT_STATE)
        state["mode"] = mode
        state["counter"] = counter
        state["hold_counter"] = 0
        state["obs_pos"] = 0 if mode != "observation" else state.get("obs_pos", 0)
        state["obs_neg"] = 0 if mode != "observation" else state.get("obs_neg", 0)
        app.m4_state = state
        if log:
            _m4_log(app, log)
    except Exception:
        pass


def _ensure_m4_state(app: Any) -> dict:
    """
    Guarantee m4_state dict has required keys and a valid mode.
    """
    state = getattr(app, "m4_state", {}) or {}
    for k, v in _M4_DEFAULT_STATE.items():
        state.setdefault(k, v)
    if state.get("mode") not in {
        "observation",
        "gradual_long",
        "gradual_short",
        "long_validation",
        "short_validation",
        "long_trading",
        "short_trading",
        "hold_long",
        "hold_short",
    }:
        state["mode"] = "observation"
    app.m4_state = state
    return state


def mechanism4_macd_mode_logic(app: Any) -> None:
    """
    Mechanism 4: MACD mode state machine driven by DIF/DEA stream.
    Implements the Observation → Gradual → Validation → Trading → Holding flows
    for both long and short sides using ensure_window consecutive MACD checks.
    """
    if not getattr(app, "use_me4", None) or not app.use_me4.get():
        return
    try:
        ensure_window = max(1, int(app.m4_params.get("ensure_window", 3)))
    except Exception:
        ensure_window = 3
    tp_enabled = bool(getattr(app, "m4_use_take_profit", None).get()) if getattr(app, "m4_use_take_profit", None) else False
    sl_enabled = bool(getattr(app, "m4_use_stop_loss", None).get()) if getattr(app, "m4_use_stop_loss", None) else False
    tp_val = None
    sl_val = None
    try:
        tp_val = float(app.m4_params.get("take_profit", 0.0))
    except Exception:
        tp_val = None
    try:
        sl_val = float(app.m4_params.get("stop_loss", 0.0))
    except Exception:
        sl_val = None

    # Risk controls: TP/SL based on current open trade equity
    if (tp_enabled or sl_enabled) and getattr(app, "open_positions", None):
        try:
            ote_val = float(app._compute_ote())
        except Exception:
            ote_val = None
        trigger = None
        if tp_enabled and tp_val is not None and ote_val is not None and ote_val >= tp_val:
            trigger = ("Take Profit", tp_val)
        elif sl_enabled and sl_val is not None and ote_val is not None and ote_val <= sl_val:
            trigger = ("Stop Loss", sl_val)
        if trigger:
            reason, threshold = trigger
            side = None
            for pos in getattr(app, "open_positions", []):
                if pos.get("owner") == "M4":
                    side = pos.get("side")
                    break
            if side is None and getattr(app, "open_positions", None):
                side = app.open_positions[0].get("side")

            if side == "long":
                app.close_long(owner="M4")
                _m4_log(app, f"{reason}: close LONG (OTE {ote_val:.2f} vs {threshold}) → Enter Short Trend")
                app.open_short(owner="M4")
                _reset_m4_state(app, "hold_short", 0, log="Opened SHORT after risk trigger → Holding Short")
                return
            if side == "short":
                app.close_short(owner="M4")
                _m4_log(app, f"{reason}: close SHORT (OTE {ote_val:.2f} vs {threshold}) → Enter Long Trend")
                app.open_long(owner="M4")
                _reset_m4_state(app, "hold_long", 0, log="Opened LONG after risk trigger → Holding Long")
                return

    state = _ensure_m4_state(app)
    mode = state["mode"]

    # Get latest MACD values from current active series
    times, prices = app._active_series()
    if not prices:
        return
    macd_hist, difs, deas = app._macd_series_for(times, prices)
    if not difs or not deas:
        return
    dif = difs[-1]
    dea = deas[-1]

    cond_pos = dif > 0 and dea > 0
    cond_neg = dif < 0 and dea < 0
    cond_long_validation = dif > dea and dif < 0
    cond_short_validation = dif < dea and dif > 0

    # --- Observation: look for consistent sign to seed a trend bias ---
    if mode == "observation":
        state["obs_pos"] = state.get("obs_pos", 0) + 1 if cond_pos else 0
        state["obs_neg"] = state.get("obs_neg", 0) + 1 if cond_neg else 0
        if state["obs_pos"] >= ensure_window:
            _reset_m4_state(app, "gradual_short", 0, log=f"Trend prep: DIF/DEA > 0 for {ensure_window} → Gradual Short")
            return
        if state["obs_neg"] >= ensure_window:
            _reset_m4_state(app, "gradual_long", 0, log=f"Trend prep: DIF/DEA < 0 for {ensure_window} → Gradual Long")
            return
        app.m4_state = state
        return

    # --- Gradual Long: wait for DIF > DEA while DIF still below zero ---
    if mode == "gradual_long":
        if cond_long_validation:
            _reset_m4_state(app, "long_validation", 1, log="Gradual Long → Long Validation (DIF > DEA & DIF < 0)")
        return

    # --- Long Validation: require ensure_window consecutive long validations ---
    if mode == "long_validation":
        if cond_long_validation:
            state["counter"] = state.get("counter", 1) + 1
            if state["counter"] >= ensure_window:
                _reset_m4_state(app, "long_trading", 0, log=f"Long Validation passed ({ensure_window}) → Enter Long")
                app.open_long(owner="M4")
                _reset_m4_state(app, "hold_long", 0, log="Opened LONG → Holding Long")
                return
        else:
            _reset_m4_state(app, "gradual_long", 0, log="Long Validation reset → Gradual Long")
        app.m4_state = state
        return

    # --- Holding Long: validate opposite (short) setup without leaving holding until confirmed ---
    if mode == "hold_long":
        if cond_short_validation:
            state["hold_counter"] = state.get("hold_counter", 0) + 1
            if state["hold_counter"] >= ensure_window:
                app.close_long(owner="M4")
                app.open_short(owner="M4")
                _reset_m4_state(app, "hold_short", 0, log="Flip: close LONG & open SHORT → Holding Short")
                return
        else:
            state["hold_counter"] = 0
        app.m4_state = state
        return

    # --- Gradual Short: wait for DIF < DEA while DIF above zero ---
    if mode == "gradual_short":
        if cond_short_validation:
            _reset_m4_state(app, "short_validation", 1, log="Gradual Short → Short Validation (DIF < DEA & DIF > 0)")
        return

    # --- Short Validation: require ensure_window consecutive short validations ---
    if mode == "short_validation":
        if cond_short_validation:
            state["counter"] = state.get("counter", 1) + 1
            if state["counter"] >= ensure_window:
                _reset_m4_state(app, "short_trading", 0, log=f"Short Validation passed ({ensure_window}) → Enter Short")
                app.open_short(owner="M4")
                _reset_m4_state(app, "hold_short", 0, log="Opened SHORT → Holding Short")
                return
        else:
            _reset_m4_state(app, "gradual_short", 0, log="Short Validation reset → Gradual Short")
        app.m4_state = state
        return

    # --- Holding Short: validate opposite (long) setup without leaving holding until confirmed ---
    if mode == "hold_short":
        if cond_long_validation:
            state["hold_counter"] = state.get("hold_counter", 0) + 1
            if state["hold_counter"] >= ensure_window:
                app.close_short(owner="M4")
                app.open_long(owner="M4")
                _reset_m4_state(app, "hold_long", 0, log="Flip: close SHORT & open LONG → Holding Long")
                return
        else:
            state["hold_counter"] = 0
        app.m4_state = state
        return

    # Any other/unexpected mode falls back to observation
    _reset_m4_state(app, "observation", 0, log="M4 reset → Observation")


def mechanism3_mean_revert_logic(app: Any) -> None:
    if app.last_price is None:
        return

    price = app.last_price
    app.me1_prices.append(price)
    cap3 = app.me1_window + 1
    if len(app.me1_prices) > cap3:
        app.me1_prices = app.me1_prices[-cap3:]

    open_m1 = [p for p in app.open_positions if p.get("owner") == "M1"]
    decision = algorithms_strat.mean_revert_decision(
        price,
        app.me1_prices,
        app.me1_window,
        app.me1_band,
        app.me1_stop,
        app.me1_prev_dist,
        open_m1,
    )
    if decision.get("log"):
        app._log_logic("M1", decision["log"])
    action = decision.get("action")
    # Check available margin before opening
    if action == "open_long":
        if getattr(app, "equity", 0.0) - (abs(getattr(app, "long_pos_size", 0) * getattr(app, "long_init_margin", 0.0) - getattr(app, "short_pos_size", 0) * getattr(app, "short_init_margin", 0.0))) < getattr(app, "long_init_margin", 0.0):
            return
        app.open_long(owner="M1")
    elif action == "open_short":
        if getattr(app, "equity", 0.0) - (abs(getattr(app, "long_pos_size", 0) * getattr(app, "long_init_margin", 0.0) - getattr(app, "short_pos_size", 0) * getattr(app, "short_init_margin", 0.0))) < getattr(app, "short_init_margin", 0.0):
            return
        app.open_short(owner="M1")
    elif action == "close_long":
        app.close_long(owner="M1")
    elif action == "close_short":
        app.close_short(owner="M1")
    app.me1_prev_dist = decision.get("prev_dist", app.me1_prev_dist)


def mechanism8_inverse_mean_revert_logic(app: Any) -> None:
    if app.last_price is None:
        return

    price = app.last_price
    app.me2_prices.append(price)
    cap8 = app.me2_window + 1
    if len(app.me2_prices) > cap8:
        app.me2_prices = app.me2_prices[-cap8:]

    open_m2 = [p for p in app.open_positions if p.get("owner") == "M2"]
    decision = algorithms_strat.inverse_mean_revert_decision(
        price,
        app.me2_prices,
        app.me2_window,
        app.me2_band,
        app.me2_stop,
        app.me2_prev_dist,
        open_m2,
    )
    if decision.get("log"):
        app._log_logic("M2", decision["log"])
    action = decision.get("action")
    if action == "open_long":
        if getattr(app, "equity", 0.0) - (abs(getattr(app, "long_pos_size", 0) * getattr(app, "long_init_margin", 0.0) - getattr(app, "short_pos_size", 0) * getattr(app, "short_init_margin", 0.0))) < getattr(app, "long_init_margin", 0.0):
            return
        app.open_long(owner="M2")
    elif action == "open_short":
        if getattr(app, "equity", 0.0) - (abs(getattr(app, "long_pos_size", 0) * getattr(app, "long_init_margin", 0.0) - getattr(app, "short_pos_size", 0) * getattr(app, "short_init_margin", 0.0))) < getattr(app, "short_init_margin", 0.0):
            return
        app.open_short(owner="M2")
    elif action == "close_long":
        app.close_long(owner="M2")
    elif action == "close_short":
        app.close_short(owner="M2")
    app.me2_prev_dist = decision.get("prev_dist", app.me2_prev_dist)


def _round_to_tick(value: float, tick_size: float) -> float:
    if tick_size <= 0:
        return value
    return round(value / tick_size) * tick_size


def mechanism_macd_atr_logic(app: Any) -> None:
    """MACD+ATR trend mechanism with ATR-based sizing and stops."""
    if app.last_price is None:
        return
    if not app.use_me_macd_atr.get():
        return
    # Use live series for logic
    times, prices = app._active_series()
    if len(prices) < 30:
        return
    params = app.macd_atr_params
    state = app.macd_atr_state
    tick_size = params["tick_size"]
    point_value = params["point_value"]
    # Build MACD + ATR
    macd_hist, dif, dea = algorithms.macd_series_for("3m", times, prices)
    if len(macd_hist) < 2:
        return
    hist_now = macd_hist[-1]
    hist_prev = macd_hist[-2]
    dif_now = dif[-1] if dif else None
    # ATR via true range with SMA window
    highs = getattr(app, "chart_highs_live", [])
    lows = getattr(app, "chart_lows_live", [])
    closes = getattr(app, "chart_closes_live", prices)
    if len(highs) != len(prices) or len(lows) != len(prices):
        return
    trs = algorithms.true_range_series(highs, lows, closes)
    atr_window = params.get("atr_window", 20)
    if len(trs) < atr_window:
        return
    atrs = []
    for i in range(len(trs)):
        if i + 1 < atr_window:
            atrs.append(math.nan)
        else:
            window = trs[i - atr_window + 1 : i + 1]
            atrs.append(sum(window) / atr_window)
    atr_now = atrs[-1]
    if math.isnan(atr_now):
        return
    valid_atrs = [v for v in atrs if not math.isnan(v)]
    if not valid_atrs:
        return
    sorted_atr = sorted(valid_atrs)
    mid = len(sorted_atr) // 2
    if len(sorted_atr) % 2 == 0:
        atr_median = 0.5 * (sorted_atr[mid - 1] + sorted_atr[mid])
    else:
        atr_median = sorted_atr[mid]
    atr_min = params["atr_min_factor"] * atr_median
    atr_max = params["atr_max_factor"] * atr_median
    vol_ok = atr_now >= atr_min and atr_now <= atr_max

    price_now = prices[-1]
    t_index = len(prices) - 1

    # Daily loss guard (simplified by date string)
    t_dt = times[-1]
    date_str = t_dt.date() if hasattr(t_dt, "date") else None
    if state["current_day"] != date_str:
        state["current_day"] = date_str
        state["equity_day_start"] = state["equity"]
        state["daily_pnl"] = 0.0
        state["daily_loss_limit"] = params["daily_loss_frac"] * state["equity_day_start"]
        state["no_new_trades"] = False

    # Update equity with bar P&L from prior position
    if len(prices) >= 2:
        bar_pnl = state["position"] * (prices[-1] - prices[-2]) * point_value
        state["equity"] += bar_pnl
        state["daily_pnl"] += bar_pnl
        if state["daily_pnl"] <= -state["daily_loss_limit"]:
            state["no_new_trades"] = True

    # Update status label with current pos
    if hasattr(app, "macd_atr_pos_var"):
        try:
            app.macd_atr_pos_var.set(f"Pos: {state['position']}")
        except Exception:
            pass

    # Exit logic
    if state["position"] > 0:
        exit_cond = False
        reason = ""
        if price_now <= (state["stop_price"] or -1e9):
            exit_cond = True
            reason = "long stop"
        if price_now >= (state["tp_price"] or 1e9):
            exit_cond = True
            reason = reason or "long tp"
        if hist_prev >= 0 and hist_now < 0:
            exit_cond = True
            reason = reason or "macd cross"
        if state["entry_index"] is not None and (t_index - state["entry_index"]) >= params["max_bars_in_trade"]:
            exit_cond = True
            reason = reason or "time stop"
        if exit_cond:
            app.close_long(owner="MACD_ATR")
            state.update({"position": 0, "entry_price": None, "entry_atr": None, "entry_index": None, "stop_price": None, "tp_price": None})
            if hasattr(app, "macd_atr_status_var"):
                app.macd_atr_status_var.set(f"Exit long ({reason}) @ {price_now:.2f}")
            return
        else:
            return
    elif state["position"] < 0:
        exit_cond = False
        reason = ""
        if price_now >= (state["stop_price"] or 1e9):
            exit_cond = True
            reason = "short stop"
        if price_now <= (state["tp_price"] or -1e9):
            exit_cond = True
            reason = reason or "short tp"
        if hist_prev <= 0 and hist_now > 0:
            exit_cond = True
            reason = reason or "macd cross"
        if state["entry_index"] is not None and (t_index - state["entry_index"]) >= params["max_bars_in_trade"]:
            exit_cond = True
            reason = reason or "time stop"
        if exit_cond:
            app.close_short(owner="MACD_ATR")
            state.update({"position": 0, "entry_price": None, "entry_atr": None, "entry_index": None, "stop_price": None, "tp_price": None})
            if hasattr(app, "macd_atr_status_var"):
                app.macd_atr_status_var.set(f"Exit short ({reason}) @ {price_now:.2f}")
            return
        else:
            return

    # If flat, consider entries
    if state["no_new_trades"]:
        return
    if not vol_ok:
        return
    # Require MACD values
    if dif_now is None or math.isnan(dif_now):
        return
    if hist_prev is None or hist_now is None:
        return

    # Compute size (simplified to 1 contract if risk allows)
    stop_distance = params["k_SL"] * atr_now
    loss_per_contract = stop_distance * point_value
    # Risk sizing uses current equity (app-level override if present)
    available_equity = state["equity"]
    try:
        if getattr(app, "equity", None) is not None:
            available_equity = min(available_equity, float(app.equity))
    except Exception:
        pass
    risk_budget = params["risk_per_trade"] * available_equity
    size = 1 if (loss_per_contract > 0 and risk_budget >= loss_per_contract) else 0
    if size <= 0:
        return

    entered = False
    if hist_prev <= 0 <= hist_now and dif_now > 0:
        stop_price = _round_to_tick(price_now - stop_distance, tick_size)
        tp_price = _round_to_tick(price_now + params["k_TP"] * atr_now, tick_size)
        state.update({
            "position": size,
            "entry_price": price_now,
            "entry_atr": atr_now,
            "entry_index": t_index,
            "stop_price": stop_price,
            "tp_price": tp_price,
        })
        app.open_long(owner="MACD_ATR")
        if hasattr(app, "macd_atr_status_var"):
            app.macd_atr_status_var.set(f"Enter long @ {price_now:.2f}")
        entered = True
    elif hist_prev >= 0 >= hist_now and dif_now < 0:
        stop_price = _round_to_tick(price_now + stop_distance, tick_size)
        tp_price = _round_to_tick(price_now - params["k_TP"] * atr_now, tick_size)
        state.update({
            "position": -size,
            "entry_price": price_now,
            "entry_atr": atr_now,
            "entry_index": t_index,
            "stop_price": stop_price,
            "tp_price": tp_price,
        })
        app.open_short(owner="MACD_ATR")
        if hasattr(app, "macd_atr_status_var"):
            app.macd_atr_status_var.set(f"Enter short @ {price_now:.2f}")
        entered = True
    if entered:
        if hasattr(app, "macd_atr_pos_var"):
            app.macd_atr_pos_var.set(f"Pos: {state['position']}")
        return
