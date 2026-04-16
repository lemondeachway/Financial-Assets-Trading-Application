"""
Lifecycle helpers for RealTickApp (clock loop and topmost suspension).
"""
from datetime import datetime
from typing import Any, Callable


def start_clock_loop(app: Any, trading_check) -> None:
    update_clock(app, trading_check)


def update_clock(app: Any, trading_check) -> None:
    now_dt = datetime.now()
    try:
        app.clock_label.config(text=f"Time: {now_dt.strftime('%H:%M:%S')}")
    except Exception:
        pass

    try:
        if getattr(app, "running", False) and not trading_check(now_dt):
            app.status_label.config(text=f"Status: waiting (now {now_dt.strftime('%H:%M:%S')})")
        app._refresh_status()
    except Exception:
        pass

    try:
        app.root.after(1000, lambda: update_clock(app, trading_check))
    except Exception:
        pass


def with_topmost_suspended(app: Any, fn: Callable):
    """Temporarily drop topmost so native dialogs are visible."""
    was_top = False
    try:
        was_top = bool(app.root.attributes("-topmost"))
    except Exception:
        was_top = False
    try:
        if was_top:
            app.root.attributes("-topmost", False)
        return fn()
    finally:
        try:
            if was_top:
                app.root.attributes("-topmost", True)
        except Exception:
            pass
