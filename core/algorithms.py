"""
Algorithmic helpers for indicators and strategy building blocks.
These functions are UI-agnostic and can be reused in backtests or live logic.
"""
from typing import List, Tuple, Any, Optional
from datetime import datetime


def sma(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def atr(values: List[float]) -> float:
    """Legacy simple ATR using absolute close-to-close moves."""
    if len(values) < 2:
        return 0.0
    moves = [abs(values[i] - values[i - 1]) for i in range(1, len(values))]
    return sum(moves) / len(moves) if moves else 0.0


def true_range_series(highs: List[float], lows: List[float], closes: List[float]) -> List[float]:
    """
    Compute true range per bar using high/low and previous close.
    Length matches inputs; first bar uses high-low as TR.
    """
    if not highs or not lows or not closes:
        return []
    trs: List[float] = []
    prev_close = closes[0]
    for h, l, c in zip(highs, lows, closes):
        tr = max(h - l, abs(h - prev_close), abs(l - prev_close))
        trs.append(tr)
        prev_close = c
    return trs


def atr_series_for(highs: List[float], lows: List[float], closes: List[float], window: int = 14) -> List[float]:
    """
    Wilder ATR series. Returns list same length as inputs; leading values
    are filled once enough data exists.
    """
    if not highs or not lows or not closes:
        return []
    trs = true_range_series(highs, lows, closes)
    atrs: List[float] = []
    if not trs:
        return atrs
    running_atr = None
    for i, tr in enumerate(trs):
        if i == 0:
            running_atr = tr
        elif i < window:
            running_atr = ((running_atr * i) + tr) / (i + 1)
        else:
            running_atr = ((running_atr * (window - 1)) + tr) / window
        atrs.append(running_atr)
    return atrs


def rsi_series(prices: List[float], window: int = 14) -> List[Optional[float]]:
    """
    Wilder RSI series matching the length of the price list.
    """
    if not prices:
        return []
    rsis: List[Optional[float]] = [None]
    avg_gain: Optional[float] = None
    avg_loss: Optional[float] = None
    for idx in range(1, len(prices)):
        delta = prices[idx] - prices[idx - 1]
        gain = max(delta, 0.0)
        loss = max(-delta, 0.0)
        if avg_gain is None:
            avg_gain = gain
            avg_loss = loss
        else:
            avg_gain = (avg_gain * (window - 1) + gain) / window
            avg_loss = (avg_loss * (window - 1) + loss) / window
        if idx < window or avg_loss is None:
            rsis.append(None)
            continue
        if avg_loss == 0:
            rsis.append(100.0)
            continue
        rs = avg_gain / avg_loss if avg_loss else float("inf")
        rsi = 100 - (100 / (1 + rs))
        rsis.append(rsi)
    return rsis


def stochastic_series(
    highs: List[float], lows: List[float], closes: List[float], window: int = 14
) -> List[Optional[float]]:
    """
    %K stochastic: how close the close sits to the high/low over the lookback window.
    """
    if not closes or not highs or not lows:
        return []
    stoch: List[Optional[float]] = []
    for idx in range(len(closes)):
        start = max(0, idx - window + 1)
        high_window = max(highs[start: idx + 1])
        low_window = min(lows[start: idx + 1])
        if high_window == low_window:
            stoch.append(None)
            continue
        stoch.append(100.0 * (closes[idx] - low_window) / (high_window - low_window))
    return stoch


def compute_macd_series(prices: List[float]) -> Tuple[List[float], List[float], List[float]]:
    """Return (macd_hist, dif, dea) lists using EMA12/EMA26 and signal=9."""
    if not prices:
        return [], [], []
    ema12: List[float] = []
    ema26: List[float] = []
    dif: List[float] = []
    dea: List[float] = []
    macd: List[float] = []
    alpha12 = 2 / (12 + 1)
    alpha26 = 2 / (26 + 1)
    alpha9 = 2 / (9 + 1)
    for price in prices:
        new_ema12 = price if not ema12 else ema12[-1] + alpha12 * (price - ema12[-1])
        new_ema26 = price if not ema26 else ema26[-1] + alpha26 * (price - ema26[-1])
        new_dif = new_ema12 - new_ema26
        new_dea = new_dif if not dea else dea[-1] + alpha9 * (new_dif - dea[-1])
        new_macd = 2 * (new_dif - new_dea)
        ema12.append(new_ema12)
        ema26.append(new_ema26)
        dif.append(new_dif)
        dea.append(new_dea)
        macd.append(new_macd)
    return macd, dif, dea


def macd_bucket_series(
    times: List[datetime], prices: List[float], bucket_minutes: int
) -> Tuple[List[float], List[float], List[float]]:
    """
    Compute MACD on bucket closes (e.g., 1m/3m/5m) and forward-fill per tick so lengths match price series.
    """
    if not prices or not times:
        return [], [], []
    macd_hist_full: List[float] = []
    dif_full: List[float] = []
    dea_full: List[float] = []

    def bucket_of(dt: datetime) -> datetime:
        minuteN = (dt.minute // bucket_minutes) * bucket_minutes
        return dt.replace(minute=minuteN, second=0, microsecond=0)

    bucket_start: datetime | None = None
    closes: List[float] = []
    current_macd = current_dif = current_dea = 0.0
    last_price = prices[0]

    for idx, (t, p) in enumerate(zip(times, prices)):
        b = bucket_of(t)
        if bucket_start is None:
            bucket_start = b
            closes.append(p)
            # seed MACD with first price
            macd_hist, dif, dea = compute_macd_series(closes)
            if macd_hist:
                current_macd = macd_hist[-1]
                current_dif = dif[-1]
                current_dea = dea[-1]
        elif b != bucket_start:
            # close previous bucket with the last price of that bucket (previous tick)
            prev_price = prices[idx - 1] if idx > 0 else p
            if closes[-1] != prev_price:
                closes.append(prev_price)
            macd_hist, dif, dea = compute_macd_series(closes)
            if macd_hist:
                current_macd = macd_hist[-1]
                current_dif = dif[-1]
                current_dea = dea[-1]
            bucket_start = b
        macd_hist_full.append(current_macd)
        dif_full.append(current_dif)
        dea_full.append(current_dea)
        last_price = p

    # ensure final bucket close is incorporated
    if closes and closes[-1] != last_price:
        closes.append(last_price)
        macd_hist, dif, dea = compute_macd_series(closes)
        if macd_hist:
            current_macd = macd_hist[-1]
            current_dif = dif[-1]
            current_dea = dea[-1]
        if macd_hist_full:
            macd_hist_full[-1] = current_macd
            dif_full[-1] = current_dif
            dea_full[-1] = current_dea

    return macd_hist_full, dif_full, dea_full


def macd_series_for(mode: str, times: List[Any], prices: List[float]) -> Tuple[List[float], List[float], List[float]]:
    mode = (mode or "5m").lower()
    if mode in ("tick", "per-tick", "ticks"):
        return compute_macd_series(prices)
    if mode == "1m":
        return macd_bucket_series(times, prices, 1)
    if mode == "3m":
        return macd_bucket_series(times, prices, 3)
    if mode == "10m":
        return macd_bucket_series(times, prices, 10)
    if mode == "15m":
        return macd_bucket_series(times, prices, 15)
    return macd_bucket_series(times, prices, 5)
