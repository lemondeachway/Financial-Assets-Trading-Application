"""
Persistence helpers for CSV writing and command file output.
"""
import os
import csv
from typing import Dict, Any, Optional
from datetime import datetime


def open_csv(app) -> None:
    if app.csv_file is not None:
        return
    try:
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        out_dir = app.csv_dir or os.path.join(root_dir, "data", "NR")
        os.makedirs(out_dir, exist_ok=True)
        date_token = datetime.now().strftime("%m%d%Y")
        base_filename = f"NR_{date_token}.csv"
        target_path = os.path.join(out_dir, base_filename)
        if os.path.exists(target_path):
            app.csv_header_written = os.path.getsize(target_path) > 0
            writer_mode = "a"
            status_txt = f"Status: running (appending to {base_filename})"
        else:
            writer_mode = "w"
            app.csv_header_written = False
            status_txt = f"Status: running (logging to {base_filename})"
        app.csv_file = open(target_path, writer_mode, newline="", encoding="utf-8")
        app.csv_writer = csv.writer(app.csv_file)
        app.status_label.config(text=status_txt)
    except Exception as e:
        app.status_label.config(text=f"Status: failed to open CSV: {e}")


def open_csv_cl(app) -> None:
    if app.csv_file_cl is not None:
        return
    try:
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        out_dir = app.csv_dir_cl or os.path.join(root_dir, "data", "CL")
        os.makedirs(out_dir, exist_ok=True)
        ts_now = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"CL_realtick_{ts_now}.csv"
        csv_path = os.path.join(out_dir, filename)
        app.csv_file_cl = open(csv_path, "w", newline="", encoding="utf-8")
        app.csv_writer_cl = csv.writer(app.csv_file_cl)
        app.csv_header_written_cl = False
        app.status_label.config(text=f"Status: running CL feed (logging to {filename})")
    except Exception as e:
        app.status_label.config(text=f"Status: failed to open CL CSV: {e}")


def close_csv(app) -> None:
    if app.csv_file is not None:
        try:
            app.csv_file.close()
        except Exception:
            pass
    app.csv_file = None
    app.csv_writer = None
    app.csv_header_written = False


def close_csv_cl(app) -> None:
    if app.csv_file_cl is not None:
        try:
            app.csv_file_cl.close()
        except Exception:
            pass
    app.csv_file_cl = None
    app.csv_writer_cl = None
    app.csv_header_written_cl = False


def write_csv_tick(app, time_str: str, tick: Dict[str, Any]) -> None:
    write_csv_tick_generic(app, "csv_writer", "csv_header_written", time_str, tick)


def write_csv_tick_cl(app, time_str: str, tick: Dict[str, Any]) -> None:
    write_csv_tick_generic(app, "csv_writer_cl", "csv_header_written_cl", time_str, tick)


def write_csv_tick_generic(app, writer_attr: str, header_attr: str, time_str: str, tick: Dict[str, Any]) -> None:
    writer = getattr(app, writer_attr, None)
    header_written = getattr(app, header_attr, False)
    if writer is None:
        return
    try:
        standard_fields = [
            "open",
            "high",
            "low",
            "bid",
            "ask",
            "last",
            "bid_vol",
            "ask_vol",
            "open_interest",
            "volume",
        ]
        use_standard = all(k in tick for k in standard_fields)
        if not header_written:
            if use_standard:
                writer.writerow(["local_time"] + standard_fields)
            else:
                fields = tick.get("fields", [])
                writer.writerow(["local_time"] + [f"f{i}" for i in range(len(fields))])
            setattr(app, header_attr, True)

        if use_standard:
            def _val(k):
                v = tick.get(k, "")
                return "" if v is None else v
            row_vals = [time_str] + [_val(k) for k in standard_fields]
            writer.writerow(row_vals)
        else:
            fields = tick.get("fields", [])
            writer.writerow([time_str] + fields)
        file_obj = getattr(app, writer_attr.replace("writer", "file"), None)
        if file_obj:
            file_obj.flush()
    except Exception:
        pass


def write_trade_command(app, command: str, time_str: str, price: Optional[float]) -> None:
    if app.in_backtest or not app.enable_command_output.get():
        return
    app.command_seq += 1
    safe_ts = time_str.replace(" ", "_").replace(":", "").replace("-", "")
    filename = f"cmd_{safe_ts}_{app.command_seq:04d}_{command}.txt"
    path = os.path.join(app.command_dir, filename)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"time={time_str}\n")
            f.write(f"command={command}\n")
            if price is not None:
                f.write(f"price={price:.1f}\n")
        app._log_logic("CMD", f"wrote command file: {filename}")
    except Exception as e:
        try:
            app.status_label.config(text=f"Status: failed to write command file: {e}")
        except Exception:
            pass
