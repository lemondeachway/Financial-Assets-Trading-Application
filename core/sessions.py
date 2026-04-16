"""
Utilities for the standard futures trading session buckets (morning/afternoon/night).
"""
from datetime import datetime, time as dtime
from typing import Literal

SessionName = Literal["morning", "afternoon", "night"]


SESSION_NAMES: tuple[SessionName, ...] = ("morning", "afternoon", "night")


def session_bucket(dt_val: datetime) -> SessionName:
    """
    Bucket a timestamp into one of the standard futures sessions.
    """
    local_time = dt_val.time()
    if local_time >= dtime(18, 0) or local_time < dtime(6, 0):
        return "night"
    if local_time >= dtime(12, 0):
        return "afternoon"
    return "morning"
