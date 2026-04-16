"""
Plotting helpers extracted from the UI class.
"""
import matplotlib as mpl
import math
from typing import List, Any
from datetime import datetime

# Default colors (light theme); overridden via apply_theme at startup.
_DEFAULT_THEME = {
    "chart_face": "#FFFFFF",
    "chart_text": "#000000",
    "muted_text": "#444444",
    "grid": "#DDDDDD",
    "line": "#000000",
    "axis_edge": "#000000",
    "positive": "#2ca02c",
    "negative": "#d62728",
}
_THEME = dict(_DEFAULT_THEME)


def apply_theme(palette) -> None:
    """
    Update Matplotlib defaults with the provided palette (ThemePalette or dict).
    """
    global _THEME
    def _val(key: str, alt: str | None = None):
        if isinstance(palette, dict):
            if palette.get(key):
                return palette.get(key)
            if alt and palette.get(alt):
                return palette.get(alt)
            return None
        return getattr(palette, key, None) or (getattr(palette, alt, None) if alt else None)
    colors = {
        "chart_face": _val("chart_face", "background"),
        "chart_text": _val("chart_text", "text"),
        "muted_text": _val("muted_text", "text"),
        "grid": _val("chart_grid", "grid"),
        "line": _val("line_primary", "line"),
        "axis_edge": _val("chart_text", "text"),
        "positive": _val("positive"),
        "negative": _val("negative"),
    }
    merged = dict(_DEFAULT_THEME)
    for key, val in colors.items():
        if val:
            merged[key] = val
    _THEME = merged

    mpl.rcParams["figure.facecolor"] = _THEME["chart_face"]
    mpl.rcParams["axes.facecolor"] = _THEME["chart_face"]
    mpl.rcParams["axes.edgecolor"] = _THEME["axis_edge"]
    mpl.rcParams["axes.labelcolor"] = _THEME["chart_text"]
    mpl.rcParams["xtick.color"] = _THEME["muted_text"]
    mpl.rcParams["ytick.color"] = _THEME["muted_text"]
    mpl.rcParams["text.color"] = _THEME["chart_text"]
    mpl.rcParams["legend.edgecolor"] = _THEME["axis_edge"]


def _apply_theme(ax) -> None:
    """Apply current theme on a Matplotlib Axes."""
    if ax is None:
        return
    ax.set_facecolor(_THEME["chart_face"])
    fig = ax.get_figure()
    if fig:
        try:
            fig.patch.set_facecolor(_THEME["chart_face"])
        except Exception:
            pass
    for spine in ax.spines.values():
        spine.set_color(_THEME["axis_edge"])
    ax.tick_params(colors=_THEME["muted_text"])
    ax.yaxis.label.set_color(_THEME["chart_text"])
    ax.xaxis.label.set_color(_THEME["chart_text"])
    ax.title.set_color(_THEME["chart_text"])
    ax.grid(color=_THEME["grid"], alpha=0.5)


# Initialize Matplotlib with default theme so figures created before app init look consistent.
apply_theme(_DEFAULT_THEME)


def draw_macd_panel(ax_macd, macd_hist: List[float], dif: List[float], dea: List[float]) -> None:
    """Render MACD histogram + lines with consistent styling (bars touching)."""
    if ax_macd is None:
        return
    _apply_theme(ax_macd)
    ax_macd.axhline(0, color=_THEME["muted_text"], linewidth=0.6, linestyle="--", alpha=0.7)
    if macd_hist:
        colors = [_THEME["positive"] if v >= 0 else _THEME["negative"] for v in macd_hist]
        x_vals = list(range(len(macd_hist)))
        ax_macd.bar(x_vals, macd_hist, color=colors, alpha=0.6, width=1.0, align="center")
        ax_macd.set_xlim(-0.5, len(macd_hist) - 0.5)
    if dif:
        ax_macd.plot(range(len(dif)), dif, color="#1f77b4", linewidth=1, label="DIF")
    if dea:
        ax_macd.plot(range(len(dea)), dea, color="#ff7f0e", linewidth=1, label="DEA")
    if ax_macd.get_legend_handles_labels()[0]:
        ax_macd.legend(loc="upper left", fontsize=8, frameon=False)
    ax_macd.relim()
    ax_macd.autoscale_view()


def draw_macd_flips(ax_macd, markers: dict | None) -> None:
    if ax_macd is None or not markers:
        return
    for side, data in markers.items():
        if not data:
            continue
        xs = [pt[0] for pt in data]
        ys = [pt[1] for pt in data]
        color = _THEME["negative"] if side == "bear" else _THEME["positive"]
        marker = "v" if side == "bear" else "^"
        ax_macd.scatter(xs, ys, c=color, marker=marker, s=60, edgecolor=_THEME["axis_edge"], zorder=5)
        for x, y, text in data:
            ax_macd.text(x, y, text, ha="center", va="bottom", color=color, fontsize=8, fontweight="bold", zorder=6)

# Shared height ratio for price:MACD panels
PRICE_MACD_HEIGHT_RATIOS = (3, 1)


def _time_to_x(times: List[Any], fallback_length: int) -> List[Any]:
    return list(range(fallback_length if times is None else len(times)))


def draw_price_macd(
    ax_price,
    ax_macd,
    times: List[Any],
    prices: List[float],
    spans=None,
    markers=None,
    title: str = "",
    y_label: str = "Price",
    max_ticks: int = 10,
    macd_fetcher=None,
    macd_data=None,
    fixed_ylim=None,
    macd_fixed_ylim=None,
) -> None:
    """
    Draw price line, optional spans/markers, and MACD panel on the provided axes.
    """
    ax_price.clear()
    ax_macd.clear()
    _apply_theme(ax_price)
    _apply_theme(ax_macd)
    ax_price.set_title(title)
    ax_price.set_ylabel(y_label)
    ax_macd.set_ylabel("MACD")
    ax_macd.set_xlabel("Time")

    if times and prices:
        n = len(prices)
        x_vals = _time_to_x(times, n)
        ax_price.plot(x_vals, prices, linewidth=1, color=_THEME["line"])

        if spans:
            for x0, x1, color in spans:
                start = min(x0, x1)
                end = max(x0, x1)
                ax_price.axvspan(start, end, color=color, alpha=0.12, linewidth=0)

        if markers:
            if markers.get("open_long_x"):
                ax_price.scatter(
                    markers["open_long_x"],
                    markers["open_long_y"],
                    c=_THEME["negative"],
                    marker="^",
                    s=40,
                )
            if markers.get("close_long_x"):
                ax_price.scatter(
                    markers["close_long_x"],
                    markers["close_long_y"],
                    c=_THEME["negative"],
                    marker="v",
                    s=40,
                )
            if markers.get("open_short_x"):
                ax_price.scatter(
                    markers["open_short_x"],
                    markers["open_short_y"],
                    c=_THEME["positive"],
                    marker="v",
                    s=40,
                )
            if markers.get("close_short_x"):
                ax_price.scatter(
                    markers["close_short_x"],
                    markers["close_short_y"],
                    c=_THEME["positive"],
                    marker="^",
                    s=40,
                )

        if len(x_vals) > 0:
            xmin = min(x_vals)
            xmax = max(x_vals)
            if xmin == xmax:
                pad = 1.0
                ax_price.set_xlim(xmin - pad, xmax + pad)
            else:
                ax_price.set_xlim(xmin, xmax)
        if fixed_ylim is None:
            ax_price.relim()
            ax_price.autoscale_view(scalex=False, scaley=True)

        step = max(1, n // max_ticks)
        tick_positions = list(range(0, n, step))
        tick_labels = [
            t.strftime("%H:%M") if isinstance(t, datetime) else str(t)
            for t in (times[i] for i in tick_positions) if times
        ] if times else [str(i) for i in tick_positions]
        ax_macd.set_xticks(tick_positions)
        ax_macd.set_xticklabels(tick_labels, rotation=0)
        ax_price.tick_params(labelbottom=False)

        macd_hist = dif = dea = []
        if macd_data is not None:
            macd_hist, dif, dea = macd_data
        elif macd_fetcher:
            macd_hist, dif, dea = macd_fetcher(times, prices)
        if macd_hist or dif or dea:
            draw_macd_panel(ax_macd, macd_hist, dif, dea)
        else:
            ax_macd.relim()
            ax_macd.autoscale_view()
    else:
        if fixed_ylim is None:
            ax_price.relim()
            ax_price.autoscale_view()
        if macd_fixed_ylim is None:
            ax_macd.relim()
            ax_macd.autoscale_view()

    if fixed_ylim:
        try:
            ax_price.set_ylim(*fixed_ylim)
        except Exception:
            pass
    if macd_fixed_ylim:
        try:
            ax_macd.set_ylim(*macd_fixed_ylim)
        except Exception:
            pass


def draw_price_only(ax_price, times: List[Any], prices: List[float], title: str, y_label: str, max_ticks: int = 8, fixed_ylim=None) -> None:
    """
    Draw a simple price line chart without MACD or markers.
    """
    ax_price.clear()
    _apply_theme(ax_price)
    ax_price.set_title(title)
    ax_price.set_xlabel("Time")
    ax_price.set_ylabel(y_label)
    n = len(prices)
    if n > 0:
        x_vals = _time_to_x(times, n)
        ax_price.plot(x_vals, prices, linewidth=1, color=_THEME["line"])
        step = max(1, n // max_ticks)
        tick_positions = list(range(0, n, step))
        tick_labels = [
            times[i].strftime("%H:%M") if times else str(i)
            for i in tick_positions
        ]
        ax_price.set_xticks(tick_positions)
        ax_price.set_xticklabels(tick_labels, rotation=0)
    if fixed_ylim is None:
        ax_price.relim()
        ax_price.autoscale_view()
    if fixed_ylim:
        try:
            ax_price.set_ylim(*fixed_ylim)
        except Exception:
            pass


def draw_price_macd_markers(
    ax_price,
    ax_macd,
    times: List[Any],
    prices: List[float],
    markers: dict | None,
    spans=None,
    title: str = "",
    y_label: str = "Price",
    max_ticks: int = 6,
    macd_fetcher=None,
    no_data_text: str | None = None,
    macd_data=None,
    fixed_ylim=None,
    macd_fixed_ylim=None,
    ax_rsi=None,
    rsi_data: List[float] | None = None,
    rsi_visible: bool = True,
    rsi_color: str = "#ffd740",
    rsi_linewidth: float = 0.8,
) -> None:
    """
    Draw price + MACD with shaded spans and scatter markers, including legend.
    """
    ax_price.clear()
    ax_macd.clear()
    _apply_theme(ax_price)
    _apply_theme(ax_macd)
    ax_price.set_title(title)
    ax_price.set_ylabel(y_label)
    ax_macd.set_ylabel("MACD")
    ax_macd.set_xlabel("Time")

    if ax_rsi is not None:
        try:
            ax_rsi.clear()
        except Exception:
            pass
        _apply_theme(ax_rsi)
        ax_rsi.set_ylabel("RSI")
        ax_rsi.set_ylim(0, 100)
        ax_rsi.set_xticks([])
        ax_rsi.xaxis.set_visible(False)
        ax_rsi.patch.set_alpha(0)
        for spine in ax_rsi.spines.values():
            spine.set_color(rsi_color)
        ax_rsi.set_zorder(ax_macd.get_zorder() + 0.5)

    if prices:
        x_vals = _time_to_x(times, len(prices))
        ax_price.plot(x_vals, prices, linewidth=1, color=_THEME["line"])
        if spans:
            for start, end, color in spans:
                s = min(start, end)
                e = max(start, end)
                ax_price.axvspan(s, e, color=color, alpha=0.12, linewidth=0)

        legend_handles = []
        if markers:
            if markers.get("open_long_x"):
                h1 = ax_price.scatter(
                    markers["open_long_x"],
                    markers["open_long_y"],
                    c=_THEME["negative"],
                    marker="^",
                    s=70,
                    edgecolors=_THEME["axis_edge"],
                    linewidths=0.8,
                    zorder=5,
                    label="Open Long",
                )
                legend_handles.append(h1)
            if markers.get("close_long_x"):
                h2 = ax_price.scatter(
                    markers["close_long_x"],
                    markers["close_long_y"],
                    c=_THEME["negative"],
                    marker="x",
                    s=80,
                    linewidths=1.2,
                    zorder=6,
                    label="Close Long",
                )
                legend_handles.append(h2)
            if markers.get("open_short_x"):
                h3 = ax_price.scatter(
                    markers["open_short_x"],
                    markers["open_short_y"],
                    c=_THEME["positive"],
                    marker="v",
                    s=70,
                    edgecolors=_THEME["axis_edge"],
                    linewidths=0.8,
                    zorder=5,
                    label="Open Short",
                )
                legend_handles.append(h3)
            if markers.get("close_short_x"):
                h4 = ax_price.scatter(
                    markers["close_short_x"],
                    markers["close_short_y"],
                    facecolors="none",
                    edgecolors=_THEME["positive"],
                    marker="o",
                    s=80,
                    linewidths=1.2,
                    zorder=6,
                    label="Close Short",
                )
                legend_handles.append(h4)
        if legend_handles:
            ax_price.legend(handles=legend_handles, loc="upper left", fontsize=8, frameon=False)

        step = max(1, len(prices) // max_ticks)
        tick_positions = list(range(0, len(prices), step))
        tick_labels = [
            times[i].strftime("%H:%M") if times else str(i)
            for i in tick_positions
        ]
        ax_price.set_xticks(tick_positions)
        ax_price.set_xticklabels(tick_labels, rotation=0)

        macd_hist = dif = dea = []
        if macd_data is not None:
            macd_hist, dif, dea = macd_data
        elif macd_fetcher:
            macd_hist, dif, dea = macd_fetcher(times if times else list(range(len(prices))), prices)
        if macd_hist or dif or dea:
            draw_macd_panel(ax_macd, macd_hist, dif, dea)
        if ax_rsi and rsi_data and rsi_visible:
            valid = [(x, v) for x, v in zip(x_vals, rsi_data) if v is not None]
            if valid:
                xs, ys = zip(*valid)
                ax_rsi.plot(xs, ys, color=rsi_color, linewidth=rsi_linewidth, linestyle="-", label="RSI")
                try:
                    ax_rsi.set_ylim(0, 100)
                except Exception:
                    pass
                if ax_rsi.get_legend_handles_labels()[0]:
                    ax_rsi.legend(loc="upper right", fontsize=7, frameon=False)
    else:
        if no_data_text:
            ax_price.text(0.5, 0.5, no_data_text, ha="center", va="center", transform=ax_price.transAxes)

    if fixed_ylim is None:
        ax_price.relim()
        ax_price.autoscale_view()
    if macd_fixed_ylim is None:
        ax_macd.relim()
        ax_macd.autoscale_view()
    if fixed_ylim:
        try:
            ax_price.set_ylim(*fixed_ylim)
        except Exception:
            pass
    if macd_fixed_ylim:
        try:
            ax_macd.set_ylim(*macd_fixed_ylim)
        except Exception:
            pass


def draw_relation(ax, points, x_label: str, y_label: str) -> None:
    """
    Scatter relation points with labels on the given axes.
    """
    ax.clear()
    _apply_theme(ax)
    ax.set_xlabel(x_label or "X")
    ax.set_ylabel(y_label or "Y")
    if points:
        xs = [p[1] for p in points]
        ys = [p[2] for p in points]
        ax.scatter(xs, ys, c="blue")
        for name, x, y in points:
            ax.annotate(name, (x, y), textcoords="offset points", xytext=(4, 4))
    ax.grid(True, linestyle="--", alpha=0.4, color=_THEME["grid"])


def trim_window(
    times: List[Any],
    prices: List[float],
    marker_pairs=None,
    spans=None,
    adjust_positions: bool = True,
    limit: int | None = None,
    macd_cache_clearers=None,
    clear_macd_cache: bool = True,
) -> None:
    """
    Keep only the last `limit` entries (or caller's default) and shift marker indices accordingly.
    """
    if limit is None:
        return
    if len(times) <= limit:
        return
    drop = len(times) - limit
    del times[:drop]
    del prices[:drop]
    if clear_macd_cache and macd_cache_clearers:
        for cache in macd_cache_clearers:
            try:
                cache.clear()
            except Exception:
                pass
    if marker_pairs:
        for xs, ys in marker_pairs:
            i = 0
            while i < len(xs):
                new_x = xs[i] - drop
                if new_x < 0:
                    del xs[i]
                    if i < len(ys):
                        del ys[i]
                else:
                    xs[i] = new_x
                    i += 1
    if spans is not None:
        trimmed_spans = []
        for x0, x1, color in spans:
            nx0 = x0 - drop
            nx1 = x1 - drop
            if nx0 >= 0 or nx1 >= 0:
                trimmed_spans.append((max(nx0, 0), max(nx1, 0), color))
        spans.clear()
        spans.extend(trimmed_spans)
    if adjust_positions:
        # caller can adjust open_index separately if needed
        pass
