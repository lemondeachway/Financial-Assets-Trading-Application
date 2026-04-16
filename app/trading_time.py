from datetime import datetime
from typing import Optional
from models import TRADING_WINDOWS


def is_trading_time(now: Optional[datetime] = None) -> bool:
    """
    Return True if the provided (or current) time falls within configured TRADING_WINDOWS.
    """
    if now is None:
        now = datetime.now()
    t = now.time()
    for start, end in TRADING_WINDOWS:
        if start <= t <= end:
            return True
    return False
