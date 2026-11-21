"""N1 regression: Qt WebEngine console callback must not crash the desktop.

Windows Actions does not install PyQt6 WebEngine. Extract the exact callback
from production source and run it with non-orderable Enum values that match
the PyQt6 JavaScriptConsoleMessageLevel behavior observed on Windows.
"""
from __future__ import annotations

import ast
from enum import Enum
from pathlib import Path
from unittest.mock import Mock


class _ConsoleLevel(Enum):
    InfoMessageLevel = 0
    WarningMessageLevel = 1
    ErrorMessageLevel = 2


class _QtPageStub:
    JavaScriptConsoleMessageLevel = _ConsoleLevel


def _actual_overlay_console_callback(logger):
    path = Path(__file__).resolve().parents[1] / "backend" / "overlay" / "window.py"
    module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    page = next(
        node for node in ast.walk(module)
        if isinstance(node, ast.ClassDef) and node.name == "OverlayPage"
    )
    callback = next(
        node for node in page.body
        if isinstance(node, ast.FunctionDef) and node.name == "javaScriptConsoleMessage"
    )
    isolated = ast.Module(body=[callback], type_ignores=[])
    namespace = {"QWebEnginePage": _QtPageStub, "logger": logger}
    exec(compile(isolated, str(path), "exec"), namespace)
    return namespace["javaScriptConsoleMessage"]


def test_n1_qt_console_levels_do_not_raise_and_only_log_errors():
    logger = Mock()
    callback = _actual_overlay_console_callback(logger)

    # A PyQt6 enum has equality/value semantics but no >= ordering.
    callback(None, _ConsoleLevel.InfoMessageLevel, "info", 3, "overlay.js")
    callback(None, _ConsoleLevel.WarningMessageLevel, "warning", 4, "overlay.js")
    logger.error.assert_not_called()

    callback(None, _ConsoleLevel.ErrorMessageLevel, "failure", 5, "overlay.js")
    logger.error.assert_called_once_with(
        "JS [%s:%d]: %s", "overlay.js", 5, "failure"
    )
