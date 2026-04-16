"""
Backtest utilities: CSV parsing and tick preparation.
These helpers are UI-agnostic so they can be used by both quick and streaming backtests.
"""
import csv
from datetime import datetime
from typing import List, Tuple


def parse_ticks_from_csv(path: str) -> List[Tuple[datetime, float, float, float, float]]:
    """
    Parse a CSV file into a list of (datetime, price) tuples.
    Detects headers with 'local_time' or 'time' and prefers 'last'/'price'/'close' columns.
    """
    ticks: List[Tuple[datetime, float, float, float, float]] = []
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    if not rows:
        return ticks

    start_idx = 0
    time_col = 0
    price_col = 1
    header = rows[0]

    def _find_col(header_row, candidates):
        lower_header = [h.lower() for h in header_row]
        for candidate in candidates:
            if candidate in lower_header:
                return lower_header.index(candidate)
        return None

    # If a leading data_point column exists, drop it for parsing purposes
    if header and header[0].lower() == "data_point":
        rows = [r[1:] for r in rows]
        header = rows[0] if rows else []

    if header and isinstance(header, list):
        lower_header = [h.lower() for h in header]
        if lower_header:
            if lower_header[0] in ("local_time", "time", "datetime"):
                start_idx = 1
            time_candidate = _find_col(header, ("local_time", "time", "datetime", "timestamp"))
            if time_candidate is not None:
                time_col = time_candidate
            price_candidate = _find_col(header, ("last", "price", "close", "open", "bid", "ask"))
            if price_candidate is not None:
                price_col = price_candidate

    high_col = None
    low_col = None
    if header and isinstance(header, list):
        lower_header = [h.lower() for h in header]
        if lower_header:
            if "high" in lower_header:
                high_col = lower_header.index("high")
            if "low" in lower_header:
                low_col = lower_header.index("low")

    prev_close = None
    for row in rows[start_idx:]:
        if len(row) <= max(time_col, price_col):
            continue
        t_str, p_str = row[time_col], row[price_col]
        if not t_str or not p_str:
            continue
        try:
            dt_val = datetime.strptime(t_str.strip(), "%Y-%m-%d %H:%M:%S")
            p_val = float(p_str)
        except Exception:
            continue
        try:
            h_val = float(row[high_col]) if high_col is not None and len(row) > high_col and row[high_col] else p_val
        except Exception:
            h_val = p_val
        try:
            l_val = float(row[low_col]) if low_col is not None and len(row) > low_col and row[low_col] else p_val
        except Exception:
            l_val = p_val
        if prev_close is None:
            prev_close = p_val
        ticks.append((dt_val, p_val, h_val, l_val, prev_close))
        prev_close = p_val

    return ticks
