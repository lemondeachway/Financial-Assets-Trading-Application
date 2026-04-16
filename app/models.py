"""
Core data models for the trading app.
Separated from the UI so other modules can reuse typed structures.
"""
from dataclasses import dataclass
from datetime import datetime, time as dtime
from typing import List, Optional, Dict, Any


# ---- Constants ----

TRADING_WINDOWS = [
    (dtime(8, 59, 59), dtime(10, 14, 59)),
    (dtime(10, 30, 0), dtime(11, 30, 0)),
    (dtime(13, 30, 0), dtime(15, 0, 0)),
    (dtime(20, 59, 59), dtime(23, 0, 0)),
]


# ---- Data classes ----

@dataclass
class Tick:
    contract: str
    last: Optional[float]
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    bid_vol: Optional[int] = None
    ask_vol: Optional[int] = None
    open_interest: Optional[float] = None
    volume: Optional[float] = None
    prev_settle: Optional[float] = None
    settle: Optional[float] = None
    fields: Optional[List[str]] = None
    payload: Optional[str] = None


@dataclass
class Position:
    side: str  # "long" or "short"
    owner: str  # "M1", "M2", "MANUAL"
    open_time: str
    open_price: float
    open_index: Optional[int]
    trail_max: Optional[float] = None
    trail_min: Optional[float] = None


@dataclass
class TradeCommand:
    time: str
    command: str  # OPEN_LONG/OPEN_SHORT/CLOSE_LONG/CLOSE_SHORT
    price: Optional[float] = None


@dataclass
class MACDSeries:
    hist: List[float]
    dif: List[float]
    dea: List[float]


@dataclass
class BacktestResult:
    path: str
    net: float
    gross: float
    extra: float
    trades: int
    markers: Dict[str, Any]
