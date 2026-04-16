"""
Theme helpers for adapting the UI to the host system preference.
"""
from dataclasses import dataclass
from datetime import datetime, time as dtime
import os
import platform
import subprocess
from typing import Optional


@dataclass(frozen=True)
class ThemePalette:
    name: str
    background: str
    surface: str
    text: str
    muted_text: str
    control: str
    control_active: str
    border: str
    entry_bg: str
    insert: str
    tab_bg: str
    tab_selected_bg: str
    selection_bg: str
    selection_fg: str
    tree_heading_bg: str
    tooltip_bg: str
    tooltip_fg: str
    chart_face: str
    chart_text: str
    chart_grid: str
    line_primary: str
    positive: str
    negative: str
    crosshair: str


LIGHT_THEME = ThemePalette(
    name="light",
    background="#FFFFFF",
    surface="#F5F5F5",
    text="#000000",
    muted_text="#444444",
    control="#F0F0F0",
    control_active="#E0E0E0",
    border="#CCCCCC",
    entry_bg="#FFFFFF",
    insert="#000000",
    tab_bg="#F5F5F5",
    tab_selected_bg="#E0E0E0",
    selection_bg="#C0D4FF",
    selection_fg="#000000",
    tree_heading_bg="#ECECEC",
    tooltip_bg="#F7F7F7",
    tooltip_fg="#000000",
    chart_face="#FFFFFF",
    chart_text="#000000",
    chart_grid="#DDDDDD",
    line_primary="#000000",
    positive="#2ca02c",
    negative="#d62728",
    crosshair="#777777",
)


DARK_THEME = ThemePalette(
    name="dark",
    background="#1E1E1E",
    surface="#252525",
    text="#F2F2F2",
    muted_text="#CFCFCF",
    control="#2D2D2D",
    control_active="#3A3A3A",
    border="#3C3C3C",
    entry_bg="#2B2B2B",
    insert="#FFFFFF",
    tab_bg="#252525",
    tab_selected_bg="#333333",
    selection_bg="#2F4F6F",
    selection_fg="#F5F5F5",
    tree_heading_bg="#2A2A2A",
    tooltip_bg="#2E2E2E",
    tooltip_fg="#F2F2F2",
    chart_face="#111111",
    chart_text="#E6E6E6",
    chart_grid="#333333",
    line_primary="#E0E0E0",
    positive="#2ca02c",
    negative="#d62728",
    crosshair="#A0A0A0",
)


_ACTIVE_THEME: ThemePalette = LIGHT_THEME


def _run_cmd(cmd: list[str]) -> Optional[str]:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        return None
    return None


def _detect_macos_theme() -> Optional[str]:
    if platform.system() != "Darwin":
        return None
    output = _run_cmd(["defaults", "read", "-g", "AppleInterfaceStyle"])
    if output and output.lower().startswith("dark"):
        return "dark"
    return "light"


def _is_daytime() -> bool:
    now = datetime.now().time()
    start = dtime(8, 40, 0)
    end = dtime(23, 0, 0)
    return start <= now <= end


def _detect_macos_time_theme() -> Optional[str]:
    if platform.system() != "Darwin":
        return None
    return "light" if _is_daytime() else "dark"


def _detect_windows_time_theme() -> Optional[str]:
    if platform.system() != "Windows":
        return None
    if _is_daytime():
        return "light"
    return None


def _detect_windows_theme() -> Optional[str]:
    if platform.system() != "Windows":
        return None
    try:
        import winreg

        path = r"Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return "light" if val else "dark"
    except Exception:
        return None


def _detect_gnome_theme() -> Optional[str]:
    if platform.system() != "Linux":
        return None
    output = _run_cmd(["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"])
    if not output:
        return None
    lower = output.lower()
    if "dark" in lower:
        return "dark"
    if "light" in lower:
        return "light"
    return None


def detect_system_theme(default: str = "light") -> str:
    """
    Return 'dark' or 'light' based on the host preference, falling back to default.
    """
    env_pref = os.environ.get("APP_THEME")
    if env_pref and env_pref.lower() in ("dark", "light"):
        return env_pref.lower()
    detected = (
        _detect_macos_time_theme()
        or _detect_macos_theme()
        or _detect_windows_time_theme()
        or _detect_windows_theme()
        or _detect_gnome_theme()
    )
    if detected in ("dark", "light"):
        return detected
    return default


def set_active_theme(theme: ThemePalette) -> None:
    global _ACTIVE_THEME
    _ACTIVE_THEME = theme


def get_active_theme() -> ThemePalette:
    return _ACTIVE_THEME


def palette_for(name: str) -> ThemePalette:
    if name == "dark":
        return DARK_THEME
    return LIGHT_THEME


def apply_ttk_theme(root, style, palette: ThemePalette) -> None:
    """
    Configure ttk styles with the provided palette.
    """
    set_active_theme(palette)
    try:
        root.configure(bg=palette.background)
    except Exception:
        pass
    try:
        style.theme_use("clam")
    except Exception:
        pass

    base_kwargs = {"background": palette.background, "foreground": palette.text}
    style.configure(".", **base_kwargs)
    style.configure("TFrame", **base_kwargs)
    style.configure("TLabel", **base_kwargs)
    style.configure("TCheckbutton", **base_kwargs)
    style.configure("Dark.TCheckbutton", **base_kwargs)

    button_kwargs = {"background": palette.control, "foreground": palette.text, "bordercolor": palette.border}
    style.configure("TButton", **button_kwargs)
    style.configure("Dark.TButton", **button_kwargs)
    style.map("TButton", background=[("active", palette.control_active)])
    style.map("Dark.TButton", background=[("active", palette.control_active)])

    entry_kwargs = {
        "fieldbackground": palette.entry_bg,
        "foreground": palette.text,
        "insertcolor": palette.insert,
        "bordercolor": palette.border,
    }
    style.configure("TEntry", **entry_kwargs)
    style.configure("Dark.TEntry", **entry_kwargs)

    combo_kwargs = {
        "fieldbackground": palette.entry_bg,
        "background": palette.entry_bg,
        "foreground": palette.text,
        "arrowcolor": palette.text,
        "bordercolor": palette.border,
    }
    style.configure("TCombobox", **combo_kwargs)
    style.configure("Dark.TCombobox", **combo_kwargs)
    style.map("TCombobox", fieldbackground=[("readonly", palette.entry_bg)], foreground=[("readonly", palette.text)])
    style.map("Dark.TCombobox", fieldbackground=[("readonly", palette.entry_bg)], foreground=[("readonly", palette.text)])

    style.configure("Treeview", background=palette.surface, fieldbackground=palette.surface, foreground=palette.text, bordercolor=palette.border)
    style.map("Treeview", background=[("selected", palette.selection_bg)], foreground=[("selected", palette.selection_fg)])
    style.configure("Treeview.Heading", background=palette.tree_heading_bg, foreground=palette.text)

    style.configure("TNotebook", background=palette.background)
    style.configure("TNotebook.Tab", background=palette.tab_bg, foreground=palette.text)
    style.map("TNotebook.Tab", background=[("selected", palette.tab_selected_bg)], foreground=[("selected", palette.text)])
