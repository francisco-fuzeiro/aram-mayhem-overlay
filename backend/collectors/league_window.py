"""Read-only Win32 locator for the actual League of Legends game window.

No screen pixels, input injection, file writes or League process manipulation.
The pure selector accepts an injected API so geometry/focus can be unit tested
without a Windows desktop session.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import PureWindowsPath
import sys


_GAME_EXE = "league of legends.exe"
_QUERY_LIMITED_INFORMATION = 0x1000


@dataclass(frozen=True)
class LeagueWindow:
    hwnd: int
    left: int
    top: int
    right: int
    bottom: int
    focused: bool

    @property
    def rect(self) -> tuple[int, int, int, int]:
        """(left, top, right, bottom) desktop physical-screen coordinates."""
        return self.left, self.top, self.right, self.bottom


class _NativeWin32:
    """Minimal read-only user32/kernel32 interface, instantiated on Windows."""

    def __init__(self) -> None:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self.user32, self.kernel32 = user32, kernel32
        self._enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows.argtypes = [self._enum_proc, wintypes.LPARAM]
        user32.EnumWindows.restype = wintypes.BOOL
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.IsWindowVisible.restype = wintypes.BOOL
        user32.IsIconic.argtypes = [wintypes.HWND]
        user32.IsIconic.restype = wintypes.BOOL
        user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        user32.GetClientRect.restype = wintypes.BOOL
        user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
        user32.ClientToScreen.restype = wintypes.BOOL
        user32.GetForegroundWindow.argtypes = []
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
        ]
        kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        user32.GetWindow.argtypes = [wintypes.HWND, ctypes.c_uint]
        user32.GetWindow.restype = wintypes.HWND
        user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        user32.GetWindowRect.restype = wintypes.BOOL
        self.dwmapi = ctypes.windll.dwmapi
        self.dwmapi.DwmGetWindowAttribute.argtypes = [
            wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
        ]
        self.dwmapi.DwmGetWindowAttribute.restype = wintypes.LONG
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

    def enumerate_windows(self) -> list[int]:
        windows: list[int] = []

        @self._enum_proc
        def collect(hwnd, _param):
            windows.append(int(hwnd))
            return True

        self.user32.EnumWindows(collect, 0)
        return windows

    def is_window_visible(self, hwnd: int) -> bool:
        return bool(self.user32.IsWindowVisible(hwnd))

    def is_minimized(self, hwnd: int) -> bool:
        return bool(self.user32.IsIconic(hwnd))

    def process_name(self, hwnd: int) -> str | None:
        pid = wintypes.DWORD()
        self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return None
        handle = self.kernel32.OpenProcess(_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return None
        try:
            path = ctypes.create_unicode_buffer(32768)
            length = wintypes.DWORD(len(path))
            if not self.kernel32.QueryFullProcessImageNameW(
                handle, 0, path, ctypes.byref(length)
            ):
                return None
            return PureWindowsPath(path.value).name
        finally:
            self.kernel32.CloseHandle(handle)

    def client_rect(self, hwnd: int) -> tuple[int, int, int, int] | None:
        rect = wintypes.RECT()
        if not self.user32.GetClientRect(hwnd, ctypes.byref(rect)):
            return None
        return rect.left, rect.top, rect.right, rect.bottom

    def client_to_screen(self, hwnd: int, point: tuple[int, int]) -> tuple[int, int] | None:
        win_point = wintypes.POINT(*point)
        if not self.user32.ClientToScreen(hwnd, ctypes.byref(win_point)):
            return None
        return win_point.x, win_point.y

    def foreground_window(self) -> int | None:
        return self.user32.GetForegroundWindow()

    def process_id(self, hwnd: int) -> int | None:
        """Owner PID for foreground classification and every z-order blocker."""
        pid = wintypes.DWORD()
        self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return int(pid.value) if pid.value else None

    def windows_above(self, hwnd: int) -> list[int]:
        """Walk GW_HWNDPREV, including layered/transparent top-level windows."""
        windows = []
        seen = {hwnd}
        current = hwnd
        for _ in range(1024):
            current = int(self.user32.GetWindow(current, 3) or 0)
            if not current:
                return windows
            if current in seen:
                raise OSError("invalid window z-order cycle")
            seen.add(current)
            windows.append(current)
        raise OSError("window z-order traversal exceeded safety bound")

    def window_rect(self, hwnd: int) -> tuple[int, int, int, int] | None:
        rect = wintypes.RECT()
        if not self.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return None
        return rect.left, rect.top, rect.right, rect.bottom

    def _dwm_attribute(self, hwnd: int, attribute: int, value) -> bool:
        return self.dwmapi.DwmGetWindowAttribute(
            hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value),
        ) == 0

    def frame_bounds(self, hwnd: int) -> tuple[int, int, int, int] | None:
        """WGC window-frame origin, not the client origin (DWM attribute 9)."""
        rect = wintypes.RECT()
        if not self._dwm_attribute(hwnd, 9, rect):
            return None
        return rect.left, rect.top, rect.right, rect.bottom

    def is_cloaked(self, hwnd: int) -> bool:
        """Unknown DWM state is not proof of safe fallback."""
        cloaked = wintypes.DWORD()
        if not self._dwm_attribute(hwnd, 14, cloaked):
            raise OSError("DWM cloak state cannot be verified")
        return bool(cloaked.value)


def find_league_window(
    *, win32=None, platform_name: str | None = None,
) -> LeagueWindow | None:
    """Find a visible, non-minimized real game executable and its client rect.

    Only executable identity qualifies: LeagueClientUx / launcher titles do not.
    No League window or unavailable/inaccessible Win32 API fails closed.
    Foreground game HWND wins if multiple candidates are present.
    """
    if (platform_name or sys.platform) != "win32":
        return None
    try:
        api = win32 if win32 is not None else _NativeWin32()
        foreground = api.foreground_window()
        candidates: list[LeagueWindow] = []
        for hwnd in api.enumerate_windows():
            try:
                if not api.is_window_visible(hwnd) or api.is_minimized(hwnd):
                    continue
                if (api.process_name(hwnd) or "").casefold() != _GAME_EXE:
                    continue
                rect = api.client_rect(hwnd)
                if rect is None:
                    continue
                l, t, r, b = rect
                if r <= l or b <= t:
                    continue
                origin = api.client_to_screen(hwnd, (l, t))
                corner = api.client_to_screen(hwnd, (r, b))
                if origin is None or corner is None:
                    continue
                left, top = origin
                right, bottom = corner
                if right <= left or bottom <= top:
                    continue
                candidates.append(LeagueWindow(
                    hwnd=int(hwnd), left=left, top=top, right=right,
                    bottom=bottom, focused=hwnd == foreground,
                ))
            except (OSError, ValueError, TypeError):
                continue
        return next((w for w in candidates if w.focused), candidates[0] if candidates else None)
    except (OSError, ValueError, TypeError, AttributeError):
        return None
