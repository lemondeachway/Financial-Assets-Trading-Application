"""
Controller helpers for feed/backtest orchestration.
"""
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
import random

import plotting
from core import algorithms
from core.sessions import SESSION_NAMES, session_bucket
import app.ui_helpers as ui_helpers
from core.backtest import parse_ticks_from_csv
from app.trading_time import is_trading_time  # simple function import
from ui import charts


def start_feed(app) -> None:
    if getattr(app.sim_mode_var, "get", lambda: False)():
        start_sim_feed(app)
        return
    if not app.running:
        app.running = True
    app._nr_fetch_inflight = False
    app._reset_live_state()
    app._close_csv()
    app._open_csv()
    app.status_label.config(text="Status: running (real tick, time-filtered)")
    _schedule_next_tick(app)


def stop_feed(app) -> None:
    app.running = False
    app._sim_stop = True
    app._nr_fetch_inflight = False
    app._close_csv()
    app.status_label.config(text="Status: stopped")


def start_feed_cl(app) -> None:
    if not app.running_cl:
        app.running_cl = True
    app._cl_fetch_inflight = False
    _reset_cl_state(app)
    app._close_csv_cl()
    app._open_csv_cl()
    app.status_label.config(text="Status: running CL feed")
    _schedule_next_tick_cl(app)


def stop_feed_cl(app) -> None:
    app.running_cl = False
    app._cl_fetch_inflight = False
    app._close_csv_cl()
    app.status_label.config(text="Status: CL stopped")


def _schedule_next_tick(app) -> None:
    if app.running:
        delay_ms = int(app.interval * 1000)
        app.root.after(delay_ms, app.fetch_and_update)


def _schedule_next_tick_cl(app) -> None:
    if app.running_cl:
        delay_ms = int(app.interval_cl * 1000)
        app.root.after(delay_ms, app.fetch_and_update_cl)


def fetch_and_update(app) -> None:
    if not app.running or app._nr_fetch_inflight:
        return
    now_dt = datetime.now()
    if app.enforce_trading_window and not is_trading_time(now_dt):
        _schedule_next_tick(app)
        return
    app._nr_fetch_inflight = True
    threading.Thread(target=_fetch_tick_async, args=(app, now_dt), daemon=True).start()


def fetch_and_update_cl(app) -> None:
    if not app.running_cl or app._cl_fetch_inflight:
        return
    now_dt = datetime.now()
    if app.enforce_trading_window_cl and not is_trading_time(now_dt):
        _schedule_next_tick_cl(app)
        return
    app._cl_fetch_inflight = True
    threading.Thread(target=_fetch_tick_async_cl, args=(app, now_dt), daemon=True).start()


def _fetch_tick_async(app, now_dt: datetime) -> None:
    tick = None
    err: Optional[Exception] = None
    try:
        tick = app._fetch_tick()
    except Exception as e:
        err = e
    try:
        app.root.after(0, lambda: _finish_tick(app, now_dt, tick, err))
    except Exception:
        pass


def _fetch_tick_async_cl(app, now_dt: datetime) -> None:
    tick = None
    err: Optional[Exception] = None
    try:
        tick = app._fetch_tick_for(app.symbol_cl, app.data_url_template_cl)
    except Exception as e:
        err = e
    try:
        app.root.after(0, lambda: _finish_tick_cl(app, now_dt, tick, err))
    except Exception:
        pass


def _finish_tick(app, now_dt: datetime, tick: Optional[Dict[str, Any]], err: Optional[Exception]) -> None:
    app._nr_fetch_inflight = False
    if not app.running:
        return
    # If running in sim mode, bypass trading window enforcement (no-op here)
    if err is not None:
        app._set_status_text(f"Status: ERROR fetching tick: {err}")
        if not getattr(app.sim_mode_var, "get", lambda: False)():
            _schedule_next_tick(app)
        return
    if tick is None or tick.get("last") is None:
        app._set_status_text("Status: got None last price – skipping tick")
        if not getattr(app.sim_mode_var, "get", lambda: False)():
            _schedule_next_tick(app)
        return

    now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
    app.last_price = float(tick["last"])
    app.last_time_str = now_str

    display_time = ui_helpers.logic_time_display(now_str)
    app.tree.insert("", tk.END, values=(display_time, app.last_price))
    children = app.tree.get_children()
    if len(children) > app.max_tick_rows:
        app.tree.delete(*children[: len(children) - app.max_tick_rows])
    app.tree.yview_moveto(1.0)

    app._write_csv_tick(now_str, tick)
    if hasattr(app, "raw_fields_label"):
        fields = tick.get("fields") or []
        preview = ", ".join(fields[:10])
        app.raw_fields_label.config(text=f"Raw fields: {preview}")

    high_val = tick.get("high") if isinstance(tick, dict) else None
    low_val = tick.get("low") if isinstance(tick, dict) else None
    charts.update_chart_live(app, now_dt, app.last_price, high=high_val, low=low_val)
    try:
        app._refresh_init_margins()
    except Exception:
        pass

    if app.use_me3.get():
        app._mechanism3_mean_revert_logic()
    if app.use_me8.get():
        app._mechanism8_inverse_mean_revert_logic()
    if getattr(app, "use_me4", None) and app.use_me4.get():
        app._mechanism4_macd_mode_logic()
    if getattr(app, "use_me_macd_atr", None) and app.use_me_macd_atr.get():
        app._mechanism_macd_atr_logic()

    if not getattr(app.sim_mode_var, "get", lambda: False)():
        _schedule_next_tick(app)


def _finish_tick_cl(app, now_dt: datetime, tick: Optional[Dict[str, Any]], err: Optional[Exception]) -> None:
    app._cl_fetch_inflight = False
    if not app.running_cl:
        return
    if err is not None:
        app._set_status_text(f"Status: ERROR fetching CL tick: {err}")
        _schedule_next_tick_cl(app)
        return
    if tick is None or tick.get("last") is None:
        app._set_status_text("Status: CL got None last price – skipping tick")
        _schedule_next_tick_cl(app)
        return

    now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
    app.last_price_cl = float(tick["last"])
    app.last_time_str_cl = now_str

    display_time = ui_helpers.logic_time_display(now_str)
    app.tree_cl.insert("", tk.END, values=(display_time, app.last_price_cl))
    children = app.tree_cl.get_children()
    if len(children) > app.max_tick_rows:
        app.tree_cl.delete(*children[: len(children) - app.max_tick_rows])
    app.tree_cl.yview_moveto(1.0)

    app._write_csv_tick_cl(now_str, tick)
    if hasattr(app, "raw_fields_label_cl"):
        fields = tick.get("fields") or []
        preview = ", ".join(fields[:10])
        app.raw_fields_label_cl.config(text=f"Raw fields: {preview}")

    high_val = tick.get("high") if isinstance(tick, dict) else None
    low_val = tick.get("low") if isinstance(tick, dict) else None
    charts.update_chart_cl(app, now_dt, app.last_price_cl, high=high_val, low=low_val)

    _schedule_next_tick_cl(app)


def start_stream_backtest(app) -> None:
    app.running = False
    stop_stream_backtest(app)
    app.in_backtest = True
    app.in_streaming = True
    app.suppress_backtest_ui = True

    path = app._with_topmost_suspended(
        lambda: filedialog.askopenfilename(
            title="Select CSV for streaming backtest",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
    )
    if not path:
        return

    try:
        ticks = parse_ticks_from_csv(path)
    except Exception as e:
        messagebox.showerror("Backtest error", f"Failed to load CSV:\n{e}")
        return
    if not ticks:
        messagebox.showerror("Backtest error", "No valid time/price rows in CSV")
        return

    # Precompute fixed ranges from full CSV
    _apply_fixed_ranges_stream(app, ticks)

    _prep_stream_state(app)

    app._stream_ticks = ticks
    app._stream_index = 0
    app._stream_stop = False
    app._stream_path = path
    delay_str = app.stream_delay_var.get().strip()
    try:
        app._stream_delay = max(0.01, float(delay_str))
    except ValueError:
        app._stream_delay = max(0.01, app.interval)
    try:
        speed = float(app.stream_speed_var.get().strip())
        if speed <= 0:
            speed = 1.0
        speed = min(speed, 200.0)
    except ValueError:
        speed = 1.0
    app._stream_speed = speed

    app.stream_progress.config(from_=0, to=len(ticks))
    app.stream_progress.set(0)
    app.stream_progress_label.config(text=f"0/{len(ticks)}")
    app.status_label.config(text=f"Status: streaming backtest ({len(ticks)} ticks)")

    app.root.after(0, app._stream_next_tick)


def _prep_stream_state(app) -> None:
    app.open_positions.clear()
    app.settlement = 0.0
    app.trade_count = 0
    app._update_position_state_label()
    app._update_settlement_label()
    if hasattr(app, "_reset_macd_atr_state"):
        app._reset_macd_atr_state()

    for tree in (app.tree, app.pos_tree, app.logic_tree):
        try:
            for item in tree.get_children():
                tree.delete(item)
        except Exception:
            pass

    app.chart_times_stream = []
    app.chart_prices_stream = []
    app.chart_highs_stream = []
    app.chart_lows_stream = []
    app.chart_closes_stream = []
    app.stream_open_long_x = []
    app.stream_open_long_y = []
    app.stream_close_long_x = []
    app.stream_close_long_y = []
    app.stream_open_short_x = []
    app.stream_open_short_y = []
    app.stream_close_short_x = []
    app.stream_close_short_y = []
    app.stream_position_spans = []
    app._stream_tick_counter = 0
    app._prev_close_stream = None
    try:
        app._macd_cache.clear()
        app._cached_macd.clear()
    except Exception:
        pass
    app._update_stream_nb_chart("", [], [], {"spans": []})

    app.me1_prices.clear()
    app.me1_prev_dist = None
    app.me2_prices.clear()
    app.me2_prev_dist = None
    app.m4_state = {
        "mode": "observation",
        "counter": 0,
        "hold_counter": 0,
        "obs_pos": 0,
        "obs_neg": 0,
    }
    for key in app.sim_states:
        app.sim_states[key]["positions"].clear()
        app.sim_states[key]["settlement"] = 0.0
    app.stream_price_range_fixed = getattr(app, "stream_price_range_fixed", None)
    app.stream_macd_range_fixed = getattr(app, "stream_macd_range_fixed", None)


def stream_next_tick(app) -> None:
    if getattr(app, "_stream_stop", True):
        app.in_backtest = False
        app.in_streaming = False
        charts.redraw_stream_chart(app)
        return
    if app._stream_index >= len(app._stream_ticks):
        marker_snapshot = {
            "open_long_x": list(app.stream_open_long_x),
            "open_long_y": list(app.stream_open_long_y),
            "close_long_x": list(app.stream_close_long_x),
            "close_long_y": list(app.stream_close_long_y),
            "open_short_x": list(app.stream_open_short_x),
            "open_short_y": list(app.stream_open_short_y),
            "close_short_x": list(app.stream_close_short_x),
            "close_short_y": list(app.stream_close_short_y),
            "spans": list(app.stream_position_spans),
        }
        app._update_stream_nb_chart(
            app._stream_path or "stream",
            list(app.chart_times_stream),
            list(app.chart_prices_stream),
            marker_snapshot,
        )
        app.status_label.config(
            text=f"Status: streaming backtest done. Ticks: {len(app._stream_ticks)}  Settlement (net): {app.settlement:.2f}"
        )
        if app.last_price is not None and app.last_time_str is not None:
            app._force_close_all_positions(app.last_price, app.last_time_str)
        _reset_stream_state(app, clear_progress=False)
        app.in_backtest = False
        app.in_streaming = False
        charts.redraw_stream_chart(app)
        return

    tick_tuple = app._stream_ticks[app._stream_index]
    dt_val = tick_tuple[0]
    p_val = tick_tuple[1]
    high_val = tick_tuple[2] if len(tick_tuple) > 2 else None
    low_val = tick_tuple[3] if len(tick_tuple) > 3 else None
    app.last_price = p_val
    app.last_time_str = dt_val.strftime("%Y-%m-%d %H:%M:%S")

    app.tree.insert("", tk.END, values=(ui_helpers.logic_time_display(app.last_time_str), app.last_price))
    children = app.tree.get_children()
    if len(children) > app.max_tick_rows:
        app.tree.delete(*children[: len(children) - app.max_tick_rows])

    # Switch fixed ranges when crossing session buckets
    session_name = session_bucket(dt_val)
    if getattr(app, "_stream_current_session", None) != session_name:
        app._stream_current_session = session_name
        app.stream_price_range_fixed = app.stream_price_ranges_by_session.get(
            session_name, app.stream_price_range_full
        )
        app.stream_macd_range_fixed = app.stream_macd_ranges_by_session.get(
            session_name, app.stream_macd_range_full
        )

    app._stream_tick_counter += 1
    draw_now = True
    charts.update_chart_stream(app, dt_val, p_val, high=high_val, low=low_val, redraw=draw_now, clear_macd_cache=False)
    if draw_now:
        marker_snapshot = {
            "open_long_x": list(app.stream_open_long_x),
            "open_long_y": list(app.stream_open_long_y),
            "close_long_x": list(app.stream_close_long_x),
            "close_long_y": list(app.stream_close_long_y),
            "open_short_x": list(app.stream_open_short_x),
            "open_short_y": list(app.stream_open_short_y),
            "close_short_x": list(app.stream_close_short_x),
            "close_short_y": list(app.stream_close_short_y),
            "spans": list(app.stream_position_spans),
        }
        app._update_stream_nb_chart(
            app._stream_path or "stream",
            list(app.chart_times_stream),
            list(app.chart_prices_stream),
            marker_snapshot,
        )
    try:
        app._refresh_init_margins()
    except Exception:
        pass

    if app.use_me3.get():
        app._mechanism3_mean_revert_logic()
    if app.use_me8.get():
        app._mechanism8_inverse_mean_revert_logic()
    if getattr(app, "use_me4", None) and app.use_me4.get():
        app._mechanism4_macd_mode_logic()

    app.stream_progress["value"] = app._stream_index + 1
    app.stream_progress_label.config(text=f"{app._stream_index + 1}/{len(app._stream_ticks)}")

    app._stream_index += 1
    delay = app._stream_delay / max(0.01, app._stream_speed)
    app.root.after(int(delay * 1000), app._stream_next_tick)


def _calc_fixed_ranges(prices: List[float], padding_ratio: float = 0.02) -> Tuple[float, float]:
    if not prices:
        return None
    mn = min(prices)
    mx = max(prices)
    span = mx - mn
    pad = span * padding_ratio if span > 0 else 0.1
    return (mn - pad, mx + pad)


def _apply_fixed_ranges_stream(app, ticks: List[Tuple[datetime, float]]) -> None:
    prices = [tick[1] for tick in ticks]
    times_all = [tick[0] for tick in ticks]
    all_price_range = _calc_fixed_ranges(prices)
    macd_hist, dif, dea = algorithms.macd_series_for((app.macd_mode_var.get() or "5m").lower(), times_all, prices)
    macd_vals = list(macd_hist or []) + list(dif or []) + list(dea or [])
    all_macd_range = _calc_fixed_ranges(macd_vals)

    # Bucket ranges per session
    price_by_session = {name: [] for name in SESSION_NAMES}
    macd_by_session = {name: [] for name in SESSION_NAMES}
    for idx, tick in enumerate(ticks):
        dt_val = tick[0]
        bucket = session_bucket(dt_val)
        price_by_session[bucket].append(tick[1])
        if macd_hist and idx < len(macd_hist) and macd_hist[idx] is not None:
            macd_by_session[bucket].append(macd_hist[idx])
        if dif and idx < len(dif) and dif[idx] is not None:
            macd_by_session[bucket].append(dif[idx])
        if dea and idx < len(dea) and dea[idx] is not None:
            macd_by_session[bucket].append(dea[idx])

    app.stream_price_ranges_by_session = {
        k: _calc_fixed_ranges(v) for k, v in price_by_session.items() if v
    }
    app.stream_macd_ranges_by_session = {
        k: _calc_fixed_ranges(v) for k, v in macd_by_session.items() if v
    }
    app.stream_price_range_full = all_price_range
    app.stream_macd_range_full = all_macd_range

    first_bucket = session_bucket(times_all[0]) if times_all else SESSION_NAMES[0]
    app._stream_current_session = first_bucket
    app.stream_price_range_fixed = app.stream_price_ranges_by_session.get(first_bucket, all_price_range)
    app.stream_macd_range_fixed = app.stream_macd_ranges_by_session.get(first_bucket, all_macd_range)

    app._stream_macd_full = (macd_hist, dif, dea)
    app._stream_macd_mode = (app.macd_mode_var.get() or "5m").lower()
    # persist to the stream notebook redraw
    try:
        app._update_stream_nb_chart("", [], [], {"spans": []})
    except Exception:
        pass


def stop_stream_backtest(app) -> None:
    app._stream_stop = True
    _reset_stream_state(app, clear_progress=True)
    app.in_backtest = False
    app.in_streaming = False


def seek_stream_progress(app, value: str) -> None:
    if not hasattr(app, "_stream_ticks"):
        return
    try:
        idx = int(float(value))
    except ValueError:
        return
    idx = max(0, min(idx, len(app._stream_ticks)))
    app._stream_index = idx
    if idx < len(app._stream_ticks):
        tick_tuple = app._stream_ticks[idx]
        dt_val = tick_tuple[0]
        p_val = tick_tuple[1]
        app.last_price = p_val
        app.last_time_str = dt_val.strftime("%Y-%m-%d %H:%M:%S")
    app.stream_progress_label.config(text=f"{idx}/{len(app._stream_ticks)}")


def _reset_stream_state(app, clear_progress: bool = True) -> None:
    app.open_positions.clear()
    app.settlement = 0.0
    app.trade_count = 0
    app._update_position_state_label()
    app._update_settlement_label()

    for tree in (app.tree, app.pos_tree, app.logic_tree):
        try:
            for item in tree.get_children():
                tree.delete(item)
        except Exception:
            pass

    app.chart_times_stream = []
    app.chart_prices_stream = []
    app.stream_open_long_x = []
    app.stream_open_long_y = []
    app.stream_close_long_x = []
    app.stream_close_long_y = []
    app.stream_open_short_x = []
    app.stream_open_short_y = []
    app.stream_close_short_x = []
    app.stream_close_short_y = []
    app.stream_position_spans = []
    app._stream_tick_counter = 0

    app.me1_prices.clear()
    app.me1_prev_dist = None
    app.me2_prices.clear()
    app.me2_prev_dist = None
    app.m4_state = {
        "mode": "observation",
        "counter": 0,
        "hold_counter": 0,
        "obs_pos": 0,
        "obs_neg": 0,
    }
    for key in app.sim_states:
        app.sim_states[key]["positions"].clear()
        app.sim_states[key]["settlement"] = 0.0

    app._update_stream_nb_chart("", [], [], {"spans": []})
    if clear_progress and hasattr(app, "stream_progress"):
        app.stream_progress.set(0)
        app.stream_progress_label.config(text="0/0")
    app.stream_price_range_fixed = None
    app.stream_macd_range_fixed = None
    app._stream_macd_full = None
    app._stream_macd_mode = None
    app.stream_price_ranges_by_session = {}
    app.stream_macd_ranges_by_session = {}
    app.stream_price_range_full = None
    app.stream_macd_range_full = None
    app._stream_current_session = None
    app._atr_cache.clear()
    if hasattr(app, "_osc_cache"):
        app._osc_cache.clear()
    if hasattr(app, "_osc_cache"):
        app._osc_cache.clear()


def reset_quick_backtest_state(app) -> None:
    app.open_positions.clear()
    app.settlement = 0.0
    app.trade_count = 0
    app.total_fees = 0.0
    if hasattr(app, "raw_fields_label"):
        app.raw_fields_label.config(text="Raw fields: --")
    app._update_position_state_label()
    app._update_settlement_label()

    for tree in (app.tree, app.pos_tree, app.logic_tree):
        try:
            for item in tree.get_children():
                tree.delete(item)
        except Exception:
            pass

    app.chart_times_live = []
    app.chart_prices_live = []
    app.chart_highs_live = []
    app.chart_lows_live = []
    app.chart_closes_live = []
    app.live_open_long_x = []
    app.live_open_long_y = []
    app.live_close_long_x = []
    app.live_close_long_y = []
    app.live_open_short_x = []
    app.live_open_short_y = []
    app.live_close_short_x = []
    app.live_close_short_y = []
    app.pl_lines = []
    app.live_position_spans = []
    app._prev_close_live = None
    app._atr_cache.clear()
    charts.redraw_chart(app)

    # Clear backtest series so each mechanism/file run starts fresh
    _reset_backtest_chart_state(app)

    app.me1_prices.clear()
    app.me1_prev_dist = None
    app.me2_prices.clear()
    app.me2_prev_dist = None
    app.m4_state = {
        "mode": "observation",
        "counter": 0,
        "hold_counter": 0,
        "obs_pos": 0,
        "obs_neg": 0,
    }
    _reset_cl_state(app)
    if hasattr(app, "_reset_macd_atr_state"):
        app._reset_macd_atr_state()
    if hasattr(app, "_macd_prev_relation"):
        app._macd_prev_relation = {"live": None, "bt": None, "stream": None}
    if hasattr(app, "_macd_last_flip_index"):
        app._macd_last_flip_index = {"live": -9999, "bt": -9999, "stream": -9999}


def _reset_backtest_chart_state(app) -> None:
    app.chart_times_bt = []
    app.chart_prices_bt = []
    app.chart_highs_bt = []
    app.chart_lows_bt = []
    app.chart_closes_bt = []
    app.bt_open_long_x = []
    app.bt_open_long_y = []
    app.bt_close_long_x = []
    app.bt_close_long_y = []
    app.bt_open_short_x = []
    app.bt_open_short_y = []
    app.bt_close_short_x = []
    app.bt_close_short_y = []
    app.bt_position_spans = []
    app.chart_highs_bt = []
    app.chart_lows_bt = []
    app.chart_closes_bt = []
    app._prev_close_bt = None


def _reset_cl_state(app) -> None:
    if hasattr(app, "tree_cl") and app.tree_cl is not None:
        for item in app.tree_cl.get_children():
            app.tree_cl.delete(item)
    if hasattr(app, "raw_fields_label_cl"):
        app.raw_fields_label_cl.config(text="Raw fields: --")
    app.last_price_cl = None
    app.last_time_str_cl = None
    app.chart_highs_cl = []
    app.chart_lows_cl = []
    app.chart_closes_cl = []
    app._prev_close_cl = None


def reset_live_state(app) -> None:
    app.in_backtest = False
    app.suppress_backtest_ui = False
    reset_quick_backtest_state(app)
    app.price_range_live_fixed = None


# -------- Simulation feed helpers --------


def _sim_speed(app) -> float:
    try:
        return max(0.01, float(app.sim_speed_var.get()))
    except Exception:
        return 1.0


def _sim_params_from_ui(app) -> Dict[str, float]:
    # base params from UI
    def _float(var, default):
        try:
            return float(var.get())
        except Exception:
            return default

    params = {
        "base": _float(app.sim_base_price_var, getattr(app, "last_price", 100.0) or 100.0),
        "atr": _float(app.sim_atr_var, 10.0),
        "jump_prob": _float(app.sim_jump_prob_var, 0.02),
        "jump_scale": _float(app.sim_jump_scale_var, 5.0),
        "speed": _sim_speed(app),
    }
    if getattr(app.sim_random_var, "get", lambda: False)():
        import random

        lp = getattr(app, "last_price", None)
        if lp is None or lp <= 0:
            lp = params["base"]
        params["base"] = random.uniform(0.9, 1.1) * lp
        params["atr"] = max(0.1, random.uniform(0.5, 1.5) * params["atr"])
        params["jump_prob"] = max(0.0, min(0.1, random.uniform(0.0, 0.05)))
        params["jump_scale"] = max(0.0, random.uniform(0.2, 2.0) * params["jump_scale"])
        params["speed"] = max(0.2, random.uniform(0.5, 2.0) * params["speed"])
    return params


def _generate_synthetic_ticks(
    app,
    count: int = 2000,
    start_price: float = 100.0,
    interval: float = 1.0,
    base: float | None = None,
    atr_val: float | None = None,
    jump_prob_val: float | None = None,
    jump_scale_val: float | None = None,
) -> List[Tuple[datetime, float, float, float, float]]:
    ticks: List[Tuple[datetime, float, float, float, float]] = []
    now = datetime.now()
    if base is None:
        try:
            base = float(app.sim_base_price_var.get())
        except Exception:
            base = start_price
    price = base
    if atr_val is None:
        try:
            atr = max(0.01, float(app.sim_atr_var.get()))
        except Exception:
            atr = 10.0
    else:
        atr = max(0.01, atr_val)
    if jump_prob_val is None:
        try:
            jump_prob = max(0.0, min(1.0, float(app.sim_jump_prob_var.get())))
        except Exception:
            jump_prob = 0.02
    else:
        jump_prob = max(0.0, min(1.0, jump_prob_val))
    if jump_scale_val is None:
        try:
            jump_scale = max(0.0, float(app.sim_jump_scale_var.get()))
        except Exception:
            jump_scale = 5.0
    else:
        jump_scale = max(0.0, jump_scale_val)
    tick_size = getattr(app, "tick_size", 0.0) or 0.0
    clamp_span = atr * 6.0  # keep synthetic prices within a band to avoid runaway ranges
    prev_close = price
    for i in range(count):
        dt_val = now + timedelta(seconds=interval * i)
        move = random.uniform(-atr * 0.5, atr * 0.5)
        if random.random() < jump_prob:
            move += random.choice([-1, 1]) * random.uniform(0, jump_scale)
        price = max(0.1, price + move)
        price = min(max(price, base - clamp_span), base + clamp_span)
        if tick_size > 0:
            price = round(price / tick_size) * tick_size
        high = max(price, prev_close) + abs(move) * 0.3
        low = min(price, prev_close) - abs(move) * 0.3
        ticks.append((dt_val, price, high, low, prev_close))
        prev_close = price
    return ticks


def start_sim_feed(app) -> None:
    app.running = True
    app._sim_stop = False
    app._nr_fetch_inflight = False
    app._reset_live_state()
    app._close_csv()
    ticks: List[Tuple[datetime, float, float, float, float]] = []
    path_val = ""
    if hasattr(app, "sim_csv_path_var"):
        path_val = app.sim_csv_path_var.get().strip()
    params = _sim_params_from_ui(app)
    if path_val:
        try:
            ticks = parse_ticks_from_csv(path_val)
        except Exception as e:
            messagebox.showerror("Sim feed", f"Failed to load sim CSV:\n{e}")
            ticks = []
    if not ticks:
        ticks = _generate_synthetic_ticks(
            app,
            start_price=app.last_price or params["base"],
            interval=float(app.interval),
            base=params["base"],
            atr_val=params["atr"],
            jump_prob_val=params["jump_prob"],
            jump_scale_val=params["jump_scale"],
        )
    app._sim_ticks = ticks
    app._sim_index = 0
    app.status_label.config(text=f"Status: SIM running ({'CSV' if path_val else 'synthetic'})")
    delay_ms = max(10, int(1000 * max(0.01, float(getattr(app, 'interval', 1.0))) / max(0.01, params["speed"])))
    app.root.after(0, lambda: _sim_next_tick(app, delay_ms))


def _sim_next_tick(app, delay_ms: int) -> None:
    if app._sim_stop or not app.running:
        return
    if app._sim_index >= len(app._sim_ticks):
        app.status_label.config(text="Status: SIM done")
        app.running = False
        return
    tick_tuple = app._sim_ticks[app._sim_index]
    dt_val, p_val, h_val, l_val, prev_close = tick_tuple
    tick = {
        "last": p_val,
        "high": h_val,
        "low": l_val,
        "open": prev_close,
        "prev_settle": prev_close,
        "fields": [],
        "payload": "",
    }
    _finish_tick(app, dt_val, tick, None)
    app._sim_index += 1
    app.root.after(delay_ms, lambda: _sim_next_tick(app, delay_ms))
