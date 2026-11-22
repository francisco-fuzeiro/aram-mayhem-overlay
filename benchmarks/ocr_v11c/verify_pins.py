"""Verify exact pinned Python lab package versions from a real Python file.

Windows PowerShell 5.1 may remove quotes in a Python `-c` argument. Use a
script path and individual package spec arguments instead. Research only:
no model download, OCR inference, game access, or product dependencies.
"""
from __future__ import annotations

import importlib.metadata
import re
import sys

_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_VERSION = re.compile(r"^[0-9][A-Za-z0-9.!+_-]*$")


def _canonical(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def check_pins(pins: list[str], installed: dict[str, str] | None = None) -> list[str]:
    """Return actionable mismatches; malformed/duplicate pins always fail."""
    if not pins:
        raise ValueError("at least one exact pin is required")
    available = (None if installed is None else
                 {_canonical(k): v for k, v in installed.items()})
    seen: set[str] = set()
    errors = []
    for pin in pins:
        parts = pin.split("==")
        if len(parts) != 2 or not _NAME.fullmatch(parts[0]) or not _VERSION.fullmatch(parts[1]):
            raise ValueError("invalid exact pin: " + pin)
        name, expected = parts
        key = _canonical(name)
        if key in seen:
            raise ValueError("duplicate pinned package: " + name)
        seen.add(key)
        try:
            if available is None:
                actual = importlib.metadata.version(name)
            else:
                actual = available.get(key)
        except importlib.metadata.PackageNotFoundError:
            actual = None
        if actual is None:
            errors.append(f"{name}: missing (expected {expected})")
        elif actual != expected:
            errors.append(f"{name}: {actual} (expected {expected})")
    return errors


def main(argv: list[str] | None = None) -> int:
    try:
        errors = check_pins(sys.argv[1:] if argv is None else argv)
    except ValueError as exc:
        print("PIN_SPEC_ERROR " + str(exc), flush=True)
        return 2
    if errors:
        print("PIN_MISMATCH " + "; ".join(errors), flush=True)
        return 1
    print("PINNED_DEPS_OK", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
