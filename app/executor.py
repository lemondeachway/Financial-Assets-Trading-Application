"""
Auto-clicker / command execution helpers extracted from the UI class.
These functions are UI-agnostic and operate on an app-like object that
exposes the expected attributes (positions, dry_run, human_move, etc.).
"""
import os
import random
import time
from typing import Optional, Tuple

try:
    import pyautogui

    PYAUTOGUI_AVAILABLE = True
    pyautogui.FAILSAFE = True
except Exception:
    PYAUTOGUI_AVAILABLE = False


def parse_command_file(path: str) -> Optional[dict]:
    cmd_time = None
    cmd_name = None
    cmd_price: Optional[float] = None
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip().lower()
                value = value.strip()
                if key == "time":
                    cmd_time = value
                elif key == "command":
                    cmd_name = value.upper()
                elif key == "price":
                    try:
                        cmd_price = float(value)
                    except ValueError:
                        cmd_price = None
    except Exception:
        return None
    if cmd_name is None:
        return None
    return {"time": cmd_time, "command": cmd_name, "price": cmd_price}


def jitter_point(pos: Tuple[int, int], radius: int) -> Tuple[int, int]:
    if radius <= 0:
        return pos
    return (
        pos[0] + random.randint(-radius, radius),
        pos[1] + random.randint(-radius, radius),
    )


def move_and_click(app, pos: Tuple[int, int]) -> None:
    if not PYAUTOGUI_AVAILABLE:
        return
    x, y = pos
    if getattr(app, "dry_run", False):
        app.status_label.config(text=f"Status: DRY-RUN click at ({x},{y})")
        return
    pyautogui.moveTo(x, y, duration=0.15)
    pyautogui.click()
    if getattr(app, "default_cursor_pos", None) is not None:
        dx, dy = app.default_cursor_pos
        pyautogui.moveTo(dx, dy, duration=0.15)


def human_move_and_click(app, pos: Tuple[int, int], button: str = "left") -> None:
    if not PYAUTOGUI_AVAILABLE:
        return
    if getattr(app, "dry_run", False):
        app.status_label.config(text=f"Status: DRY-RUN human click at {pos} [{button}]")
        return

    target = jitter_point(pos, getattr(app, "jitter_pixels", 0))
    overshoot = getattr(app, "overshoot_pixels", 0)
    move_time_range = getattr(app, "move_time_range", (0.25, 0.45))
    click_hold_range = getattr(app, "click_hold_range", (0.05, 0.12))
    jitter = getattr(app, "jitter_pixels", 0)
    if overshoot > 0:
        ox = target[0] + random.randint(-overshoot, overshoot)
        oy = target[1] + random.randint(-overshoot, overshoot)
        pyautogui.moveTo(ox, oy, duration=random.uniform(*move_time_range), tween=pyautogui.easeInOutQuad)

    pyautogui.moveTo(target[0], target[1], duration=random.uniform(*move_time_range), tween=pyautogui.easeInOutQuad)
    time.sleep(random.uniform(0.02, 0.06))
    hold = random.uniform(*click_hold_range)
    pyautogui.mouseDown(button=button)
    time.sleep(hold)
    pyautogui.mouseUp(button=button)
    if getattr(app, "default_cursor_pos", None) is not None:
        dx, dy = jitter_point(app.default_cursor_pos, jitter)
        pyautogui.moveTo(dx, dy, duration=random.uniform(*move_time_range), tween=pyautogui.easeInOutQuad)


def resolve_pos(app, name: str) -> Optional[Tuple[int, int]]:
    if name == "OPEN_LONG_POS":
        return getattr(app, "open_long_pos", None)
    if name == "OPEN_SHORT_POS":
        return getattr(app, "open_short_pos", None)
    if name == "CLOSE_POS":
        return getattr(app, "close_pos", None)
    return None


def execute_command_click(app, cmd_name: str) -> None:
    seq = getattr(app, "action_sequences", {}).get(cmd_name)
    if not seq:
        return
    for step in seq:
        if step.get("type") == "delay":
            time.sleep(random.uniform(*getattr(app, "inter_step_delay", (0.06, 0.15))))
            continue
        pos_name = step.get("pos")
        pos_val = resolve_pos(app, pos_name) if isinstance(pos_name, str) else pos_name
        button = step.get("button", "left")
        if pos_val is None:
            continue
        if getattr(app, "human_move", False):
            human_move_and_click(app, pos_val, button=button)
        else:
            move_and_click(app, pos_val)
        time.sleep(random.uniform(*getattr(app, "inter_step_delay", (0.06, 0.15))))


def watch_commands_loop(app) -> None:
    stop_event = getattr(app, "click_stop_event", None)
    command_dir = getattr(app, "command_dir", "")
    while stop_event and (not stop_event.is_set()):
        try:
            files = os.listdir(command_dir)
        except FileNotFoundError:
            os.makedirs(command_dir, exist_ok=True)
            files = []
        cmd_files = [f for f in files if f.startswith("cmd_") and f.endswith(".txt")]
        cmd_files.sort()
        for fname in cmd_files:
            path = os.path.join(command_dir, fname)
            info = parse_command_file(path)
            try:
                os.remove(path)
            except OSError:
                pass
            if info is None:
                continue
            if info.get("command", "") not in getattr(app, "action_sequences", {}):
                continue
            execute_command_click(app, info.get("command", ""))
        time.sleep(0.2)
