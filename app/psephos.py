import sys
import os

# Allow running as a script: inject repo root so `app` package is importable
if __package__ is None or __package__ == "":
    import pathlib
    ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
    if str(ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(ROOT_DIR))
import csv
import functools
import json
import random
import threading
import time
import math
import platform
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime, time as dtime
import re
from typing import List, Dict, Any, Optional, Tuple

from app.models import TRADING_WINDOWS as MODEL_TRADING_WINDOWS
from core import algorithms, algorithms_strat, mechanisms, persistence, trading
from core.backtest import parse_ticks_from_csv
import executor
from app import data_fetch
import ui_helpers
import analysis
from app import config
from app import controller
from app.trading_time import is_trading_time
try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
    pyautogui.FAILSAFE = True
except Exception:
    PYAUTOGUI_AVAILABLE = False

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import plotting
from ui import test_tab
from ui import relation_tab
from ui import analysis_tab
from ui import order_tab
from tkinter import ttk
from ui import backtest_tab
from ui import strategy_tab
from ui import position_tab
from ui import algo_tab
from ui import contract_tab
from ui import trend_tab
from ui import theme
from ui.tooltip import ToolTip
from ui import app_ui
from ui import lifecycle
from ui import charts


def fetch_nr_tick(symbol: str = "NR2601") -> Dict[str, Any]:
    return data_fetch.fetch_nr_tick(symbol)


def fetch_option_chain(product: str, exchange: str, pinzhong: str, callback: Optional[str] = None) -> Dict[str, Any]:
    return data_fetch.fetch_option_chain(product, exchange, pinzhong, callback=callback)


def fetch_option_quote(symbol: str) -> Dict[str, Any]:
    return data_fetch.fetch_option_quote(symbol)


TRADING_WINDOWS = MODEL_TRADING_WINDOWS


class RealTickApp:
    def __init__(self, root: tk.Tk, symbol: str = config.DEFAULT_SYMBOL_NR, interval: float = config.DEFAULT_INTERVAL_NR) -> None:
        self.root = root
        self.symbol = symbol
        self.interval = interval
        self.data_url_template: str = "https://hq.sinajs.cn/list=nf_{symbol}"
        self.symbol_var = tk.StringVar(value=self.symbol)
        self.url_var = tk.StringVar(value=self.data_url_template)
        self.interval_var = tk.StringVar(value=str(self.interval))
        self.csv_dir_var = tk.StringVar()  # reset later to default
        self.enforce_trading_window: bool = True

        # CL feed defaults (display value without prefix, internal fetch uses hf_)
        self.symbol_cl_display = "CL"
        self.symbol_cl = "hf_CL"
        self.interval_cl = 1.0
        self.data_url_template_cl: str = "https://hq.sinajs.cn/list={symbol}"
        self.symbol_cl_var = tk.StringVar(value=self.symbol_cl_display)
        self.url_cl_var = tk.StringVar(value=self.data_url_template_cl)
        self.interval_cl_var = tk.StringVar(value=str(self.interval_cl))
        self.csv_dir_cl_var = tk.StringVar()
        self.enforce_trading_window_cl: bool = False
        self.option_product_var = tk.StringVar(value="ta")
        self.option_exchange_var = tk.StringVar(value="czce")
        self.option_pinzhong_var = tk.StringVar(value="ta2602")
        self.option_quote_symbol_var = tk.StringVar(value="ta2605C4050")
        self.option_chain_text: Optional[tk.Text] = None
        self.option_quote_text: Optional[tk.Text] = None
        # Theme (light/dark) follows system preference
        self.theme_name = theme.detect_system_theme()
        self.theme = theme.palette_for(self.theme_name)
        theme.set_active_theme(self.theme)
        plotting.apply_theme(self.theme)
        # MACD mode selection: "Tick" (per-tick) or "1m"/"3m"/"5m" bucket closes
        self.macd_mode_var = tk.StringVar(value="1m")
        # streaming redraw throttling
        self.stream_draw_mod = 5
        self._stream_tick_counter = 0
        self._stream_macd_full: Optional[tuple] = None
        self._stream_macd_mode: Optional[str] = None
        self.stream_price_ranges_by_session: Dict[str, tuple] = {}
        self.stream_macd_ranges_by_session: Dict[str, tuple] = {}
        self.stream_price_range_full: Optional[tuple] = None
        self.stream_macd_range_full: Optional[tuple] = None
        self._stream_current_session: Optional[str] = None
        self.atr_window = 14
        self.rsi_window = 14
        self.stoch_window = 14
        self._atr_cache: Dict[Any, Any] = {}
        self._osc_cache: Dict[Any, Any] = {}
        self.price_range_live_fixed: Optional[tuple] = None

        self.show_rsi_on_chart: bool = True

        # OHLC tracking for ATR
        self.chart_highs_live: List[float] = []
        self.chart_lows_live: List[float] = []
        self.chart_closes_live: List[float] = []
        self.chart_highs_bt: List[float] = []
        self.chart_lows_bt: List[float] = []
        self.chart_closes_bt: List[float] = []
        self.chart_highs_stream: List[float] = []
        self.chart_lows_stream: List[float] = []
        self.chart_closes_stream: List[float] = []
        self.chart_highs_cl: List[float] = []
        self.chart_lows_cl: List[float] = []
        self.chart_closes_cl: List[float] = []
        self._prev_close_live: Optional[float] = None
        self._prev_close_stream: Optional[float] = None
        self._prev_close_bt: Optional[float] = None
        self._prev_close_cl: Optional[float] = None
        # Simulation controls
        self.sim_mode_var = tk.BooleanVar(value=True)
        self.sim_speed_var = tk.StringVar(value="2.0")
        self.sim_csv_path_var = tk.StringVar(value="")
        self._sim_ticks: List[tuple] = []
        self._sim_index: int = 0
        self._sim_stop: bool = False
        self.sim_random_var = tk.BooleanVar(value=False)
        # Sim profile knobs
        self.sim_base_price_var = tk.StringVar(value="12000")
        self.sim_atr_var = tk.StringVar(value="50.0")  # approximate ATR for synthetic
        self.sim_jump_prob_var = tk.StringVar(value="0.02")
        self.sim_jump_scale_var = tk.StringVar(value="5.0")
        # Fee toggles
        self.no_close_today_fee_var = tk.BooleanVar(value=True)
        self.no_close_today_fee: bool = True
        self.use_me_macd_atr = tk.BooleanVar(value=False)
        self.use_alt_settlement_var = tk.BooleanVar(value=False)
        self.alt_settlement_enabled = False
        self.alt_settlement_tick_factor = 2.0
        self.alt_settlement_tick_factor_var = tk.StringVar(value=str(self.alt_settlement_tick_factor))
        self.macd_atr_params = {
            "point_value": 10.0,
            "tick_size": config.DEFAULT_TICK_SIZE_NR,
            "risk_per_trade": 0.01,
            "k_SL": 2.0,
            "k_TP": 3.0,
            "atr_min_factor": 0.5,
            "atr_max_factor": 2.0,
            "max_bars_in_trade": 2000,
            "daily_loss_frac": 0.03,
            "atr_window": 20,
            "initial_equity": 19134.0,
        }
        self.macd_atr_state = {
            "equity": self.macd_atr_params["initial_equity"],
            "position": 0,
            "entry_price": None,
            "entry_atr": None,
            "entry_index": None,
            "stop_price": None,
            "tp_price": None,
            "current_day": None,
            "equity_day_start": self.macd_atr_params["initial_equity"],
            "daily_pnl": 0.0,
            "daily_loss_limit": self.macd_atr_params["daily_loss_frac"] * self.macd_atr_params["initial_equity"],
            "no_new_trades": False,
        }
        self.macd_atr_status_var = tk.StringVar(value="--")
        self.macd_atr_pos_var = tk.StringVar(value="Pos: 0")
        self.macd_flip_counts = {key: 0 for key in ("above_bear", "above_bull", "below_bear", "below_bull")}
        self.macd_flip_last_time = {key: None for key in ("above_bear", "above_bull", "below_bear", "below_bull")}
        self._macd_prev_relation = {"live": None, "bt": None, "stream": None}
        self.macd_flip_gap = 4
        self._macd_last_flip_index = {"live": -9999, "bt": -9999, "stream": -9999}
        self.macd_flip_markers_live = {"bear": [], "bull": []}
        self.macd_flip_markers_bt = {"bear": [], "bull": []}
        self.preload_times: List[Any] = []
        self.preload_prices: List[float] = []
        self.preload_macd: Tuple[List[float], List[float], List[float]] = ([], [], [])
        self.preload_fig = None
        self.preload_ax = None
        self.preload_ax_macd = None
        self.preload_canvas = None
        self.preload_source_path: Optional[str] = None
        self.preload_label_var: Optional[tk.StringVar] = None
        self._preload_zoom_cid: Optional[int] = None
        self._preload_pan_press: Optional[float] = None
        self._preload_pan_cid = {"press": None, "motion": None, "release": None}
        self.preload_fixed_xlim: tuple[float, float] | None = None
        self.preload_fixed_ylim: tuple[float, float] | None = None
        self.preload_display_times: List[Any] = []
        self.preload_display_prices: List[float] = []
        self.preload_display_macd: Tuple[List[float], List[float], List[float]] = ([], [], [])
        self.preload_loading: bool = False
        self.preload_spinner_index: int = 0
        self._preload_loading_after: Optional[str] = None
        self.loading_overlay: Optional[ttk.Frame] = None
        self.splash_label_var = tk.StringVar(value="Preparing preload...")
        self.splash_progress: Optional[ttk.Progressbar] = None
        self.preload_crosshair_v = None
        self.preload_crosshair_h = None
        self.preload_crosshair_enabled = False
        self.preload_crosshair_label_var = tk.StringVar(value="Time: -- | Price: --")
        self.preload_tab_active = False
        self._preload_last_xdata: Optional[float] = None
        self._preload_last_price: Optional[float] = None
        self.preload_display_times: List[Any] = []
        self.preload_display_prices: List[float] = []
        self.preload_display_macd: Tuple[List[float], List[float], List[float]] = ([], [], [])

        self.status_window: Optional[tk.Toplevel] = None
        self.status_window_visible: bool = False
        self.status_info_label = None
        self.metrics_labels: List[ttk.Label] = []
        self.status_label: ttk.Label = ttk.Label(self.root)

        self.running = False
        self.running_cl = False

        self.last_price: Optional[float] = None
        self.last_time_str: Optional[str] = None
        self.last_price_cl: Optional[float] = None
        self.last_time_str_cl: Optional[str] = None

        # Track open positions with ownership so mechanisms don't interfere
        self.open_positions: List[dict] = []
        self.settlement: float = 0.0
        self._apply_extra_fee: bool = False
        self.trade_count: int = 0
        self.equity: float = 19134.0
        self.trade_fee_mode: str = "percent"  # "fixed" or "percent"
        self.trade_fee_pct: float = 0.0005    # percent of price per trade when mode=percent
        # Position sizing / margins
        self.order_qty: int = 1
        self.long_pos_size: int = 0
        self.short_pos_size: int = 0
        self.long_init_margin: float = 0.0
        self.short_init_margin: float = 0.0
        # Margin ratios
        self.long_margin_ratio: float = 0.14
        self.short_margin_ratio: float = 0.14

        self.csv_file = None
        self.csv_writer = None
        self.csv_header_written = False
        self.csv_file_cl = None
        self.csv_writer_cl = None
        self.csv_header_written_cl = False

        # data for chart (compressed-time index on x-axis)
        self.chart_times_live: List[datetime] = []
        self.chart_prices_live: List[float] = []
        self.chart_times_bt: List[datetime] = []
        self.chart_prices_bt: List[float] = []
        self.chart_times_stream: List[datetime] = []
        self.chart_prices_stream: List[float] = []
        self.chart_cl_times: List[datetime] = []
        self.chart_cl_prices: List[float] = []
        self.max_points_stream: int = config.DEFAULT_MAX_POINTS_STREAM

        # trade markers: separate lists for open/close & long/short (live)
        self.live_open_long_x: List[int] = []
        self.live_open_long_y: List[float] = []
        self.live_close_long_x: List[int] = []
        self.live_close_long_y: List[float] = []

        self.live_open_short_x: List[int] = []
        self.live_open_short_y: List[float] = []
        self.live_close_short_x: List[int] = []
        self.live_close_short_y: List[float] = []

        # backtest markers
        self.bt_open_long_x: List[int] = []
        self.bt_open_long_y: List[float] = []
        self.bt_close_long_x: List[int] = []
        self.bt_close_long_y: List[float] = []
        self.bt_open_short_x: List[int] = []
        self.bt_open_short_y: List[float] = []
        self.bt_close_short_x: List[int] = []
        self.bt_close_short_y: List[float] = []

        # streaming markers
        self.stream_open_long_x: List[int] = []
        self.stream_open_long_y: List[float] = []
        self.stream_close_long_x: List[int] = []
        self.stream_close_long_y: List[float] = []
        self.stream_open_short_x: List[int] = []
        self.stream_open_short_y: List[float] = []
        self.stream_close_short_x: List[int] = []
        self.stream_close_short_y: List[float] = []

        # P/L vertical lines at close tick: (x, y_open, y_close, color)
        self.pl_lines: List[Tuple[int, float, float, str]] = []  # live only (unused)
        # Holding-period spans colored by profit/loss once closed: (x_start, x_end, color)
        self.live_position_spans: List[Tuple[int, int, str]] = []
        self.bt_position_spans: List[Tuple[int, int, str]] = []
        self.stream_position_spans: List[Tuple[int, int, str]] = []

        # Backtest / automation flags
        self.in_backtest: bool = False
        self.in_streaming: bool = False
        self.suppress_backtest_ui: bool = False
        self._suppress_logic_log: bool = False

        # Contract basics
        self.tick_size: float = config.DEFAULT_TICK_SIZE_NR
        self.leverage: float = config.DEFAULT_LEVERAGE
        # per-trade fee (applies on every open/close)
        self.trade_fee: float = config.DEFAULT_TRADE_FEE

        # Mini backtest chart
        self.fig_bt = None
        self.ax_bt = None
        self.canvas_bt = None
        self.macd_data_rows_max = 300
        self._last_macd_logged_len_live: int = 0
        self._last_macd_logged_len_stream: int = 0

        # Directory for external trade command files (for Windows auto-clicker)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(script_dir)
        self.command_dir = os.path.join(script_dir, "commands")
        os.makedirs(self.command_dir, exist_ok=True)
        self.command_seq: int = 0
        self.max_tick_rows: int = 1000
        # Directory for saving live ticks
        self.csv_dir = os.path.join(root_dir, "data", "NR")
        os.makedirs(self.csv_dir, exist_ok=True)
        self.csv_dir_var.set(self.csv_dir)
        # CL save dir
        self.csv_dir_cl = os.path.join(root_dir, "data", "CL")
        os.makedirs(self.csv_dir_cl, exist_ok=True)
        self.csv_dir_cl_var.set(self.csv_dir_cl)

        # ----- Strategy states & parameters -----
        # Mechanism 1 – History cap (chart)
        self.max_points = 2000

        # Mechanism 1 – Mean reversion to SMA
        self.me1_prices: List[float] = []
        self.me1_prev_dist: Optional[float] = None
        self.me1_window: int = 20
        self.me1_band: float = 20.0      # distance from SMA to open
        self.me1_stop: float = 40.0      # stop-loss distance

        # Mechanism 2 – Inverse mean reversion to SMA (swap long/short of M1)
        self.me2_prices: List[float] = []
        self.me2_prev_dist: Optional[float] = None
        self.me2_window: int = 20
        self.me2_band: float = 20.0
        self.me2_stop: float = 40.0

        # Auto-clicker / command executor state
        self.dry_run = False
        self.human_move = False
        self.jitter_pixels = 5
        self.overshoot_pixels = 8
        self.move_time_range = (0.25, 0.45)
        self.click_hold_range = (0.05, 0.12)
        self.inter_step_delay = (0.06, 0.15)
        self.action_sequences = {
            "OPEN_LONG": [{"type": "click", "pos": "OPEN_LONG_POS", "button": "left"}],
            "OPEN_SHORT": [{"type": "click", "pos": "OPEN_SHORT_POS", "button": "left"}],
            "CLOSE_LONG": [{"type": "click", "pos": "CLOSE_POS", "button": "left"}],
            "CLOSE_SHORT": [{"type": "click", "pos": "CLOSE_POS", "button": "left"}],
        }
        self.order_layouts = {
            "Mac": {
                "open_long_pos": (505, 380),
                "open_short_pos": (646, 380),
                "close_pos": (773, 380),
                "default_cursor_pos": (642, 332),
            },
            "Windows": {
                "open_long_pos": (155, 1065),
                "open_short_pos": (315, 1065),
                "close_pos": (475, 1065),
                "default_cursor_pos": (315, 1019),
            },
            "TV": {},
        }
        self.open_long_pos: Tuple[int, int] = self.order_layouts["Windows"]["open_long_pos"]
        self.open_short_pos: Tuple[int, int] = self.order_layouts["Windows"]["open_short_pos"]
        self.close_pos: Tuple[int, int] = self.order_layouts["Windows"]["close_pos"]
        self.default_cursor_pos: Tuple[int, int] = self.order_layouts["Windows"]["default_cursor_pos"]
        self.order_coord_vars: dict[str, Tuple[tk.StringVar, tk.StringVar]] = {}
        self.order_layout_var: Optional[tk.StringVar] = None
        self.click_thread: Optional[threading.Thread] = None
        self.click_stop_event = threading.Event()

        # Backtest trend tabs storage
        self.bt_mech_notebook: Optional[ttk.Notebook] = None
        self.bt_mech_subtabs: dict = {}
        self.bt_stream_notebook: Optional[ttk.Notebook] = None
        # Streaming chart embedded in Backtest tab
        self.stream_fig = None
        self.stream_ax = None
        self.stream_canvas = None
        # Streaming chart inside Streaming Backtest Trend tab (single tab, reused)
        self.stream_nb_fig = None
        self.stream_nb_ax = None
        self.stream_nb_ax_macd = None
        self.stream_nb_canvas = None
        self.stream_nb_tab = None

        # Quick backtest sampling step (data_point interval)
        self.backtest_step_var = tk.StringVar(value="1")

        # Analysis / relation state
        self.relation_points: List[Tuple[str, float, float]] = []
        self.rel_x_label_var = tk.StringVar(value="X")
        self.rel_y_label_var = tk.StringVar(value="Y")
        self.rel_point_name_var = tk.StringVar(value="")
        self.rel_point_x_var = tk.StringVar(value="")
        self.rel_point_y_var = tk.StringVar(value="")
        self.rel_fig = None
        self.rel_ax = None
        self.rel_canvas = None

        # MACD data viewer
        self.macd_tree = None
        self.macd_data_rows_max = 300
        self._last_macd_logged_len_live: int = 0
        self._last_macd_logged_len_stream: int = 0

        # M4 MACD mode
        self.use_me4 = tk.BooleanVar(value=False)
        self.m4_use_take_profit = tk.BooleanVar(value=False)
        self.m4_use_stop_loss = tk.BooleanVar(value=False)
        self.m4_params = {
            "ensure_window": 3,
            "take_profit": 600.0,
            "stop_loss": -100.0,
        }
        self.m4_state = {
            "mode": "observation",
            "counter": 0,
            "hold_counter": 0,
            "obs_pos": 0,
            "obs_neg": 0,
        }

        # Sim P&L per mechanism
        self.sim_states = {
            "M3": {"positions": [], "settlement": 0.0, "prices": [], "prev_dist": None, "hold": 0},
            "M8": {"positions": [], "settlement": 0.0, "prices": [], "prev_dist": None, "hold": 0},
        }

        # Editable formulas (strings for reference/documentation)
        self.me1_formula: str = (
            "Inputs: window=N, band=D, stop=S.\n"
            "SMA_t = avg(price[t-N+1..t]); dist = price_t - SMA_t.\n"
            "Entry: open long if dist < -D and prev_dist >= -D; open short if dist > D and prev_dist <= D.\n"
            "Exit: long when price_t >= SMA_t or price_t <= entry - S; "
            "short when price_t <= SMA_t or price_t >= entry + S."
        )
        self.me2_formula: str = (
            "Inputs: window=N, band=D, stop=S.\n"
            "SMA_t = avg(price[t-N+1..t]); dist = price_t - SMA_t.\n"
            "Entry: open SHORT if dist < -D and prev_dist >= -D; open LONG if dist > D and prev_dist <= D.\n"
            "Exit: SHORT when price_t >= SMA_t or price_t <= entry - S; "
            "LONG when price_t <= SMA_t or price_t >= entry + S."
        )
        # expose tooltip class to UI builders
        self.tooltip_cls = ToolTip
        self._build_ui()
        self.root.bind("<space>", self._toggle_status_window)
        self.fullscreen = False
        self.root.bind("<F11>", self._toggle_fullscreen)
        self.root.bind("<Escape>", lambda e: self._exit_fullscreen() if self.fullscreen else None)
        self._center_window()
        lifecycle.start_clock_loop(self, is_trading_time)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        # Order watcher is opt-in to avoid accidental clicks from stale files
        # cache for MACD series keyed by id(times)
        self._cached_macd = {}
        self._macd_cache = {}
        # Async fetch guards (prevent overlapping network calls)
        self._nr_fetch_inflight: bool = False
        self._cl_fetch_inflight: bool = False

    def _set_status_text(self, text: str) -> None:
        """Thread-safe helper to update the status bar from any thread."""
        def _update():
            try:
                self.status_label.config(text=text)
            except Exception:
                pass

        try:
            if threading.current_thread() is threading.main_thread():
                _update()
            else:
                self.root.after(0, _update)
        except Exception:
            pass

    def _sma(self, values: List[float]) -> float:
        return algorithms.sma(values)

    def _atr(self, values: List[float]) -> float:
        """Average true range using consecutive absolute differences."""
        return algorithms.atr(values)

    def _build_algo_tab(self, notebook: ttk.Notebook, title: str,
                        fields: List[Tuple[str, str, type]], formula_attr: str,
                        state_vars: List[str]) -> None:
        """
        Thin wrapper to build an algorithm sub-tab using the shared helper in ui.algo_tab.
        """
        from ui import algo_tab  # local import to avoid cycles
        algo_tab.build_algo_subtab(self, notebook, title, fields, formula_attr, state_vars)


    # ----- Auto clicker helpers -----

    def _parse_command_file(self, path: str) -> Optional[dict]:
        return executor.parse_command_file(path)

    def _jitter_point(self, pos: Tuple[int, int], radius: int) -> Tuple[int, int]:
        return executor.jitter_point(pos, radius)

    def _move_and_click(self, pos: Tuple[int, int]) -> None:
        return executor.move_and_click(self, pos)

    def _human_move_and_click(self, pos: Tuple[int, int], button: str = "left") -> None:
        return executor.human_move_and_click(self, pos, button)

    def _resolve_pos(self, name: str) -> Optional[Tuple[int, int]]:
        return executor.resolve_pos(self, name)

    def _refresh_order_coord_vars(self) -> None:
        vars_map = getattr(self, "order_coord_vars", {})
        for attr, var_pair in vars_map.items():
            coords = getattr(self, attr, None)
            if coords is None:
                continue
            varx, vary = var_pair
            try:
                varx.set(str(int(coords[0])))
                vary.set(str(int(coords[1])))
            except Exception:
                varx.set(str(coords[0]))
                vary.set(str(coords[1]))

    def apply_order_layout(self, layout_name: str) -> None:
        layout = getattr(self, "order_layouts", {}).get(layout_name)
        if not layout:
            return
        for attr, coords in layout.items():
            if coords is None:
                continue
            setattr(self, attr, coords)
        self._refresh_order_coord_vars()

    def _execute_command_click(self, cmd_name: str) -> None:
        return executor.execute_command_click(self, cmd_name)

    def _watch_commands_loop(self) -> None:
        return executor.watch_commands_loop(self)

    def start_autoclicker(self) -> None:
        if self.click_thread and self.click_thread.is_alive():
            self.status_label.config(text="Status: auto-clicker already running")
            return
        if not PYAUTOGUI_AVAILABLE:
            messagebox.showerror("PyAutoGUI missing", "pyautogui is required for auto-clicker.")
            return
        self.click_stop_event.clear()
        self.click_thread = threading.Thread(target=self._watch_commands_loop, daemon=True)
        self.click_thread.start()
        self.status_label.config(text="Status: Order running")

    def stop_autoclicker(self) -> None:
        self.click_stop_event.set()
        if self.click_thread:
            self.click_thread.join(timeout=1.0)
        self.status_label.config(text="Status: Order stopped")

    def _fetch_tick_for(self, symbol: str, url_template: str) -> Optional[Dict[str, Any]]:
        return data_fetch.fetch_tick_for(symbol, url_template)

    def _fetch_tick(self) -> Optional[Dict[str, Any]]:
        return self._fetch_tick_for(self.symbol, self.data_url_template)

    def _write_option_text(self, widget: Optional[tk.Text], content: str) -> None:
        if widget is None:
            return
        widget.config(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, content)
        widget.config(state=tk.DISABLED)

    def _fetch_option_chain(self) -> None:
        product = self.option_product_var.get().strip()
        exchange = self.option_exchange_var.get().strip()
        pinzhong = self.option_pinzhong_var.get().strip()
        if not (product and exchange and pinzhong):
            messagebox.showerror("Options", "Product, exchange, and pinzhong are required.")
            return
        try:
            data = fetch_option_chain(product, exchange, pinzhong)
            body = json.dumps(data.get("result", data), ensure_ascii=False, indent=2)
            self._write_option_text(self.option_chain_text, body)
        except Exception as exc:
            messagebox.showerror("Option Chain", f"Failed to fetch option chain:\n{exc}")

    def _fetch_option_quote(self) -> None:
        symbol = self.option_quote_symbol_var.get().strip()
        if not symbol:
            messagebox.showerror("Options", "Option symbol is required.")
            return
        try:
            data = fetch_option_quote(symbol)
            body = json.dumps(data, ensure_ascii=False, indent=2)
            self._write_option_text(self.option_quote_text, body)
        except Exception as exc:
            messagebox.showerror("Option Quote", f"Failed to fetch option quote:\n{exc}")

    def _build_ui(self) -> None:
        app_ui.build_ui(self)

    # ----- Mechanism 4: MACD Mode -----
    def _mechanism4_macd_mode_logic(self) -> None:
        mechanisms.mechanism4_macd_mode_logic(self)

    def _center_window(self) -> None:
        self.root.withdraw()
        self.root.update_idletasks()

        desired_w = 1700
        desired_h = 1100
        if platform.system() == "Windows":
            desired_w = 1100
            desired_h = 750

        self.root.minsize(desired_w, desired_h)
        w = desired_w
        h = desired_h

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()

        x = (sw - w) // 2
        y = (sh - h) // 2

        self.root.geometry(f"{w}x{h}+{x}+{y}")
        try:
            self.root.attributes("-topmost", True)
        except Exception:
            pass
        self.root.deiconify()

    # ----- internal clock loop (1 second) -----

    def _with_topmost_suspended(self, fn):
        return lifecycle.with_topmost_suspended(self, fn)

    def _refresh_status(self) -> None:
        symbol = getattr(self, "symbol", "")
        mech_active = []
        if getattr(self, "use_me3", None) and self.use_me3.get():
            mech_active.append("M1")
        if getattr(self, "use_me8", None) and self.use_me8.get():
            mech_active.append("M2")
        if getattr(self, "use_me_macd_atr", None) and self.use_me_macd_atr.get():
            mech_active.append("M3")
        if getattr(self, "use_me4", None) and self.use_me4.get():
            mech_active.append("M4")
        mech_str = ",".join(mech_active) if mech_active else "None"

        data_state = "running" if getattr(self, "running", False) else "stopped"
        if not getattr(self, "running", False) and not is_trading_time():
            data_state = "waiting"

        cl_state = "stopped"
        if getattr(self, "running_cl", False):
            cl_state = "running"
        else:
            # respect trading window for CL if enabled
            try:
                if not getattr(self, "enforce_trading_window_cl", False) or is_trading_time():
                    cl_state = "stopped"
                else:
                    cl_state = "waiting"
            except Exception:
                cl_state = "stopped"
        cl_symbol = getattr(self, "symbol_cl_display", "CL")

        order_on = (
            getattr(self, "click_thread", None) is not None
            and self.click_thread.is_alive()
            and getattr(self, "enable_command_output", None)
            and self.enable_command_output.get()
        )
        order_str = "on" if order_on else "off"

        net = getattr(self, "settlement", 0.0)
        equity_val = getattr(self, "equity", 0.0)
        total_fee = getattr(self, "total_fees", 0.0)
        long_size = getattr(self, "long_pos_size", 0)
        short_size = getattr(self, "short_pos_size", 0)
        total_size = abs(long_size - short_size)
        used_margin = abs(long_size * getattr(self, "long_init_margin", 0.0) - short_size * getattr(self, "short_init_margin", 0.0))
        available_margin = equity_val - used_margin
        used_margin_ratio = (used_margin / equity_val * 100.0) if equity_val else 0.0
        ote_val = self._compute_ote()
        self.status_label.config(
            text=(
                f"Contract (NR): {symbol} [{data_state}] | "
                f"Mechanisms: {mech_str} | Execute orders: {order_str}"
            )
        )
        info_parts = [
            f"Equity: {equity_val:.2f}",
            f"OTE: {ote_val:.2f}",
            f"Used margin: {used_margin:.2f}",
            f"Available margin: {available_margin:.2f}",
            f"Used margin ratio: {used_margin_ratio:.2f}%",
        ]
        if not (self.in_backtest and not self.in_streaming):
            info_parts.extend([f"Net: {net:.2f}", f"Fees: {total_fee:.2f}"])
        info_parts.extend([f"Total size: {total_size}", f"Long size: {long_size}", f"Short size: {short_size}"])
        groups = [
            info_parts[:5],
            info_parts[5:8],
            info_parts[8:],
        ]
        for idx, group in enumerate(groups):
            if idx < len(getattr(self, "metrics_labels", [])):
                self.metrics_labels[idx].config(text=" | ".join(group))
        flip_texts = []
        for key in ("above_bear", "above_bull", "below_bear", "below_bull"):
            count = self.macd_flip_counts.get(key, 0)
            t = self.macd_flip_last_time.get(key) or "--"
            flip_texts.append(f"{key.replace('_', ' ').title()}: {count}@{t}")
        if self.status_info_label:
            self.status_info_label.config(text=" | ".join(flip_texts))
        for mech, lbl in self.sim_labels.items():
            state = self.sim_states.get(mech, {})
            lbl.config(text=f"{mech}: {state.get('settlement', 0.0):.2f}")

        # update MACD data viewer latest row if present
        try:
            self._log_macd_row(self.chart_times_live, self.chart_prices_live, context="live")
        except Exception:
            pass

    def _toggle_alt_settlement(self) -> None:
        self.alt_settlement_enabled = bool(self.use_alt_settlement_var.get())
        try:
            self._refresh_status()
        except Exception:
            pass

    def _create_status_window(self) -> None:
        if self.status_window is not None and getattr(self.status_window, "winfo_exists", lambda: False)():
            return
        win = tk.Toplevel(self.root)
        win.title("Status Info")
        win.transient(self.root)
        try:
            win.attributes("-topmost", True)
        except Exception:
            pass
        win.protocol("WM_DELETE_WINDOW", self._hide_status_window)
        win.columnconfigure(0, weight=1)

        header_frame = ttk.Frame(win)
        header_frame.grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 2))
        status_label = ttk.Label(header_frame, text="Status: initial", anchor="w")
        status_label.pack(side=tk.LEFT, anchor="w")
        clock_label = ttk.Label(header_frame, text="Time: --:--:--", anchor="w")
        clock_label.pack(side=tk.RIGHT, anchor="e")

        metrics_frame = ttk.Frame(win)
        metrics_frame.grid(row=1, column=0, sticky="ew", padx=12)
        self.metrics_labels = []
        for i in range(3):
            lbl = ttk.Label(metrics_frame, text="", anchor="w", justify=tk.LEFT)
            lbl.grid(row=i, column=0, sticky="ew", pady=2)
            self.metrics_labels.append(lbl)

        flip_frame = ttk.LabelFrame(win, text="Trend flips")
        flip_frame.grid(row=2, column=0, sticky="ew", padx=12, pady=(4, 8))
        self.status_info_label = ttk.Label(flip_frame, text="Bear flips: 0 | Bull flips: 0", anchor="w", justify=tk.LEFT)
        self.status_info_label.pack(fill=tk.X, padx=8, pady=4)

        win.withdraw()
        self.status_window = win
        self.status_label = status_label
        self.clock_label = clock_label
        self.status_window_visible = False

    def _hide_status_window(self) -> None:
        if self.status_window is None:
            return
        try:
            self.status_window.withdraw()
        except Exception:
            pass
        self.status_window_visible = False

    def _toggle_status_window(self, event=None) -> None:
        if event is not None:
            focus_widget = self.root.focus_get()
            if focus_widget is None or focus_widget.winfo_toplevel() != self.root:
                return
        if self.status_window is None or not getattr(self.status_window, "winfo_exists", lambda: False)():
            self._create_status_window()
        if self.status_window_visible:
            self._hide_status_window()
        else:
            try:
                self.status_window.deiconify()
            except Exception:
                pass
            self.status_window_visible = True
            try:
                self.root.focus_force()
            except Exception:
                pass

    def _toggle_rsi_overlay(self) -> None:
        self.show_rsi_on_chart = not getattr(self, "show_rsi_on_chart", True)
        text = "Hide RSI overlay" if self.show_rsi_on_chart else "Show RSI overlay"
        btn = getattr(self, "rsi_toggle_button", None)
        if btn is not None:
            try:
                btn.config(text=text)
            except Exception:
                pass
        if hasattr(self, "_refresh_macd_mode"):
            try:
                self._refresh_macd_mode()
            except Exception:
                pass

    def _toggle_fullscreen(self, event=None) -> None:
        self.fullscreen = not getattr(self, "fullscreen", False)
        try:
            self.root.attributes("-fullscreen", self.fullscreen)
        except Exception:
            pass
        self.root.update_idletasks()

    def _exit_fullscreen(self) -> None:
        if not getattr(self, "fullscreen", False):
            return
        self.fullscreen = False
        try:
            self.root.attributes("-fullscreen", False)
        except Exception:
            pass
        self.root.update_idletasks()

    def _compute_ote(self) -> float:
        """
        Compute Open Trade Equity based on current price and open positions.
        Long OTE: (last_price - avg_entry_long) * long_qty * contract_multiplier
        Short OTE: (avg_entry_short - last_price) * short_qty * contract_multiplier
        """
        if self.last_price is None:
            return 0.0
        # contract multiplier is stored in leverage field per contract info
        try:
            contract_multiplier = float(getattr(self, "leverage", 1.0))
        except Exception:
            contract_multiplier = 1.0
        long_qty = 0
        long_cost = 0.0
        short_qty = 0
        short_cost = 0.0
        for pos in self.open_positions:
            qty = pos.get("qty", 1)
            if pos.get("side") == "long":
                long_qty += qty
                long_cost += qty * pos.get("open_price", 0.0)
            elif pos.get("side") == "short":
                short_qty += qty
                short_cost += qty * pos.get("open_price", 0.0)
        long_ote = 0.0
        short_ote = 0.0
        if long_qty > 0:
            avg_long = long_cost / long_qty
            long_ote = (self.last_price - avg_long) * long_qty * contract_multiplier
        if short_qty > 0:
            avg_short = short_cost / short_qty
            short_ote = (avg_short - self.last_price) * short_qty * contract_multiplier
        return long_ote + short_ote

    def _log_macd_row(self, times: List[Any], prices: List[float], context: str = "live") -> None:
        """
        Append the latest MACD values (per current MACD TF) to the MACD data tree.
        Context: 'live' or 'stream'.
        """
        if self.macd_tree is None:
            return
        if not times or not prices:
            return
        idx = len(prices) - 1
        last_len_attr = "_last_macd_logged_len_stream" if context == "stream" else "_last_macd_logged_len_live"
        last_key_attr = "_last_macd_logged_key_stream" if context == "stream" else "_last_macd_logged_key_live"
        last_len = getattr(self, last_len_attr, -1)
        last_key = getattr(self, last_key_attr, None)
        current_key = times[-1]
        # If we've already logged this timestamp, skip
        if last_key is not None and current_key == last_key:
            return
        macd_hist, dif, dea = self._macd_series_for(times, prices)
        if not dif or not dea or idx >= len(dif) or idx >= len(dea):
            return
        hist_val = macd_hist[idx] if macd_hist and idx < len(macd_hist) else None
        dif_val = dif[idx]
        dea_val = dea[idx]
        atr_val = None
        try:
            atrs = self._atr_series_for(times, prices)
            if atrs and idx < len(atrs):
                atr_val = atrs[idx]
                if isinstance(atr_val, float) and math.isnan(atr_val):
                    atr_val = None
        except Exception:
            atr_val = None
        t_val = times[idx]
        t_str = t_val.strftime("%Y-%m-%d %H:%M:%S") if isinstance(t_val, datetime) else str(t_val)
        price_val = prices[idx]
        vol_str = ""
        if atr_val is not None and price_val:
            try:
                vol_pct = (atr_val / price_val) * 100
                vol_str = f"{vol_pct:.2f}%"
            except Exception:
                vol_str = ""
        highs, lows, closes = self._ohlc_for_context(context)
        rsi_vals = self._rsi_series_for(closes, self.rsi_window)
        stoch_vals = self._stoch_series_for(highs, lows, closes, self.stoch_window)
        rsi_val = rsi_vals[idx] if idx < len(rsi_vals) else None
        stoch_val = stoch_vals[idx] if idx < len(stoch_vals) else None
        rsi_str = "" if rsi_val is None else f"{rsi_val:.2f}"
        stoch_str = "" if stoch_val is None else f"{stoch_val:.2f}"
        row = (
            t_str,
            f"{price_val:.4f}",
            f"{dif_val:.4f}",
            f"{dea_val:.4f}",
            "" if hist_val is None else f"{hist_val:.4f}",
            "" if atr_val is None else f"{atr_val:.4f}",
            vol_str,
            rsi_str,
            stoch_str,
        )
        self._track_macd_relation(idx, t_str, dif_val, dea_val, context=context, hist_val=hist_val)
        try:
            self.macd_tree.insert("", tk.END, values=row)
            children = self.macd_tree.get_children()
            if len(children) > self.macd_data_rows_max:
                self.macd_tree.delete(*children[: len(children) - self.macd_data_rows_max])
            # auto-scroll to latest
            self.macd_tree.yview_moveto(1.0)
            setattr(self, last_len_attr, len(prices))
            setattr(self, last_key_attr, current_key)
        except Exception:
            pass

    def _macd_relation_state(self, dif_val: float, dea_val: float) -> Optional[str]:
        if dif_val > 0 and dea_val > 0:
            if dif_val > dea_val:
                return "above_dif_gt_dea"
            if dea_val > dif_val:
                return "above_dea_gt_dif"
        if dif_val < 0 and dea_val < 0:
            if dea_val < dif_val:
                return "below_dea_lt_dif"
            if dif_val < dea_val:
                return "below_dif_lt_dea"
        return None

    def _track_macd_relation(self, idx: int, t_str: str, dif_val: float | None, dea_val: float | None, context: str = "live", hist_val: float | None = None) -> None:
        if dif_val is None or dea_val is None:
            self._macd_prev_relation[context] = None
            return
        curr_state = self._macd_relation_state(dif_val, dea_val)
        prev_state = self._macd_prev_relation.get(context)
        transitions = {
            ("above_dif_gt_dea", "above_dea_gt_dif"): "above_bear",
            ("above_dea_gt_dif", "above_dif_gt_dea"): "above_bull",
            ("below_dea_lt_dif", "below_dif_lt_dea"): "below_bear",
            ("below_dif_lt_dea", "below_dea_lt_dif"): "below_bull",
        }
        if prev_state and curr_state:
            key = transitions.get((prev_state, curr_state))
            if key:
                gap = getattr(self, "macd_flip_gap", 0)
                last_idx = self._macd_last_flip_index.get(context, -9999)
                if idx - last_idx >= gap:
                    self.macd_flip_counts[key] += 1
                    self.macd_flip_last_time[key] = t_str
                    label_text = key.split("_")
                    label_text = "".join(part[0].upper() for part in label_text)
                    side = "bear" if "bear" in key else "bull"
                    y_val = (dif_val + dea_val) / 2
                    self._record_macd_flip_marker(idx, y_val, side, context, label_text)
                    self._macd_last_flip_index[context] = idx
        self._macd_prev_relation[context] = curr_state

    def _macd_flip_marker_set(self, context: str) -> Optional[dict]:
        if context == "live":
            return getattr(self, "macd_flip_markers_live", None)
        if context == "bt":
            return getattr(self, "macd_flip_markers_bt", None)
        return None

    def _record_macd_flip_marker(self, idx: int, value: float, side: str, context: str, label_text: str) -> None:
        markers = self._macd_flip_marker_set(context)
        if markers is None or side not in markers:
            return
        marks = markers[side]
        for existing_idx, existing_value, _ in marks:
            if existing_idx == idx and abs(existing_value - value) < 1e-9:
                return
        marks.append((idx, value, label_text))

    # ----- CSV handling for live logging -----

    def _open_csv(self) -> None:
        persistence.open_csv(self)

    def _write_csv_tick(self, time_str: str, tick: Dict[str, Any]) -> None:
        persistence.write_csv_tick(self, time_str, tick)

    def _write_csv_tick_cl(self, time_str: str, tick: Dict[str, Any]) -> None:
        persistence.write_csv_tick_cl(self, time_str, tick)

    def _write_csv_tick_generic(self, writer_attr: str, header_attr: str, time_str: str, tick: Dict[str, Any]) -> None:
        persistence.write_csv_tick_generic(self, writer_attr, header_attr, time_str, tick)

    def _open_csv_cl(self) -> None:
        persistence.open_csv_cl(self)

    def _close_csv_cl(self) -> None:
        persistence.close_csv_cl(self)

    def _close_csv(self) -> None:
        persistence.close_csv(self)

    # ----- Strategy logic logging -----

    def _log_logic(self, mechanism: str, message: str) -> None:
        if self._suppress_logic_log:
            return
        if self.last_time_str is not None:
            t_str = self.last_time_str
        else:
            t_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Attach price and fee breakdown
        price = self.last_price
        fee_str = ""
        if price is not None:
            fee_val = trading.calc_trade_fee(self, price)
            if getattr(self, "trade_fee_mode", "fixed") == "percent":
                fee_str = f" | fee={fee_val:.2f} ({self.trade_fee_pct}% of {price:.2f})"
            else:
                fee_str = f" | fee={fee_val:.2f} (fixed)"
            message = f"{message} | price={price:.2f}{fee_str}"
        display_time = ui_helpers.logic_time_display(t_str)
        self.logic_tree.insert("", tk.END, values=(display_time, mechanism, message))
        self.logic_tree.yview_moveto(1.0)

    # ----- External trade command writing (for auto-trading on Windows) -----

    def _write_trade_command(self, command: str, time_str: str, price: Optional[float]) -> None:
        persistence.write_trade_command(self, command, time_str, price)

    # ----- Chart & trade markers -----

    def _active_series(self):
        if self.in_streaming:
            return self.chart_times_stream, self.chart_prices_stream
        if self.in_backtest:
            return self.chart_times_bt, self.chart_prices_bt
        return self.chart_times_live, self.chart_prices_live

    def _compute_macd_series(self, prices: List[float]) -> Tuple[List[float], List[float], List[float]]:
        """Return (macd_hist, dif, dea) lists using EMA12/EMA26 and signal=9."""
        return algorithms.compute_macd_series(prices)

    def _macd_series_for(self, times: List[Any], prices: List[float]) -> Tuple[List[float], List[float], List[float]]:
        """Select MACD timeframe based on user choice."""
        mode = (self.macd_mode_var.get() or "5m").lower()
        if self.in_streaming and getattr(self, "_stream_macd_full", None) is not None:
            if getattr(self, "_stream_macd_mode", None) == mode:
                macd_hist, dif, dea = self._stream_macd_full
                n = len(prices)
                total_processed = None
                try:
                    if getattr(self, "_stream_index", None) is not None:
                        total_processed = getattr(self, "_stream_index") + 1
                    if getattr(self, "_stream_ticks", None) is not None:
                        total_processed = min(total_processed or len(self._stream_ticks), len(self._stream_ticks))
                except Exception:
                    total_processed = None
                if total_processed is None:
                    total_processed = n
                start = max(0, total_processed - n)
                end = start + n
                macd_hist = list(macd_hist[start:end]) if macd_hist is not None else []
                dif = list(dif[start:end]) if dif is not None else []
                dea = list(dea[start:end]) if dea is not None else []
                return macd_hist or [], dif or [], dea or []
        key = (id(times), len(prices), mode)
        cached = self._macd_cache.get(key)
        if cached is not None:
            return cached
        res = algorithms.macd_series_for(mode, times, prices)
        try:
            self._macd_cache[key] = res
        except Exception:
            pass
        return res

    def _preload_csv_paths(self) -> List[str]:
        date_re = re.compile(r"(0[1-9]|1[0-2])([0-3]\d)(20\d{2})")
        candidates: List[tuple[datetime, str]] = []
        try:
            root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            out_dir = self.csv_dir or os.path.join(root_dir, "data", "NR")
            if not os.path.isdir(out_dir):
                return []
            for fn in os.listdir(out_dir):
                if not fn.lower().endswith(".csv"):
                    continue
                match = date_re.search(fn)
                if not match:
                    continue
                mm, dd, yyyy = match.groups()
                try:
                    ts = datetime(int(yyyy), int(mm), int(dd))
                except ValueError:
                    continue
                p = os.path.join(out_dir, fn)
                candidates.append((ts, p))
        except Exception:
            return []
        if not candidates:
            return []
        candidates.sort(key=lambda tup: tup[0], reverse=True)
        return [candidates[0][1]]

    def _ensure_loading_overlay(self) -> None:
        if self.loading_overlay is not None and getattr(self.loading_overlay, "winfo_exists", lambda: False)():
            return
        overlay = ttk.Frame(self.root, style="LoadingOverlay.TFrame")
        label = ttk.Label(overlay, textvariable=self.splash_label_var, font=("", 12))
        label.pack(expand=True)
        self.splash_progress = ttk.Progressbar(overlay, mode="indeterminate")
        self.splash_progress.pack(fill=tk.X, padx=16, pady=8)
        self.loading_overlay = overlay

    def _show_splash(self) -> None:
        self._ensure_loading_overlay()
        if self.loading_overlay is None:
            return
        self.root.update_idletasks()
        self.loading_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.loading_overlay.lift()
        self.splash_progress.start(80)

    def _hide_splash(self) -> None:
        if self.splash_progress is not None:
            try:
                self.splash_progress.stop()
            except Exception:
                pass
        if self.loading_overlay is not None:
            self.loading_overlay.place_forget()
        self.loading_overlay = None

    def load_preload_series(self) -> None:
        if getattr(self, "preload_loading", False):
            return
        self.preload_loading = True
        self.preload_spinner_index = 0
        self._update_preload_loading_ui()
        self._show_splash()
        threading.Thread(target=self._preload_worker, daemon=True).start()

    def _preload_worker(self) -> None:
        paths = self._preload_csv_paths()
        ticks: List[tuple] = []
        for path in paths:
            try:
                ticks.extend(parse_ticks_from_csv(path))
            except Exception:
                continue
        self.root.after(0, lambda: self._on_preload_loaded(paths, ticks))

    def _on_preload_loaded(self, paths: List[str], ticks: List[tuple]) -> None:
        self.preload_loading = False
        if self._preload_loading_after is not None:
            try:
                self.root.after_cancel(self._preload_loading_after)
            except Exception:
                pass
            self._preload_loading_after = None
        self.preload_source_path = paths[0] if paths else None
        self.preload_times = [t[0] for t in ticks]
        self.preload_prices = [t[1] for t in ticks]
        macd_hist, dif, dea = self._macd_series_for(self.preload_times, self.preload_prices)
        self.preload_macd = (macd_hist, dif, dea)
        length = len(self.preload_prices)
        if length < 2:
            self.preload_display_times = self.preload_times
            self.preload_display_prices = self.preload_prices
            self.preload_display_macd = self.preload_macd
        else:
            step = max(1, math.ceil(length / 1600))
            indices = list(range(0, length, step))
            if indices[-1] != length - 1:
                indices.append(length - 1)
            self.preload_display_times = [self.preload_times[i] for i in indices]
            self.preload_display_prices = [self.preload_prices[i] for i in indices]
            self.preload_display_macd = (
                [macd_hist[i] for i in indices],
                [dif[i] for i in indices],
                [dea[i] for i in indices],
            )
        if self.preload_display_times:
            self.preload_fixed_xlim = (0, len(self.preload_display_times) - 1)
        if self.preload_display_prices:
            mx = max(self.preload_display_prices)
            mn = min(self.preload_display_prices)
            pad = (mx - mn) * 0.02 if mx != mn else max(0.5, abs(mx) * 0.02)
            self.preload_fixed_ylim = (mn - pad, mx + pad)
        self.draw_preload_chart()
        self._update_preload_loading_ui()
        self._hide_splash()

    def _update_preload_loading_ui(self) -> None:
        if self.preload_loading:
            spinner = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
            self.preload_spinner_index = (self.preload_spinner_index + 1) % len(spinner)
            if self.preload_label_var is not None:
                self.preload_label_var.set(f"{spinner[self.preload_spinner_index]} Loading preload data...")
            if hasattr(self, "preload_progressbar") and self.preload_progressbar is not None:
                try:
                    self.preload_progressbar.start(60)
                except Exception:
                    pass
            self._preload_loading_after = self.root.after(120, self._update_preload_loading_ui)
        else:
            if hasattr(self, "preload_progressbar") and self.preload_progressbar is not None:
                try:
                    self.preload_progressbar.stop()
                except Exception:
                    pass

    def draw_preload_chart(self) -> None:
        if not self.preload_fig or self.preload_ax is None or self.preload_ax_macd is None or self.preload_canvas is None:
            return
        plotting.draw_price_macd(
            self.preload_ax,
            self.preload_ax_macd,
            self.preload_display_times,
            self.preload_display_prices,
            title="Preloaded Trend",
            y_label="Price",
            macd_data=self.preload_display_macd,
        )
        if self.preload_label_var is not None:
            if self.preload_source_path:
                basename = os.path.basename(self.preload_source_path)
                self.preload_label_var.set(f"Preloaded from {basename} ({len(self.preload_prices)} ticks)")
            else:
                self.preload_label_var.set("Preloaded data: none available")
        if self.preload_fixed_xlim is not None:
            self.preload_ax.set_xlim(*self.preload_fixed_xlim)
            self.preload_ax_macd.set_xlim(*self.preload_fixed_xlim)
        if self.preload_fixed_ylim is not None:
            self.preload_ax.set_ylim(*self.preload_fixed_ylim)
            self.preload_ax.set_autoscale_on(False)
            self.preload_ax_macd.set_autoscale_on(False)
        self.preload_canvas.draw_idle()

    def _zoom_preload_chart(self, event) -> None:
        if self.preload_ax is None or self.preload_ax_macd is None or not getattr(self, "preload_tab_active", False):
            return
        if not self.preload_times:
            return
        if event.step is not None:
            factor = 1 / 1.2 if event.step > 0 else 1.2
        else:
            factor = 1 / 1.2 if getattr(event, "button", "") == "up" else 1.2
        xdata = event.xdata if event.xdata is not None else sum(self.preload_ax.get_xlim()) / 2
        cur_xlim = self.preload_ax.get_xlim()
        new_left = xdata - (xdata - cur_xlim[0]) * factor
        new_right = xdata + (cur_xlim[1] - xdata) * factor
        self.preload_ax.set_xlim(new_left, new_right)
        self.preload_ax_macd.set_xlim(new_left, new_right)
        self.preload_canvas.draw_idle()

    def _zoom_preload_by(self, factor: float) -> None:
        if self.preload_ax is None or self.preload_ax_macd is None:
            return
        if not getattr(self, "preload_tab_active", False):
            return
        cur_xlim = self.preload_ax.get_xlim()
        center = (cur_xlim[0] + cur_xlim[1]) / 2
        half_span = (cur_xlim[1] - cur_xlim[0]) / 2 * factor
        new_left = center - half_span
        new_right = center + half_span
        self.preload_ax.set_xlim(new_left, new_right)
        self.preload_ax_macd.set_xlim(new_left, new_right)
        if self.preload_canvas:
            self.preload_canvas.draw_idle()

    def _zoom_preload_shortcut(self, factor: float, event) -> str:
        self._zoom_preload_by(factor)
        return "break"

    def _pan_preload_start(self, event) -> None:
        if not getattr(self, "preload_tab_active", False):
            return
        if event.inaxes != self.preload_ax:
            return
        if getattr(event, "button", None) != 3:
            return
        self._preload_pan_press = event.xdata

    def _pan_preload_motion(self, event) -> None:
        if self._preload_pan_press is None or not self.preload_ax:
            return
        if event.xdata is None:
            return
        delta = self._preload_pan_press - event.xdata
        if abs(delta) < 1e-6:
            return
        cur_xlim = self.preload_ax.get_xlim()
        new_left = cur_xlim[0] + delta
        new_right = cur_xlim[1] + delta
        self.preload_ax.set_xlim(new_left, new_right)
        self.preload_ax_macd.set_xlim(new_left, new_right)
        self.preload_canvas.draw_idle()
        self._preload_pan_press = event.xdata

    def _pan_preload_end(self, event) -> None:
        self._preload_pan_press = None

    def _update_preload_crosshair(self, event) -> None:
        if not getattr(self, "preload_tab_active", False):
            return
        if event.inaxes not in (self.preload_ax, self.preload_ax_macd):
            return
        if not getattr(self, "preload_crosshair_enabled", False):
            return
        if not self.preload_display_times:
            return
        xdata = event.xdata
        ydata = event.ydata
        if xdata is None and event.inaxes is not None and event.x is not None and event.y is not None:
            inv = event.inaxes.transData.inverted()
            xdata, ydata = inv.transform((event.x, event.y))
        if xdata is None:
            xdata = self._preload_last_xdata
        if xdata is None:
            return
        self._preload_last_xdata = xdata
        idx_floor = max(0, min(int(math.floor(xdata)), len(self.preload_display_times) - 1))
        idx_ceil = max(0, min(int(math.ceil(xdata)), len(self.preload_display_times) - 1))
        if event.inaxes == self.preload_ax and ydata is not None:
            price = ydata
            self._preload_last_price = price
        else:
            price = self._preload_last_price if self._preload_last_price is not None else self.preload_display_prices[idx_floor]
        if self.preload_crosshair_v is None:
            self.preload_crosshair_v = self.preload_ax.axvline(xdata, color="#888", linestyle="--", linewidth=0.8)
        else:
            self.preload_crosshair_v.set_xdata([xdata, xdata])
        if self.preload_crosshair_h is None:
            self.preload_crosshair_h = self.preload_ax.axhline(price, color="#888", linestyle="--", linewidth=0.8)
        else:
            self.preload_crosshair_h.set_ydata([price, price])
        time_val = self.preload_display_times[idx_floor]
        if idx_floor != idx_ceil:
            later = self.preload_display_times[idx_ceil]
            if hasattr(time_val, "timestamp") and hasattr(later, "timestamp"):
                ratio = (xdata - idx_floor) / max(1, idx_ceil - idx_floor)
                interp_ts = time_val.timestamp() * (1 - ratio) + later.timestamp() * ratio
                time_val = datetime.fromtimestamp(interp_ts)
        time_str = time_val.strftime("%Y-%m-%d %H:%M:%S") if hasattr(time_val, "strftime") else str(time_val)
        self.preload_crosshair_label_var.set(f"Time: {time_str} | Price: {price:.2f}")
        if self.preload_canvas:
            self.preload_canvas.draw_idle()

    def _hide_preload_crosshair(self, event=None) -> None:
        self.preload_crosshair_enabled = False
        if self.preload_crosshair_v is not None:
            try:
                self.preload_crosshair_v.remove()
            except Exception:
                pass
            self.preload_crosshair_v = None
        if self.preload_crosshair_h is not None:
            try:
                self.preload_crosshair_h.remove()
            except Exception:
                pass
            self.preload_crosshair_h = None
        self.preload_crosshair_label_var.set("Time: -- | Price: --")
        if self.preload_canvas:
            self.preload_canvas.draw_idle()

    def _toggle_preload_crosshair(self, event) -> None:
        if getattr(event, "button", None) != 1:
            return
        if not getattr(self, "preload_tab_active", False):
            return
        if event.inaxes not in (self.preload_ax, self.preload_ax_macd):
            return
        self.preload_crosshair_enabled = not self.preload_crosshair_enabled
        if self.preload_crosshair_enabled:
            self._update_preload_crosshair(event)
        else:
            self._hide_preload_crosshair()

    def _pan_preload_keyboard(self, direction: int) -> None:
        if self.preload_ax is None or self.preload_ax_macd is None:
            return
        cur_xlim = self.preload_ax.get_xlim()
        span = cur_xlim[1] - cur_xlim[0]
        delta = span * 0.1 * direction
        new_left = cur_xlim[0] + delta
        new_right = cur_xlim[1] + delta
        self.preload_ax.set_xlim(new_left, new_right)
        self.preload_ax_macd.set_xlim(new_left, new_right)
        if self.preload_canvas:
            self.preload_canvas.draw_idle()

    def _atr_series_for(self, times: List[Any], prices: List[float]) -> List[float]:
        """
        Compute ATR series using tracked OHLC aligned with the current context.
        """
        if self.in_streaming:
            highs = self.chart_highs_stream
            lows = self.chart_lows_stream
            closes = self.chart_closes_stream
        elif self.in_backtest:
            highs = self.chart_highs_bt
            lows = self.chart_lows_bt
            closes = self.chart_closes_bt
        else:
            highs = self.chart_highs_live
            lows = self.chart_lows_live
            closes = self.chart_closes_live
        key = (id(highs), len(closes), self.atr_window)
        cached = self._atr_cache.get(key)
        if cached is not None:
            return cached
        atrs = algorithms.atr_series_for(highs, lows, closes, window=self.atr_window)
        try:
            self._atr_cache[key] = atrs
        except Exception:
            pass
        return atrs

    def _ohlc_for_context(self, context: str) -> Tuple[List[float], List[float], List[float]]:
        if context == "stream":
            return self.chart_highs_stream, self.chart_lows_stream, self.chart_closes_stream
        if context == "bt":
            return self.chart_highs_bt, self.chart_lows_bt, self.chart_closes_bt
        if context == "cl":
            return self.chart_highs_cl, self.chart_lows_cl, self.chart_closes_cl
        return self.chart_highs_live, self.chart_lows_live, self.chart_closes_live

    def _rsi_series_for(self, closes: List[float], window: int) -> List[Optional[float]]:
        key = ("rsi", id(closes), len(closes), window)
        cached = self._osc_cache.get(key)
        if cached is not None:
            return cached
        res = algorithms.rsi_series(closes, window=window)
        try:
            self._osc_cache[key] = res
        except Exception:
            pass
        return res

    def _stoch_series_for(self, highs: List[float], lows: List[float], closes: List[float], window: int) -> List[Optional[float]]:
        key = ("stoch", id(highs), id(lows), len(closes), window)
        cached = self._osc_cache.get(key)
        if cached is not None:
            return cached
        res = algorithms.stochastic_series(highs, lows, closes, window=window)
        try:
            self._osc_cache[key] = res
        except Exception:
            pass
        return res

    def _draw_macd_panel(self, ax_macd, macd_hist: List[float], dif: List[float], dea: List[float]) -> None:
        return plotting.draw_macd_panel(ax_macd, macd_hist, dif, dea)

    def _macd_bucket_series(
        self, times: List[datetime], prices: List[float], bucket_minutes: int
    ) -> Tuple[List[float], List[float], List[float]]:
        """
        Compute MACD on N-minute bucket closes, then forward-fill per tick so lengths match price series.
        """
        return algorithms.macd_bucket_series(times, prices, bucket_minutes)

    def _refresh_macd_mode(self) -> None:
        """Redraw charts with the selected MACD timeframe."""
        try:
            self._redraw_chart()
            self._redraw_chart_cl()
            # refresh streaming notebook tab with current data/markers
            marker_snapshot = {
                "open_long_x": list(getattr(self, "stream_open_long_x", [])),
                "open_long_y": list(getattr(self, "stream_open_long_y", [])),
                "close_long_x": list(getattr(self, "stream_close_long_x", [])),
                "close_long_y": list(getattr(self, "stream_close_long_y", [])),
                "open_short_x": list(getattr(self, "stream_open_short_x", [])),
                "open_short_y": list(getattr(self, "stream_open_short_y", [])),
                "close_short_x": list(getattr(self, "stream_close_short_x", [])),
                "close_short_y": list(getattr(self, "stream_close_short_y", [])),
                "spans": list(getattr(self, "stream_position_spans", [])),
            }
            self._update_stream_nb_chart(
                getattr(self, "_stream_path", "") or "stream",
                list(self.chart_times_stream),
                list(self.chart_prices_stream),
                marker_snapshot,
            )
        except Exception:
            pass

    def _active_markers(self):
        if self.in_streaming:
            return (
                self.stream_open_long_x,
                self.stream_open_long_y,
                self.stream_close_long_x,
                self.stream_close_long_y,
                self.stream_open_short_x,
                self.stream_open_short_y,
                self.stream_close_short_x,
                self.stream_close_short_y,
                self.stream_position_spans,
            )
        if self.in_backtest:
            return (
                self.bt_open_long_x,
                self.bt_open_long_y,
                self.bt_close_long_x,
                self.bt_close_long_y,
                self.bt_open_short_x,
                self.bt_open_short_y,
                self.bt_close_short_x,
                self.bt_close_short_y,
                self.bt_position_spans,
            )
        return (
            self.live_open_long_x,
            self.live_open_long_y,
            self.live_close_long_x,
            self.live_close_long_y,
            self.live_open_short_x,
            self.live_open_short_y,
            self.live_close_short_x,
            self.live_close_short_y,
            self.live_position_spans,
        )

    def _trim_window(
        self,
        times: List[Any],
        prices: List[float],
        marker_pairs: Optional[List[Tuple[List[int], List[float]]]] = None,
        spans: Optional[List[Tuple[int, int, str]]] = None,
        flip_markers: Optional[dict] = None,
        adjust_positions: bool = True,
        limit: Optional[int] = None,
        clear_macd_cache: bool = True,
    ) -> None:
        max_len = limit if limit is not None else self.max_points
        total = len(times)
        if total <= max_len:
            return
        drop = total - max_len
        plotting.trim_window(
            times,
            prices,
            marker_pairs=marker_pairs,
            spans=spans,
            adjust_positions=adjust_positions,
            limit=max_len,
            macd_cache_clearers=[self._macd_cache, self._cached_macd, self._atr_cache, self._osc_cache],
            clear_macd_cache=clear_macd_cache,
        )
        self._adjust_macd_flip_markers(drop, flip_markers)

    def _adjust_macd_flip_markers(self, drop: int, flip_markers: Optional[dict]) -> None:
        if not flip_markers or drop <= 0:
            return
        for side, marks in flip_markers.items():
            i = 0
            while i < len(marks):
                idx, val, tag = marks[i]
                if idx < drop:
                    del marks[i]
                else:
                    marks[i] = (idx - drop, val, tag)
                    i += 1

    def _redraw_chart(self) -> None:
        charts.redraw_chart(self)

    def _redraw_chart_cl(self) -> None:
        charts.redraw_chart_cl(self)

    def _redraw_backtest_chart(self) -> None:
        charts.redraw_backtest_chart(self)

    def _update_chart_live(self, now_dt: datetime, last_val: float, high: Optional[float] = None, low: Optional[float] = None, redraw: bool = True) -> None:
        charts.update_chart_live(self, now_dt, last_val, high=high, low=low, redraw=redraw)

    def _update_chart_bt(self, now_dt: datetime, last_val: float, high: Optional[float] = None, low: Optional[float] = None) -> None:
        charts.update_chart_bt(self, now_dt, last_val, high=high, low=low)

    def _update_chart_stream(self, now_dt: datetime, last_val: float, high: Optional[float] = None, low: Optional[float] = None, redraw: bool = True) -> None:
        charts.update_chart_stream(self, now_dt, last_val, high=high, low=low, redraw=redraw)

    def _update_chart_cl(self, now_dt: datetime, last_val: float) -> None:
        charts.update_chart_cl(self, now_dt, last_val)

    def _redraw_stream_chart(self) -> None:
        charts.redraw_stream_chart(self)


    def _add_backtest_trend_tab(
        self,
        mech: str,
        path: str,
        times: List[datetime],
        prices: List[float],
        markers: Dict[str, List[Any]],
        macd_snapshot: Optional[tuple] = None,
        target_notebook: Optional[ttk.Notebook] = None,
    ) -> None:
        nb_target = target_notebook or self.bt_mech_notebook
        if nb_target is None:
            return

        # Streaming Backtest Trend uses a single reusable tab; draw there instead.
        if nb_target is self.bt_stream_notebook:
            self._update_stream_nb_chart(path, times, prices, markers)
            return

        if mech not in self.bt_mech_subtabs:
            frame = ttk.Frame(nb_target)
            nb_target.add(frame, text=mech)
            nb = ttk.Notebook(frame)
            nb.pack(fill=tk.BOTH, expand=True)
            self.bt_mech_subtabs[mech] = nb
            try:
                nb_target.select(frame)
            except Exception:
                pass
        nb = self.bt_mech_subtabs[mech]
        csv_tab = ttk.Frame(nb)
        nb.add(csv_tab, text=os.path.basename(path))
        try:
            nb.select(csv_tab)
            nb_target.select(nb)
        except Exception:
            pass

        palette = getattr(self, "theme", None)
        chart_bg = getattr(palette, "chart_face", "#FFFFFF")

        fig = Figure(figsize=(12, 7), dpi=100, constrained_layout=True)
        ax_price, ax_macd = fig.subplots(
            2,
            1,
            sharex=True,
            gridspec_kw={"height_ratios": plotting.PRICE_MACD_HEIGHT_RATIOS},
        )
        ax_rsi = ax_macd.twinx()
        macd_hist_all, dif_all, dea_all = self._macd_series_for(times if times else list(range(len(prices))), prices)
        highs, lows, closes = self._ohlc_for_context("bt")
        rsi_series = self._rsi_series_for(closes, self.rsi_window)
        plotting.draw_price_macd_markers(
            ax_price,
            ax_macd,
            times,
            prices,
            markers,
            spans=markers.get("spans", []),
            title="",
            y_label="Price",
            max_ticks=6,
            macd_fetcher=None,
            macd_data=(macd_hist_all, dif_all, dea_all),
            ax_rsi=ax_rsi,
            rsi_data=rsi_series,
            fixed_ylim=getattr(self, "bt_price_range_fixed", None),
            macd_fixed_ylim=getattr(self, "bt_macd_range_fixed", None),
            rsi_visible=self.show_rsi_on_chart,
        )
        flip_snapshot = {k: list(v) for k, v in self.macd_flip_markers_bt.items()}
        plotting.draw_macd_flips(ax_macd, flip_snapshot)
        self.macd_flip_markers_bt = {"bear": [], "bull": []}
        canvas = FigureCanvasTkAgg(fig, master=csv_tab)
        canvas.draw()
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.configure(bg=chart_bg, highlightthickness=0, borderwidth=0)
        canvas_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=0, pady=0)

    def _ensure_stream_nb_canvas(self) -> None:
        """Guarantee a single reusable tab + canvas inside Streaming Backtest Trend notebook."""
        palette = getattr(self, "theme", None)
        chart_bg = getattr(palette, "chart_face", "#FFFFFF")
        if self.bt_stream_notebook is None:
            return
        if self.stream_nb_tab is None or str(self.stream_nb_tab) not in self.bt_stream_notebook.tabs():
            frame = ttk.Frame(self.bt_stream_notebook)
            self.bt_stream_notebook.add(frame, text="Streaming (live)")
            self.stream_nb_tab = frame
            try:
                self.bt_stream_notebook.select(frame)
            except Exception:
                pass

            chart_frame = ttk.Frame(frame)
            chart_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=0, pady=0)

            self.stream_nb_fig = Figure(figsize=(12, 7), dpi=100, constrained_layout=True)
            self.stream_nb_ax, self.stream_nb_ax_macd = self.stream_nb_fig.subplots(
                2,
                1,
                sharex=True,
                gridspec_kw={"height_ratios": plotting.PRICE_MACD_HEIGHT_RATIOS},
            )
            self.stream_nb_ax.set_title("Streaming Backtest Trend")
            self.stream_nb_ax.set_ylabel("Price")
            self.stream_nb_ax_macd.set_ylabel("MACD")
            self.stream_nb_ax_macd.set_xlabel("Time")
            self.stream_nb_canvas = FigureCanvasTkAgg(self.stream_nb_fig, master=chart_frame)
            self.stream_nb_canvas.draw()
            canvas_widget = self.stream_nb_canvas.get_tk_widget()
            canvas_widget.configure(bg=chart_bg, highlightthickness=0, borderwidth=0)
            canvas_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=0, pady=0)

    def _update_stream_nb_chart(
        self, path: str, times: List[datetime], prices: List[float], markers: Dict[str, List[Any]]
    ) -> None:
        """Redraw the Streaming Backtest Trend notebook tab with latest streaming data."""
        _ = getattr(self, "theme", None)
        self._ensure_stream_nb_canvas()
        if self.stream_nb_ax is None or self.stream_nb_canvas is None:
            return
        macd_data = None
        macd_fetcher = self._macd_series_for
        if getattr(self, "_stream_macd_full", None) is not None:
            macd_data = self._macd_series_for(times, prices)
            macd_fetcher = None
        plotting.draw_price_macd_markers(
            self.stream_nb_ax,
            self.stream_nb_ax_macd,
            times,
            prices,
            markers,
            spans=markers.get("spans", []),
            title="Streaming Backtest Trend" if not path else f"Streaming Backtest Trend – {os.path.basename(path)}",
            y_label="Price",
            max_ticks=6,
            macd_fetcher=macd_fetcher,
            macd_data=macd_data,
            no_data_text="No data yet",
            fixed_ylim=getattr(self, "stream_price_range_fixed", None),
            macd_fixed_ylim=getattr(self, "stream_macd_range_fixed", None),
        )

        self.stream_nb_canvas.draw_idle()

    def _mark_trade(self, side: str, action: str, price: float, index: Optional[int]) -> None:
        """
        Add a colored marker at the given tick index for this trade.
        side: 'long' or 'short'
        action: 'open' or 'close'
        """
        if index is None:
            return

        (
            open_long_x,
            open_long_y,
            close_long_x,
            close_long_y,
            open_short_x,
            open_short_y,
            close_short_x,
            close_short_y,
            _,
        ) = self._active_markers()

        if side == "long":
            if action == "open":
                open_long_x.append(index)
                open_long_y.append(price)
            else:
                close_long_x.append(index)
                close_long_y.append(price)
        else:
            if action == "open":
                open_short_x.append(index)
                open_short_y.append(price)
            else:
                close_short_x.append(index)
                close_short_y.append(price)

        self._redraw_chart()

    def _add_pl_line(self, side: str, open_price: float, close_price: float,
                     open_index: Optional[int], close_index: Optional[int]) -> None:
        """
        P/L lines are suppressed; keep method as a no-op for compatibility.
        """
        if close_index is None or open_index is None:
            return
        # still track spans for shaded holding periods
        if side == "long":
            profit = close_price - open_price
        else:
            profit = open_price - close_price
        color = "green" if profit >= 0 else "red"
        spans = self._active_markers()[-1]
        spans.append((open_index, close_index, color))
        if self.suppress_backtest_ui:
            return

    # ----- Backtest CSV through strategies -----

    def backtest_csv(self) -> None:
        # stop live run
        self.running = False

        path = self._with_topmost_suspended(
            lambda: filedialog.askopenfilename(
                title="Select CSV for backtest",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
        )
        if not path:
            return

        self._run_quick_backtest_for_path(path)

    def quick_backtest_multi(self) -> None:
        paths = self._with_topmost_suspended(
            lambda: filedialog.askopenfilenames(
                title="Select CSV files for backtest",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
        )
        if not paths:
            return
        for child in self.quick_results_frame.winfo_children():
            child.destroy()
        # aggregate stats per selected mechanism across all files
        agg: dict = {}
        if self.bt_mech_notebook is not None:
            for tab_id in self.bt_mech_notebook.tabs():
                self.bt_mech_notebook.forget(tab_id)
        self.bt_mech_subtabs = {}
        for path in paths:
            self._reset_backtest_chart_state()
            summary = self._run_quick_backtest_for_path(path, agg)
            if summary:
                ttk.Label(self.quick_results_frame, text=summary, anchor="w", justify=tk.LEFT).pack(
                    side=tk.TOP, anchor="w", padx=6, pady=2
                )
        # render aggregated totals for mechanisms that ran
        if agg:
            lines = ["Aggregated totals:"]
            for mech in sorted(agg.keys()):
                s = agg[mech]
                lines.append(
                    f"{mech}: net={s['net']:.2f} trades={s['trades']} fees={s.get('fees', 0.0):.2f}"
                )
            ttk.Label(self.quick_results_frame, text="\n".join(lines), anchor="w", justify=tk.LEFT).pack(
                side=tk.TOP, anchor="w", padx=6, pady=4
            )

    def _run_quick_backtest_for_path(self, path: str, agg: Optional[dict] = None) -> Optional[str]:
        self.in_backtest = True
        self.suppress_backtest_ui = True
        try:
            self._atr_cache.clear()
            ticks = parse_ticks_from_csv(path)

            if not ticks:
                raise ValueError("No valid time/price rows in CSV")

            # Precompute fixed ranges for backtest charts
            prices_all = [tick[1] for tick in ticks]
            times_all = [tick[0] for tick in ticks]
            self.bt_price_range_fixed = self._calc_fixed_range(prices_all)
            macd_hist_all, dif_all, dea_all = self._macd_series_for(times_all, prices_all)
            macd_vals_all = list(macd_hist_all or []) + list(dif_all or []) + list(dea_all or [])
            self.bt_macd_range_fixed = self._calc_fixed_range(macd_vals_all)

            original_flags = {
                "me3": bool(self.use_me3.get()),
                "me8": bool(self.use_me8.get()),
                "me_macd_atr": bool(self.use_me_macd_atr.get()),
                "me4": bool(self.use_me4.get()),
            }
            enabled_mechs = [
                name for name, flag in [
                    ("M1", original_flags["me3"]),
                    ("M2", original_flags["me8"]),
                    ("M3", original_flags["me_macd_atr"]),
                    ("M4", original_flags["me4"]),
                ] if flag
            ]
            if not enabled_mechs:
                self._with_topmost_suspended(
                    lambda: messagebox.showinfo("No mechanisms", "Enable at least one mechanism before backtest.")
                )
                return None

            summaries = []
            for mech in enabled_mechs:
                self._set_mechanism_flags(mech)
                if mech == "M3" and hasattr(self, "_reset_macd_atr_state"):
                    self._reset_macd_atr_state()
                self._reset_quick_backtest_state()
                self.macd_flip_markers_bt = {"bear": [], "bull": []}
                self._apply_extra_fee = True
                trades_before = len(self.pos_tree.get_children())
                self._macd_prev_relation["bt"] = None
                self._macd_last_flip_index["bt"] = -9999

                last_dt_str = ""
                # determine sampling step
                try:
                    step_val = max(1, int(self.backtest_step_var.get().strip()))
                except Exception:
                    step_val = 1
                sampled_ticks = ticks[::step_val] if step_val > 1 else ticks
                sampled_indices = list(range(0, len(ticks), step_val))
                sampled_len = min(len(sampled_ticks), len(sampled_indices))
                # Replay ticks
                for sample_idx, tick_tuple in zip(sampled_indices[:sampled_len], sampled_ticks[:sampled_len]):
                    dt_val = tick_tuple[0]
                    p_val = tick_tuple[1]
                    high_val = tick_tuple[2] if len(tick_tuple) > 2 else None
                    low_val = tick_tuple[3] if len(tick_tuple) > 3 else None
                    self.last_price = p_val
                    last_dt_str = dt_val.strftime("%Y-%m-%d %H:%M:%S")
                    self.last_time_str = last_dt_str

                    display_time = ui_helpers.logic_time_display(self.last_time_str)
                    self.tree.insert("", tk.END, values=(display_time, self.last_price))
                    children = self.tree.get_children()
                    # Avoid pruning during backtest so the table shows full CSV
                    if len(children) > self.max_tick_rows:
                        self.tree.delete(*children[: len(children) - self.max_tick_rows])

                    self._update_chart_bt(dt_val, p_val, high_val, low_val)

                    if self.use_me3.get():
                        self._mechanism3_mean_revert_logic()
                    if self.use_me8.get():
                        self._mechanism8_inverse_mean_revert_logic()
                    if getattr(self, "use_me_macd_atr", None) and self.use_me_macd_atr.get():
                        self._mechanism_macd_atr_logic()
                    # removed other mechanisms
                    dif_val = dif_all[sample_idx] if sample_idx < len(dif_all) else None
                    dea_val = dea_all[sample_idx] if sample_idx < len(dea_all) else None
                    hist_val = macd_hist_all[sample_idx] if sample_idx < len(macd_hist_all) else None
                    chart_idx = len(self.chart_prices_bt) - 1
                    self._track_macd_relation(chart_idx, last_dt_str, dif_val, dea_val, context="bt", hist_val=hist_val)
                    if getattr(self, "use_me4", None) and self.use_me4.get():
                        self._mechanism4_macd_mode_logic()

                # Force-close any leftover positions at last price to realize P/L
                if last_dt_str and self.last_price is not None:
                    self._force_close_all_positions(self.last_price, last_dt_str)

                self._update_position_state_label()
                self._update_settlement_label()
                self._redraw_chart()
                trades = self.trade_count

                # capture chart data for backtest trend tab
                times_snapshot = list(self.chart_times_bt)
                prices_snapshot = list(self.chart_prices_bt)
                macd_snapshot = (list(macd_hist_all), list(dif_all), list(dea_all))
                marker_snapshot = {
                    "open_long_x": list(self.bt_open_long_x),
                    "open_long_y": list(self.bt_open_long_y),
                    "close_long_x": list(self.bt_close_long_x),
                    "close_long_y": list(self.bt_close_long_y),
                    "open_short_x": list(self.bt_open_short_x),
                    "open_short_y": list(self.bt_open_short_y),
                    "close_short_x": list(self.bt_close_short_x),
                    "close_short_y": list(self.bt_close_short_y),
                    "spans": list(self.bt_position_spans),
                }
                self._add_backtest_trend_tab(mech, path, times_snapshot, prices_snapshot, marker_snapshot, macd_snapshot)
                # Populate MACD Data tab with backtest MACD rows
                self._populate_macd_data_backtest(times_snapshot, prices_snapshot, macd_hist_all, dif_all, dea_all)

                summaries.append(
                    f"{mech}=net:{self.settlement:.2f} trades:{trades} fees:{getattr(self, 'total_fees', 0.0):.2f}"
                )
                if agg is not None:
                    agg.setdefault(mech, {"net": 0.0, "trades": 0, "fees": 0.0})
                    agg[mech]["net"] += self.settlement
                    agg[mech]["trades"] += trades
                    agg[mech]["fees"] += getattr(self, "total_fees", 0.0)

            # restore flags
            self.use_me3.set(original_flags["me3"])
            self.use_me8.set(original_flags["me8"])
            self._apply_extra_fee = False

            self.status_label.config(
                text=f"Backtest done ({os.path.basename(path)}): " + "; ".join(summaries)
            )
            return f"{os.path.basename(path)} -> " + "; ".join(summaries)

        except Exception as e:
            messagebox.showerror("Backtest error", f"Failed to backtest:\n{e}")
            return None
        finally:
            # ensure commands are never emitted during backtest
            self.in_backtest = False
            self._apply_extra_fee = False
            self.suppress_backtest_ui = False
            # Reset live totals so the status bar returns to "live" zero after quick backtest.
            self.settlement = 0.0
            self.trade_count = 0
            self.total_fees = 0.0
            self._update_settlement_label()
            try:
                self._refresh_status()
            except Exception:
                pass

    def start_stream_backtest(self) -> None:
        controller.start_stream_backtest(self)

    def _stream_next_tick(self) -> None:
        controller.stream_next_tick(self)

    def stop_stream_backtest(self) -> None:
        controller.stop_stream_backtest(self)

    def _seek_stream_progress(self, value: str) -> None:
        controller.seek_stream_progress(self, value)

    def _reset_stream_state(self, clear_progress: bool = True) -> None:
        controller._reset_stream_state(self, clear_progress)

    def _populate_macd_data_backtest(self, times: List[datetime], prices: List[float], macd_hist: List[float], dif: List[float], dea: List[float]) -> None:
        """
        Fill the MACD Data tab with backtest MACD/ATR rows.
        """
        if getattr(self, "macd_tree", None) is None:
            return
        try:
            self.macd_tree.delete(*self.macd_tree.get_children())
        except Exception:
            return
        # Compute ATR series aligned to backtest OHLC
        atrs = []
        try:
            atrs = self._atr_series_for(times, prices)
        except Exception:
            atrs = []
        highs, lows, closes = self._ohlc_for_context("bt")
        rsi_vals = self._rsi_series_for(closes, self.rsi_window)
        stoch_vals = self._stoch_series_for(highs, lows, closes, self.stoch_window)

        for idx, (t_val, price_val) in enumerate(zip(times, prices)):
            t_str = t_val.strftime("%Y-%m-%d %H:%M:%S") if isinstance(t_val, datetime) else str(t_val)
            dif_val = dif[idx] if idx < len(dif) else None
            dea_val = dea[idx] if idx < len(dea) else None
            hist_val = macd_hist[idx] if idx < len(macd_hist) else None
            atr_val = atrs[idx] if idx < len(atrs) else None
            rsi_val = rsi_vals[idx] if idx < len(rsi_vals) else None
            stoch_val = stoch_vals[idx] if idx < len(stoch_vals) else None
            def fmt(v):
                if v is None:
                    return ""
                try:
                    if isinstance(v, float) and math.isnan(v):
                        return ""
                    return f"{float(v):.4f}"
                except Exception:
                    return ""
            vol_str = ""
            if atr_val is not None and price_val:
                try:
                    vol_pct = (atr_val / price_val) * 100
                    vol_str = f"{vol_pct:.2f}%"
                except Exception:
                    vol_str = ""
            row = (
                t_str,
                f"{price_val:.4f}",
                fmt(dif_val),
                fmt(dea_val),
                fmt(hist_val),
                fmt(atr_val),
                vol_str,
                "" if rsi_val is None else f"{rsi_val:.2f}",
                "" if stoch_val is None else f"{stoch_val:.2f}",
            )
            try:
                self.macd_tree.insert("", tk.END, values=row)
            except Exception:
                break

    def _reset_quick_backtest_state(self) -> None:
        controller.reset_quick_backtest_state(self)
        self.bt_price_range_fixed = None
        self.bt_macd_range_fixed = None

    def _reset_backtest_chart_state(self) -> None:
        controller._reset_backtest_chart_state(self)

    def _reset_cl_state(self) -> None:
        controller._reset_cl_state(self)

    def _reset_live_state(self) -> None:
        controller.reset_live_state(self)

    def _calc_fixed_range(self, values: List[float], padding_ratio: float = 0.02) -> Optional[Tuple[float, float]]:
        if not values:
            return None
        mn = min(values)
        mx = max(values)
        span = mx - mn
        pad = span * padding_ratio if span > 0 else 0.1
        return (mn - pad, mx + pad)

    def _set_mechanism_flags(self, active: str) -> None:
        self.use_me3.set(active == "M1")
        self.use_me8.set(active == "M2")
        if hasattr(self, "use_me_macd_atr"):
            self.use_me_macd_atr.set(active == "M3")
        if hasattr(self, "use_me4"):
            self.use_me4.set(active == "M4")

    def _force_close_all_positions(self, price: float, time_str: str) -> None:
        trading.force_close_all_positions(self, price, time_str)

    # ----- Mechanism 3: mean reversion to SMA -----

    def _mechanism3_mean_revert_logic(self) -> None:
        mechanisms.mechanism3_mean_revert_logic(self)

    # ----- Mechanism 2: inverse mean reversion to SMA -----

    def _mechanism8_inverse_mean_revert_logic(self) -> None:
        mechanisms.mechanism8_inverse_mean_revert_logic(self)

    # ----- Mechanism: MACD + ATR trend/momentum -----

    def _mechanism_macd_atr_logic(self) -> None:
        mechanisms.mechanism_macd_atr_logic(self)

    # ----- Real tick feed control -----

    def start_feed(self) -> None:
        controller.start_feed(self)

    def stop_feed(self) -> None:
        controller.stop_feed(self)

    def start_feed_cl(self) -> None:
        controller.start_feed_cl(self)

    def stop_feed_cl(self) -> None:
        controller.stop_feed_cl(self)

    def _schedule_next_tick(self) -> None:
        controller._schedule_next_tick(self)

    def _schedule_next_tick_cl(self) -> None:
        controller._schedule_next_tick_cl(self)

    def fetch_and_update(self) -> None:
        controller.fetch_and_update(self)

    def fetch_and_update_cl(self) -> None:
        controller.fetch_and_update_cl(self)

    def _fetch_tick_async(self, now_dt: datetime) -> None:
        controller._fetch_tick_async(self, now_dt)

    def _fetch_tick_async_cl(self, now_dt: datetime) -> None:
        controller._fetch_tick_async_cl(self, now_dt)

    def _finish_tick(self, now_dt: datetime, tick: Optional[Dict[str, Any]], err: Optional[Exception]) -> None:
        controller._finish_tick(self, now_dt, tick, err)

    def _finish_tick_cl(self, now_dt: datetime, tick: Optional[Dict[str, Any]], err: Optional[Exception]) -> None:
        controller._finish_tick_cl(self, now_dt, tick, err)

    # ----- Position / trading management -----

    def _update_position_state_label(self) -> None:
        total = len(self.open_positions)
        long_count = sum(1 for p in self.open_positions if p["side"] == "long")
        short_count = sum(1 for p in self.open_positions if p["side"] == "short")
        self.position_label.config(
            text=f"Hold positions: {total} (long: {long_count}, short: {short_count})"
        )

    def _update_settlement_label(self) -> None:
        self.settlement_label.config(text=f"Settlement (net): {self.settlement:.2f}")
        self._update_equity_label()

    def _update_equity_label(self) -> None:
        if hasattr(self, "equity_label"):
            self.equity_label.config(text=f"Equity: {self.equity:.2f}")

    def _refresh_init_margins(self) -> None:
        """
        Update the displayed per-contract initial margins using latest price and ratios.
        """
        try:
            last_price = self.last_price if self.last_price is not None else 0.0
            point_value = getattr(self, "leverage", 1.0)
            long_ratio = getattr(self, "long_margin_ratio", 0.0)
            short_ratio = getattr(self, "short_margin_ratio", 0.0)
            long_init = last_price * long_ratio * point_value
            short_init = last_price * short_ratio * point_value
            self.long_init_margin = long_init
            self.short_init_margin = short_init
            if hasattr(self, "long_init_margin_var"):
                self.long_init_margin_var.set(f"{long_init:.2f}")
            if hasattr(self, "short_init_margin_var"):
                self.short_init_margin_var.set(f"{short_init:.2f}")
        except Exception:
            pass

    def _append_position_row(
        self,
        action: str,
        qty: int,
        time_str: str,
        price: Optional[float],
        diff: Optional[float],
    ) -> None:
        if self.suppress_backtest_ui:
            return
        diff_str = "" if diff is None else f"{diff:.2f}"
        price_str = "" if price is None else f"{price:.1f}"
        display_time = ui_helpers.logic_time_display(time_str)
        self.pos_tree.insert("", tk.END, values=(action, qty, display_time, price_str, diff_str))
        self.pos_tree.yview_moveto(1.0)

    def _current_tick_info(self) -> Optional[Tuple[str, float]]:
        if self.last_time_str is None or self.last_price is None:
            self.status_label.config(text="Status: no valid tick yet – cannot trade")
            return None
        return self.last_time_str, self.last_price

    def open_long(self, owner: str = "MANUAL") -> None:
        trading.open_long(self, owner)

    def open_short(self, owner: str = "MANUAL") -> None:
        trading.open_short(self, owner)

    def close_long(self, owner: Optional[str] = None) -> None:
        trading.close_long(self, owner)

    def close_short(self, owner: Optional[str] = None) -> None:
        trading.close_short(self, owner)

    def on_close(self) -> None:
        self.running = False
        self.running_cl = False
        self._close_csv()
        self._close_csv_cl()
        self.stop_autoclicker()
        self.root.destroy()

    def apply_data_settings(self) -> None:
        sym = self.symbol_var.get().strip()
        url_tpl = self.url_var.get().strip()
        interval_str = self.interval_var.get().strip()
        csv_dir = self.csv_dir_var.get().strip()

        if sym:
            self.symbol = sym
        # auto loosen time filter for global futures (hf_) or dm_ feeds
        sym_lower = self.symbol.lower()
        self.enforce_trading_window = not (sym_lower.startswith("hf_") or sym_lower.startswith("dm_"))
        if url_tpl:
            self.data_url_template = url_tpl
        if csv_dir:
            try:
                os.makedirs(csv_dir, exist_ok=True)
                self.csv_dir = csv_dir
            except Exception as e:
                messagebox.showerror("Data Settings", f"Failed to set save path:\n{e}")

        try:
            new_interval = float(interval_str)
            if new_interval > 0:
                self.interval = new_interval
        except ValueError:
            pass

        self.status_label.config(
            text=f"Status: settings applied (symbol={self.symbol}, interval={self.interval}, save={self.csv_dir})"
        )

    def apply_contract_info(self) -> None:
        """Apply NR contract settings (fee, tick size, leverage, equity, fee mode/percent)."""
        try:
            self.trade_fee = float(self.trade_fee_var.get().strip())
        except Exception:
            pass
        try:
            self.tick_size = float(self.tick_size_var.get().strip())
        except Exception:
            pass
        try:
            self.leverage = float(self.leverage_var.get().strip())
        except Exception:
            pass
        try:
            self.equity = float(self.equity_var.get().strip())
        except Exception:
            pass
        mode = str(self.trade_fee_mode_var.get()).strip().lower()
        if mode in ("fixed", "percent"):
            self.trade_fee_mode = mode
        try:
            self.trade_fee_pct = max(0.0, float(self.trade_fee_pct_var.get().strip()))
        except Exception:
            pass
        try:
            self.no_close_today_fee = bool(self.no_close_today_fee_var.get())
        except Exception:
            self.no_close_today_fee = True
        try:
            self.order_qty = max(0, int(float(self.order_qty_var.get().strip())))
        except Exception:
            pass
        try:
            self.long_margin_ratio = float(self.long_margin_ratio_var.get().strip())
        except Exception:
            pass
        try:
            self.short_margin_ratio = float(self.short_margin_ratio_var.get().strip())
        except Exception:
            pass
        self._refresh_init_margins()
        try:
            self.contract_symbol_label.config(text=f"Symbol: {self.symbol}")
            self.status_label.config(text="Status: contract info updated")
            self._update_equity_label()
        except Exception:
            pass

    def apply_data_settings_cl(self) -> None:
        sym = self.symbol_cl_var.get().strip()
        url_tpl = self.url_cl_var.get().strip()
        interval_str = self.interval_cl_var.get().strip()
        csv_dir = self.csv_dir_cl_var.get().strip()

        if sym:
            self.symbol_cl_display = sym
            self.symbol_cl = sym if sym.lower().startswith("hf_") else f"hf_{sym}"
        sym_lower = self.symbol_cl.lower()
        self.enforce_trading_window_cl = not (sym_lower.startswith("hf_") or sym_lower.startswith("dm_"))
        if url_tpl:
            self.data_url_template_cl = url_tpl
        if csv_dir:
            try:
                os.makedirs(csv_dir, exist_ok=True)
                self.csv_dir_cl = csv_dir
            except Exception as e:
                messagebox.showerror("Data Settings", f"Failed to set CL save path:\n{e}")
        try:
            new_interval = float(interval_str)
            if new_interval > 0:
                self.interval_cl = new_interval
        except ValueError:
            pass
        self.status_label.config(
            text=f"Status: CL settings applied (symbol={self.symbol_cl_display}, interval={self.interval_cl}, save={self.csv_dir_cl})"
        )

    def _choose_csv_dir(self) -> None:
        def pick():
            return filedialog.askdirectory(title="Select folder to save CSV")
        path = self._with_topmost_suspended(pick)
        if not path:
            return
        try:
            os.makedirs(path, exist_ok=True)
        except Exception as e:
            messagebox.showerror("Data Settings", f"Failed to use folder:\n{e}")
            return
        self.csv_dir = path
        self.csv_dir_var.set(path)
        self.status_label.config(text=f"Status: save folder set to {path}")

    def _choose_sim_csv(self) -> None:
        path = self._with_topmost_suspended(
            lambda: filedialog.askopenfilename(
                title="Select CSV for simulation",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
        )
        if path:
            self.sim_csv_path_var.set(path)

    def _reset_macd_atr_state(self) -> None:
        params = self.macd_atr_params
        self.macd_atr_state = {
            "equity": params["initial_equity"],
            "position": 0,
            "entry_price": None,
            "entry_atr": None,
            "entry_index": None,
            "stop_price": None,
            "tp_price": None,
            "current_day": None,
            "equity_day_start": params["initial_equity"],
            "daily_pnl": 0.0,
            "daily_loss_limit": params["daily_loss_frac"] * params["initial_equity"],
            "no_new_trades": False,
        }
        if hasattr(self, "macd_atr_status_var"):
            self.macd_atr_status_var.set("--")
        if hasattr(self, "macd_atr_pos_var"):
            self.macd_atr_pos_var.set("Pos: 0")

    def _choose_csv_dir_cl(self) -> None:
        def pick():
            return filedialog.askdirectory(title="Select folder to save CSV (CL)")
        path = self._with_topmost_suspended(pick)
        if not path:
            return
        try:
            os.makedirs(path, exist_ok=True)
        except Exception as e:
            messagebox.showerror("Data Settings", f"Failed to use folder:\n{e}")
            return
        self.csv_dir_cl = path
        self.csv_dir_cl_var.set(path)
        self.status_label.config(text=f"Status: CL save folder set to {path}")

    # ----- Test tab handlers -----

    def _run_trading_movement_test(self) -> None:
        test_tab.run_trading_movement_test(self)

    def _append_test_log(self, msg: str) -> None:
        test_tab.append_test_log(self, msg)

    def _update_cursor_coords(self) -> None:
        test_tab.update_cursor_coords(self, PYAUTOGUI_AVAILABLE, pyautogui if PYAUTOGUI_AVAILABLE else None)

    def load_analysis_csv(self) -> None:
        paths = self._with_topmost_suspended(
            lambda: filedialog.askopenfilenames(
                title="Select CSV files for analysis",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
        )
        if not paths:
            return

        try:
            summaries = analysis.summarize_csv_paths(list(paths))
        except ValueError as e:
            messagebox.showerror("Analysis", str(e))
            return
        self.analysis_text.delete("1.0", tk.END)
        self.analysis_text.insert("1.0", "\n".join(summaries))

    def _relation_add_point(self) -> None:
        relation_tab.add_point(self)

    def _relation_clear_points(self) -> None:
        relation_tab.clear_points(self)

    def _redraw_relation_plot(self) -> None:
        relation_tab.redraw(self)


def main() -> None:
    symbol = sys.argv[1] if len(sys.argv) >= 2 else "NR0"

    if len(sys.argv) >= 3:
        try:
            interval = float(sys.argv[2])
        except ValueError:
            interval = config.DEFAULT_INTERVAL_NR
    else:
        interval = config.DEFAULT_INTERVAL_NR

    root = tk.Tk()
    root.withdraw()
    app = RealTickApp(root, symbol=symbol, interval=interval)
    root.mainloop()


if __name__ == "__main__":
    main()
