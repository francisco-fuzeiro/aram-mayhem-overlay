"""Read-only, best-effort League HUD scale detection from the game executable.

No client files are modified. Bad or missing configuration fails to conservative
default scales and carries an explicit confidence marker.
"""
from __future__ import annotations

import configparser
import ctypes
from ctypes import wintypes
import math
from pathlib import Path
import sys

from backend.overlay.hud_zones import HudScales

_QUERY_LIMITED_INFORMATION = 0x1000


def executable_path_for_hwnd(hwnd: int) -> str | None:
    """Resolve only the game's own HWND -> PID -> executable path on Windows."""
    if sys.platform != "win32" or not hwnd:
        return None
    handle = None
    try:
        user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
        ]
        kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return None
        handle = kernel32.OpenProcess(_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return None
        path = ctypes.create_unicode_buffer(32768)
        length = wintypes.DWORD(len(path))
        if not kernel32.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(length)):
            return None
        return path.value
    except (OSError, ValueError, AttributeError, TypeError):
        return None
    finally:
        if handle:
            kernel32.CloseHandle(handle)


def read_hud_scales(exe_path: str | Path | None) -> HudScales:
    """Read [HUD] GlobalScale and MinimapScale; clamp raw cfg values.

    Both keys must be present and finite. No partial scale configurations are
    trusted; fallback carries confidence='default'. Formulae are provisional.
    """
    if not exe_path:
        return HudScales()
    try:
        cfg = Path(exe_path).parent.parent / "Config" / "game.cfg"
        parser = configparser.ConfigParser(interpolation=None, strict=False)
        with cfg.open("r", encoding="utf-8-sig") as source:
            parser.read_file(source)
        hud = parser.getfloat("HUD", "GlobalScale")
        minimap = parser.getfloat("HUD", "MinimapScale")
        if not (math.isfinite(hud) and math.isfinite(minimap)):
            raise ValueError("invalid HUD scales")
        return HudScales(
            hud=max(0.0, min(1.0, hud)),
            minimap=max(0.0, min(3.0, minimap)),
            confidence="game_cfg",
        )
    except (OSError, ValueError, TypeError, configparser.Error):
        return HudScales()
