"""
Trading and position management helpers.
"""
from typing import Optional, Tuple


def _alt_settlement_enabled(app) -> bool:
    var = getattr(app, "use_alt_settlement_var", None)
    if var is not None:
        try:
            return bool(var.get())
        except Exception:
            return False
    return getattr(app, "alt_settlement_enabled", False)


def _alt_settlement_tick_factor(app) -> float:
    fallback = getattr(app, "alt_settlement_tick_factor", 2.0)
    var = getattr(app, "alt_settlement_tick_factor_var", None)
    if var is not None:
        try:
            fallback = float(var.get())
        except Exception:
            pass
    return max(0.0, fallback)


def _settlement_price_adjustment(app, base_price: Optional[float], side: str, action: str) -> Optional[float]:
    """
    Adjust prices when the alternate settlement mode is enabled.
    """
    if base_price is None or not _alt_settlement_enabled(app):
        return base_price
    tick = max(0.0, float(getattr(app, "tick_size", 0.0)))
    factor = _alt_settlement_tick_factor(app)
    delta = factor * tick
    if side == "long":
        if action == "open":
            return base_price + delta
        if action == "close":
            return base_price - delta
    else:
        if action == "open":
            return base_price - delta
        if action == "close":
            return base_price + delta
    return base_price


def find_position(app, side: str, owner: Optional[str] = None) -> Optional[int]:
    for i, p in enumerate(app.open_positions):
        if p["side"] != side:
            continue
        if owner is not None and p.get("owner") != owner:
            continue
        return i
    return None


def calc_trade_fee(app, price: Optional[float]) -> float:
    if app.trade_fee_mode == "percent" and price is not None:
        try:
            return max(0.0, float(price) * float(app.trade_fee_pct))
        except Exception:
            return max(0.0, app.trade_fee)
    return max(0.0, app.trade_fee)


def adjust_equity(app, delta: float) -> None:
    if app.in_backtest:
        return
    try:
        app.equity += delta
    except Exception:
        pass
    app._update_equity_label()


def _get_order_qty(app) -> int:
    """
    Resolve order quantity from app state/var.
    """
    try:
        return max(0, int(float(getattr(app, "order_qty", 1))))
    except Exception:
        pass
    try:
        var = getattr(app, "order_qty_var", None)
        if var is not None:
            return max(0, int(float(var.get())))
    except Exception:
        pass
    return 1

def _accumulate_fee(app, fee: float) -> None:
    try:
        app.total_fees = getattr(app, "total_fees", 0.0) + max(0.0, fee)
    except Exception:
        app.total_fees = max(0.0, fee)
    try:
        app._refresh_init_margins()
    except Exception:
        pass


def open_long(app, owner: str = "MANUAL") -> None:
    info = app._current_tick_info()
    if info is None:
        return
    t_str, price = info
    _, active_prices = app._active_series()
    open_index = len(active_prices) - 1 if active_prices else None
    open_date = None
    try:
        open_date = t_str.split(" ")[0]
    except Exception:
        pass
    qty = _get_order_qty(app)
    settlement_entry = _settlement_price_adjustment(app, price, "long", "open")
    if settlement_entry is None:
        settlement_entry = price
    pos = {
        "side": "long",
        "owner": owner,
        "open_time": t_str,
        "open_price": price,
        "open_index": open_index,
        "trail_max": price,
        "open_date": open_date,
        "qty": qty,
        "settlement_entry_price": settlement_entry,
    }
    app.long_pos_size = getattr(app, "long_pos_size", 0) + qty
    app.open_positions.append(pos)
    app._append_position_row(f"open long ({owner})", 1, t_str, price, None)
    app._update_position_state_label()
    fee = calc_trade_fee(app, price)
    app.settlement -= fee
    app.trade_count += 1
    _accumulate_fee(app, fee)
    app._update_settlement_label()
    if not app.in_backtest:
        adjust_equity(app, -fee)
    app._write_trade_command("OPEN_LONG", t_str, price)
    app._mark_trade("long", "open", price, open_index)


def open_short(app, owner: str = "MANUAL") -> None:
    info = app._current_tick_info()
    if info is None:
        return
    t_str, price = info
    _, active_prices = app._active_series()
    open_index = len(active_prices) - 1 if active_prices else None
    open_date = None
    try:
        open_date = t_str.split(" ")[0]
    except Exception:
        pass
    qty = _get_order_qty(app)
    settlement_entry = _settlement_price_adjustment(app, price, "short", "open")
    if settlement_entry is None:
        settlement_entry = price
    pos = {
        "side": "short",
        "owner": owner,
        "open_time": t_str,
        "open_price": price,
        "open_index": open_index,
        "trail_min": price,
        "open_date": open_date,
        "qty": qty,
        "settlement_entry_price": settlement_entry,
    }
    app.short_pos_size = getattr(app, "short_pos_size", 0) + qty
    app.open_positions.append(pos)
    app._append_position_row(f"open short ({owner})", 1, t_str, price, None)
    app._update_position_state_label()
    fee = calc_trade_fee(app, price)
    app.settlement -= fee
    app.trade_count += 1
    _accumulate_fee(app, fee)
    app._update_settlement_label()
    if not app.in_backtest:
        adjust_equity(app, -fee)
    app._write_trade_command("OPEN_SHORT", t_str, price)
    app._mark_trade("short", "open", price, open_index)


def _no_close_today_fee_enabled(app) -> bool:
    """
    Determine if fee should be waived for same-day closes.
    """
    # Prefer explicit attribute, else fall back to Tk variable if present.
    val = getattr(app, "no_close_today_fee", None)
    if val is None:
        try:
            var = getattr(app, "no_close_today_fee_var", None)
            if var is not None:
                return bool(var.get())
        except Exception:
            return True
    try:
        return bool(val)
    except Exception:
        return True


def close_long(app, owner: Optional[str] = None) -> None:
    info = app._current_tick_info()
    if info is None:
        return
    t_str, price = info
    idx = find_position(app, "long", owner)
    if idx is None:
        app.status_label.config(text="Status: no long position to close")
        return
    pos = app.open_positions.pop(idx)
    entry_price = pos["open_price"]
    open_index = pos.get("open_index")
    qty = pos.get("qty", 1)
    entry_settlement_price = pos.get("settlement_entry_price", entry_price)
    close_settlement_price = _settlement_price_adjustment(app, price, "long", "close") or price
    diff = float(close_settlement_price - entry_settlement_price) * app.leverage
    fee = calc_trade_fee(app, price)
    # waive fee if closing on same day and toggle is on
    if _no_close_today_fee_enabled(app):
        try:
            open_date = pos.get("open_date")
            close_date = t_str.split(" ")[0] if t_str else None
            if open_date and close_date and open_date == close_date:
                fee = 0.0
        except Exception:
            pass
    app.settlement += diff
    app.settlement -= fee
    app.trade_count += 1
    _accumulate_fee(app, fee)
    label_owner = pos.get("owner", "MANUAL")
    app._append_position_row(f"close long ({label_owner})", 1, t_str, price, diff)
    app.long_pos_size = max(0, getattr(app, "long_pos_size", 0) - qty)
    app._update_position_state_label()
    app._update_settlement_label()
    if not app.in_backtest:
        adjust_equity(app, diff - fee)
    app._write_trade_command("CLOSE_LONG", t_str, price)
    _, active_prices = app._active_series()
    close_index = len(active_prices) - 1 if active_prices else None
    app._mark_trade("long", "close", price, close_index)
    app._add_pl_line("long", entry_price, price, open_index, close_index)


def close_short(app, owner: Optional[str] = None) -> None:
    info = app._current_tick_info()
    if info is None:
        return
    t_str, price = info
    idx = find_position(app, "short", owner)
    if idx is None:
        app.status_label.config(text="Status: no short position to close")
        return
    pos = app.open_positions.pop(idx)
    entry_price = pos["open_price"]
    open_index = pos.get("open_index")
    qty = pos.get("qty", 1)
    entry_settlement_price = pos.get("settlement_entry_price", entry_price)
    close_settlement_price = _settlement_price_adjustment(app, price, "short", "close") or price
    diff = float(entry_settlement_price - close_settlement_price) * app.leverage
    fee = calc_trade_fee(app, price)
    if _no_close_today_fee_enabled(app):
        try:
            open_date = pos.get("open_date")
            close_date = t_str.split(" ")[0] if t_str else None
            if open_date and close_date and open_date == close_date:
                fee = 0.0
        except Exception:
            pass
    app.settlement += diff
    app.settlement -= fee
    app.trade_count += 1
    _accumulate_fee(app, fee)
    label_owner = pos.get("owner", "MANUAL")
    app._append_position_row(f"close short ({label_owner})", 1, t_str, price, diff)
    app.short_pos_size = max(0, getattr(app, "short_pos_size", 0) - qty)
    app._update_position_state_label()
    app._update_settlement_label()
    if not app.in_backtest:
        adjust_equity(app, diff - fee)
    app._write_trade_command("CLOSE_SHORT", t_str, price)
    _, active_prices = app._active_series()
    close_index = len(active_prices) - 1 if active_prices else None
    app._mark_trade("short", "close", price, close_index)
    app._add_pl_line("short", entry_price, price, open_index, close_index)


def force_close_all_positions(app, price: float, time_str: str) -> None:
    app.last_price = price
    app.last_time_str = time_str
    while app.open_positions:
        pos = app.open_positions[0]
        side = pos["side"]
        owner = pos.get("owner", "MANUAL")
        if side == "long":
            close_long(app, owner=owner)
        else:
            close_short(app, owner=owner)
