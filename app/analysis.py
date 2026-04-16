"""
Analysis/statistics utilities extracted from the UI code.
"""
import statistics
from typing import List, Optional
from datetime import datetime
import csv

from core.sessions import SESSION_NAMES, session_bucket


def percentile(data: List[float], pct: float) -> Optional[float]:
    if not data:
        return None
    k = (len(data) - 1) * pct
    f = int(k)
    c = min(f + 1, len(data) - 1)
    if f == c:
        return data[f]
    return data[f] + (data[c] - data[f]) * (k - f)


def summarize_price_series(times: List[datetime], prices: List[float], window: int = 20) -> List[str]:
    """
    Return human-readable summary lines for a time/price series.
    """
    if not prices or not times:
        return ["No valid time/price rows"]

    prices_sorted = sorted(prices)
    count = len(prices)
    p_min = min(prices)
    p_max = max(prices)
    p_range = p_max - p_min
    p_mean = statistics.mean(prices)
    p_median = statistics.median(prices)
    p_stdev = statistics.stdev(prices) if count > 1 else 0.0
    p5 = percentile(prices_sorted, 0.05)
    p95 = percentile(prices_sorted, 0.95)

    return [
        f"Rows: {count}",
        f"Price min/max: {p_min:.2f} / {p_max:.2f}  (range {p_range:.2f})",
        f"Mean/Median: {p_mean:.2f} / {p_median:.2f}",
        f"Stdev: {p_stdev:.2f}",
        f"5th/95th percentiles: {p5:.2f} / {p95:.2f}" if p5 is not None and p95 is not None else "Percentiles: n/a",
    ]


def _session_summary_lines(times: List[datetime]) -> List[str]:
    """
    Return descriptive lines that highlight the morning/afternoon/night breakdown.
    """
    counts = {name: 0 for name in SESSION_NAMES}
    first_seen: dict[str, datetime] = {}
    last_seen: dict[str, datetime] = {}
    for dt_val in times:
        name = session_bucket(dt_val)
        counts[name] += 1
        if name not in first_seen or dt_val < first_seen[name]:
            first_seen[name] = dt_val
        if name not in last_seen or dt_val > last_seen[name]:
            last_seen[name] = dt_val
    coverage = ", ".join(f"{name.title()} {counts[name]} rows" for name in SESSION_NAMES)
    span_parts = []
    for name in SESSION_NAMES:
        if counts[name]:
            span_parts.append(
                f"{name.title()} {first_seen[name].strftime('%H:%M:%S')}–{last_seen[name].strftime('%H:%M:%S')}"
            )
        else:
            span_parts.append(f"{name.title()} none")
    return [f"Session coverage: {coverage}", f"Session spans: {', '.join(span_parts)}"]


def load_time_price_csv(path: str) -> tuple[List[datetime], List[float]]:
    """
    Load a CSV containing time,price rows. Returns (times, prices).
    Raises ValueError on failure or if no valid rows.
    """
    try:
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
    except Exception as e:
        raise ValueError(f"Failed to load CSV: {e}")
    if not rows:
        raise ValueError("Empty CSV file")

    times: List[datetime] = []
    prices: List[float] = []
    start_idx = 0
    if rows[0] and rows[0][0].lower() in ("local_time", "time"):
        start_idx = 1
    for row in rows[start_idx:]:
        if len(row) < 2:
            continue
        t_str, p_str = row[0], row[1]
        try:
            dt_val = datetime.strptime(t_str, "%Y-%m-%d %H:%M:%S")
            p_val = float(p_str)
        except Exception:
            continue
        times.append(dt_val)
        prices.append(p_val)
    if not prices or not times:
        raise ValueError("No valid time/price rows")
    return times, prices


def summarize_csv_paths(paths: List[str]) -> List[str]:
    """
    Produce summaries for multiple CSV paths. Returns flat list of lines.
    Raises ValueError if any path fails.
    """
    summaries: List[str] = []
    for path in paths:
        times, prices = load_time_price_csv(path)
        summary_lines = summarize_price_series(times, prices, window=20)
        summary_lines.extend(_session_summary_lines(times))
        summaries.extend([f"File: {path}"] + summary_lines)
    return summaries
