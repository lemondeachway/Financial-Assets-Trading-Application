"""
Strategy logic extracted from the monolithic app.
Provides mean-reversion and inverse mean-reversion helpers.
"""
from typing import List, Optional, Dict, Any

def update_mean_revert_state(prices: List[float], window: int, cap: int) -> List[float]:
    """
    Append latest price and trim to cap size for SMA calculation.
    """
    prices = list(prices)
    if len(prices) > cap:
        prices = prices[-cap:]
    return prices

def mean_revert_decision(
    price: float,
    prices: List[float],
    window: int,
    band: float,
    stop: float,
    prev_dist: Optional[float],
    open_positions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Return decisions for mean-reversion (M1).
    """
    decision: Dict[str, Any] = {"action": None, "log": None}
    if len(prices) < window + 1:
        decision["log"] = f"warmup {len(prices)}/{window+1}"
        return decision
    sma = sum(prices[-window:]) / window
    dist = price - sma
    decision["dist"] = dist

    # Exit checks if holding any (use first position as reference)
    if open_positions:
        pos = open_positions[0]
        side = pos["side"]
        entry = pos["open_price"]
        if side == "long":
            if price >= sma:
                decision["action"] = "close_long"
                decision["log"] = "exit: CLOSE LONG (back to SMA)"
            elif price <= entry - stop:
                decision["action"] = "close_long"
                decision["log"] = "stop: CLOSE LONG (stop-loss)"
        elif side == "short":
            if price <= sma:
                decision["action"] = "close_short"
                decision["log"] = "exit: CLOSE SHORT (back to SMA)"
            elif price >= entry + stop:
                decision["action"] = "close_short"
                decision["log"] = "stop: CLOSE SHORT (stop-loss)"
    # Entry signals (allowed even when already holding)
    if decision["action"] is None:
        if dist < -band and (prev_dist is None or prev_dist >= -band):
            decision["action"] = "open_long"
            decision["log"] = "signal: OPEN LONG (below band)"
        elif dist > band and (prev_dist is None or prev_dist <= band):
            decision["action"] = "open_short"
            decision["log"] = "signal: OPEN SHORT (above band)"
    decision["prev_dist"] = dist
    return decision

def inverse_mean_revert_decision(
    price: float,
    prices: List[float],
    window: int,
    band: float,
    stop: float,
    prev_dist: Optional[float],
    open_positions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Return decisions for inverse mean-reversion (M2).
    """
    decision: Dict[str, Any] = {"action": None, "log": None}
    if len(prices) < window + 1:
        decision["log"] = f"warmup {len(prices)}/{window+1}"
        return decision
    sma = sum(prices[-window:]) / window
    dist = price - sma
    decision["dist"] = dist

    if open_positions:
        pos = open_positions[0]
        side = pos["side"]
        entry = pos["open_price"]
        if side == "short":
            if price >= sma:
                decision["action"] = "close_short"
                decision["log"] = "exit: CLOSE SHORT (back to SMA)"
            elif price <= entry - stop:
                decision["action"] = "close_short"
                decision["log"] = "stop: CLOSE SHORT (stop-profit)"
        elif side == "long":
            if price <= sma:
                decision["action"] = "close_long"
                decision["log"] = "exit: CLOSE LONG (back to SMA)"
            elif price >= entry + stop:
                decision["action"] = "close_long"
                decision["log"] = "stop: CLOSE LONG (stop-profit)"
    if decision["action"] is None:
        if dist < -band and (prev_dist is None or prev_dist >= -band):
            decision["action"] = "open_short"
            decision["log"] = "signal: OPEN SHORT (inverse)"
        elif dist > band and (prev_dist is None or prev_dist <= band):
            decision["action"] = "open_long"
            decision["log"] = "signal: OPEN LONG (inverse)"
    decision["prev_dist"] = dist
    return decision
