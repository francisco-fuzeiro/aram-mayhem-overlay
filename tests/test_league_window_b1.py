"""M4/B1: Windows game-window selection and client-area coordinates (AUD-02a)."""
from dataclasses import dataclass

import pytest

from backend.collectors.league_window import LeagueWindow, find_league_window


@dataclass
class FakeWindow:
    process: str
    rect: tuple[int, int, int, int]
    origin: tuple[int, int]
    visible: bool = True
    minimized: bool = False


class FakeWin32:
    def __init__(self, windows, foreground=None):
        self.windows = windows
        self.foreground = foreground

    def enumerate_windows(self):
        return list(self.windows)

    def is_window_visible(self, hwnd):
        return self.windows[hwnd].visible

    def is_minimized(self, hwnd):
        return self.windows[hwnd].minimized

    def process_name(self, hwnd):
        return self.windows[hwnd].process

    def client_rect(self, hwnd):
        return self.windows[hwnd].rect

    def client_to_screen(self, hwnd, point):
        ox, oy = self.windows[hwnd].origin
        return ox + point[0], oy + point[1]

    def foreground_window(self):
        return self.foreground


def test_no_win32_api_used_on_other_platforms():
    assert find_league_window(platform_name="linux") is None


def test_windowed_client_area_ignores_titlebar_and_borders():
    win = FakeWin32({
        8: FakeWindow("League of Legends.exe", (0, 0, 1280, 720), (108, 139)),
    }, foreground=8)
    assert find_league_window(win32=win, platform_name="win32") == LeagueWindow(
        hwnd=8, left=108, top=139, right=1388, bottom=859, focused=True
    )


def test_borderless_client_matches_desktop_without_border_offset():
    win = FakeWin32({
        9: FakeWindow("League of Legends.exe", (0, 0, 2560, 1440), (0, 0)),
    }, foreground=9)
    result = find_league_window(win32=win, platform_name="win32")
    assert result is not None
    assert result.rect == (0, 0, 2560, 1440)


def test_negative_origin_on_secondary_monitor_is_preserved():
    win = FakeWin32({
        4: FakeWindow("League of Legends.exe", (0, 0, 1920, 1080), (-1920, -80)),
    }, foreground=17)
    result = find_league_window(win32=win, platform_name="win32")
    assert result is not None
    assert result.rect == (-1920, -80, 0, 1000)
    assert result.focused is False


@pytest.mark.parametrize("windows", [
    {},
    {3: FakeWindow("League of Legends.exe", (0, 0, 1920, 1080), (0, 0), minimized=True)},
    {3: FakeWindow("League of Legends.exe", (0, 0, 1920, 1080), (0, 0), visible=False)},
    {3: FakeWindow("League of Legends.exe", (0, 0, 0, 1080), (0, 0))},
    {3: FakeWindow("LeagueClientUx.exe", (0, 0, 1920, 1080), (0, 0))},
])
def test_missing_minimized_hidden_invalid_or_client_only_returns_none(windows):
    assert find_league_window(win32=FakeWin32(windows), platform_name="win32") is None


def test_real_game_executable_wins_over_similar_window_titles():
    win = FakeWin32({
        1: FakeWindow("LeagueClientUx.exe", (0, 0, 1920, 1080), (0, 0)),
        2: FakeWindow("League of Legends.exe", (0, 0, 1920, 1080), (30, 40)),
    }, foreground=1)
    result = find_league_window(win32=win, platform_name="win32")
    assert result is not None and result.hwnd == 2 and not result.focused
