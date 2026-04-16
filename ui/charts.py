"""
Chart redraw/update helpers extracted from the app.
"""
from datetime import datetime
from typing import Any, List, Dict
from app import plotting


def redraw_chart(app) -> None:
    markers = {
        "open_long_x": app.live_open_long_x,
        "open_long_y": app.live_open_long_y,
        "close_long_x": app.live_close_long_x,
        "close_long_y": app.live_close_long_y,
        "open_short_x": app.live_open_short_x,
        "open_short_y": app.live_open_short_y,
        "close_short_x": app.live_close_short_x,
        "close_short_y": app.live_close_short_y,
    }
    macd_hist, dif, dea = app._macd_series_for(app.chart_times_live, app.chart_prices_live)
    price_limits = _update_range(app, "price_range_live", app.chart_prices_live)
    fixed = getattr(app, "price_range_live_fixed", None)
    if fixed:
        price_limits = fixed
    macd_limits = _update_range(app, "macd_range_live", list(macd_hist or []) + list(dif or []) + list(dea or []))
    plotting.draw_price_macd(
        app.ax,
        app.ax_macd,
        app.chart_times_live,
        app.chart_prices_live,
        spans=app.live_position_spans,
        markers=markers,
        title="Last Price",
        y_label="Price",
        max_ticks=10,
        macd_data=(macd_hist, dif, dea),
        fixed_ylim=price_limits,
        macd_fixed_ylim=macd_limits,
    )
    plotting.draw_macd_flips(app.ax_macd, getattr(app, "macd_flip_markers_live", None))
    app.canvas.draw_idle()
    redraw_backtest_chart(app)


def redraw_chart_cl(app) -> None:
    if not hasattr(app, "ax_cl") or app.ax_cl is None:
        return
    macd_hist, dif, dea = app._macd_series_for(app.chart_cl_times, app.chart_cl_prices)
    price_limits = _update_range(app, "price_range_cl", app.chart_cl_prices)
    macd_limits = _update_range(app, "macd_range_cl", list(macd_hist or []) + list(dif or []) + list(dea or []))
    plotting.draw_price_macd(
        app.ax_cl,
        app.ax_cl_macd,
        app.chart_cl_times,
        app.chart_cl_prices,
        spans=None,
        markers=None,
        title="CL Last Price",
        y_label="Price",
        max_ticks=10,
        macd_data=(macd_hist, dif, dea),
        fixed_ylim=price_limits,
        macd_fixed_ylim=macd_limits,
    )
    if hasattr(app, "canvas_cl") and app.canvas_cl:
        app.canvas_cl.draw_idle()


def redraw_backtest_chart(app) -> None:
    if app.ax_bt is None or app.canvas_bt is None:
        return
    plotting.draw_price_only(
        app.ax_bt,
        app.chart_times_live,
        app.chart_prices_live,
        title="",
        y_label="Price",
        max_ticks=6,
        fixed_ylim=getattr(app, "bt_price_range_fixed", None),
    )
    app.canvas_bt.draw_idle()


def _align_ohlc_lengths(app, context: str) -> None:
    """
    Ensure OHLC arrays stay in sync with their corresponding time series.
    context: 'live', 'bt', 'stream', 'cl'
    """
    mapping = {
        "live": (app.chart_times_live, app.chart_highs_live, app.chart_lows_live, app.chart_closes_live),
        "bt": (app.chart_times_bt, app.chart_highs_bt, app.chart_lows_bt, app.chart_closes_bt),
        "stream": (app.chart_times_stream, app.chart_highs_stream, app.chart_lows_stream, app.chart_closes_stream),
        "cl": (app.chart_cl_times, app.chart_highs_cl, app.chart_lows_cl, app.chart_closes_cl),
    }
    times, highs, lows, closes = mapping[context]
    target = len(times)
    for arr in (highs, lows, closes):
        if len(arr) > target:
            del arr[: len(arr) - target]


def update_chart_live(app, now_dt: datetime, last_val: float, high: float | None = None, low: float | None = None, redraw: bool = True) -> None:
    app.chart_times_live.append(now_dt)
    app.chart_prices_live.append(last_val)
    app.chart_highs_live.append(high if high is not None else last_val)
    app.chart_lows_live.append(low if low is not None else last_val)
    app.chart_closes_live.append(last_val)
    # Keep the full live history in memory so the trend can be viewed end-to-end.
    # Trimming is intentionally skipped for live data to preserve all ticks.
    _align_ohlc_lengths(app, "live")
    try:
        app._log_macd_row(app.chart_times_live, app.chart_prices_live, context="live")
    except Exception:
        pass
    if redraw and not app.suppress_backtest_ui:
        redraw_chart(app)


def update_chart_bt(app, now_dt: datetime, last_val: float, high: float | None = None, low: float | None = None) -> None:
    app.chart_times_bt.append(now_dt)
    app.chart_prices_bt.append(last_val)
    app.chart_highs_bt.append(high if high is not None else last_val)
    app.chart_lows_bt.append(low if low is not None else last_val)
    app.chart_closes_bt.append(last_val)
    # Avoid trimming during quick backtests so the trend chart shows full history.
    if not getattr(app, "suppress_backtest_ui", False):
        app._trim_window(
            app.chart_times_bt,
            app.chart_prices_bt,
            [
                (app.bt_open_long_x, app.bt_open_long_y),
                (app.bt_close_long_x, app.bt_close_long_y),
                (app.bt_open_short_x, app.bt_open_short_y),
                (app.bt_close_short_x, app.bt_close_short_y),
            ],
            app.bt_position_spans,
        )
    _align_ohlc_lengths(app, "bt")


def update_chart_stream(app, now_dt: datetime, last_val: float, high: float | None = None, low: float | None = None, redraw: bool = True, clear_macd_cache: bool = True) -> None:
    app.chart_times_stream.append(now_dt)
    app.chart_prices_stream.append(last_val)
    app.chart_highs_stream.append(high if high is not None else last_val)
    app.chart_lows_stream.append(low if low is not None else last_val)
    app.chart_closes_stream.append(last_val)
    app._trim_window(
        app.chart_times_stream,
        app.chart_prices_stream,
        [
            (app.stream_open_long_x, app.stream_open_long_y),
            (app.stream_close_long_x, app.stream_close_long_y),
            (app.stream_open_short_x, app.stream_open_short_y),
            (app.stream_close_short_x, app.stream_close_short_y),
        ],
        app.stream_position_spans,
        limit=app.max_points_stream,
        # Preserve MACD/EMA state when trimming streaming data so hist/lines stay stable
        clear_macd_cache=False,
    )
    _align_ohlc_lengths(app, "stream")
    try:
        app._log_macd_row(app.chart_times_stream, app.chart_prices_stream, context="stream")
    except Exception:
        pass
    if redraw:
        redraw_stream_chart(app)


def _update_range(app, attr_name: str, values: List[float], padding_ratio: float = 0.02) -> tuple | None:
    if not values:
        return None
    mn = min(values)
    mx = max(values)
    span = mx - mn
    pad = span * padding_ratio if span > 0 else max(0.1, abs(mx) * padding_ratio or 0.1)
    new_range = (mn - pad, mx + pad)
    setattr(app, attr_name, new_range)
    return new_range


def update_chart_cl(app, now_dt: datetime, last_val: float, high: float | None = None, low: float | None = None) -> None:
    app.chart_cl_times.append(now_dt)
    app.chart_cl_prices.append(last_val)
    app.chart_highs_cl.append(high if high is not None else last_val)
    app.chart_lows_cl.append(low if low is not None else last_val)
    app.chart_closes_cl.append(last_val)
    app._trim_window(app.chart_cl_times, app.chart_cl_prices, adjust_positions=False)
    _align_ohlc_lengths(app, "cl")
    redraw_chart_cl(app)


def redraw_stream_chart(app) -> None:
    if app.stream_ax is None or app.stream_canvas is None:
        return
    plotting.draw_price_only(
        app.stream_ax,
        app.chart_times_stream,
        app.chart_prices_stream,
        title="Streaming Backtest Trend",
        y_label="Price",
        max_ticks=8,
        fixed_ylim=getattr(app, "stream_price_range_fixed", None),
    )
    app.stream_canvas.draw_idle()
