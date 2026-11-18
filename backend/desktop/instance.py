"""Single-user ARAM Oracle process lock and authenticated local activation channel.

The lock file is never removed: unlinking a lock inode allows competing owners.
An expired/crashed owner releases the OS lock automatically. Only a lock holder
may publish or remove the per-user activation descriptor.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import queue
import secrets
import socket
import sys
import threading
import time

logger = logging.getLogger("aram-oracle.desktop")
ACTIONS = frozenset({"settings", "overlay"})


def _lock(handle) -> None:
    handle.seek(0)
    if sys.platform == "win32":
        import msvcrt
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock(handle) -> None:
    handle.seek(0)
    if sys.platform == "win32":
        import msvcrt
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class InstanceGate:
    """Own one app and forward subsequent launches to its UI thread via a queue."""

    def __init__(self, directory: Path | None = None):
        self.directory = directory or (Path.home() / ".aram-oracle")
        self.lock_path = self.directory / "desktop-instance.lock"
        self.info_path = self.directory / "desktop-instance.json"
        self._handle = None
        self._listener = None
        self._thread = None
        self._token = None
        self.commands: queue.Queue[str] = queue.Queue()
        self._closing = threading.Event()

    def acquire(self) -> bool:
        """Return False for a live owner; never steal its lock or delete its file."""
        self.directory.mkdir(parents=True, exist_ok=True)
        handle = self.lock_path.open("a+b")
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        try:
            _lock(handle)
        except (OSError, BlockingIOError):
            handle.close()
            return False
        self._handle = handle
        return True

    def listen(self) -> None:
        """Publish a ready activation endpoint while holding the OS lock."""
        if self._handle is None:
            raise RuntimeError("Cannot advertise an instance without owning its lock")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(("127.0.0.1", 0))
            sock.listen(4)
            sock.settimeout(0.2)
            self._token = secrets.token_hex(32)
            self._listener = sock
            self._closing.clear()
            self._thread = threading.Thread(
                target=self._serve, name="aram-oracle-activation", daemon=True
            )
            self._thread.start()
            descriptor = {"port": sock.getsockname()[1], "token": self._token,
                          "pid": os.getpid()}
            temporary = self.info_path.with_suffix(".tmp")
            try:
                with temporary.open("w", encoding="utf-8") as output:
                    json.dump(descriptor, output)
                if sys.platform != "win32":
                    os.chmod(temporary, 0o600)
                os.replace(temporary, self.info_path)
            finally:
                temporary.unlink(missing_ok=True)
        except BaseException:
            sock.close()
            self._closing.set()
            raise

    def _serve(self) -> None:
        listener = self._listener
        while not self._closing.is_set():
            try:
                client, _address = listener.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with client:
                client.settimeout(1)
                try:
                    request = client.recv(2048)
                    command = json.loads(request.decode("utf-8"))
                    if (isinstance(command, dict)
                            and secrets.compare_digest(
                                str(command.get("token", "")), self._token or ""
                            )
                            and command.get("action") in ACTIONS):
                        self.commands.put(command["action"])
                        client.sendall(b"ok\n")
                    else:
                        client.sendall(b"denied\n")
                except (OSError, UnicodeError, ValueError, TypeError):
                    logger.debug("Ignoring invalid local activation request")

    def forward(self, action: str, timeout: float = 20.0) -> bool:
        """Ask a primary process to show Settings/overlay during startup races."""
        if action not in ACTIONS:
            raise ValueError("Unsupported activation action")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                descriptor = json.loads(self.info_path.read_text(encoding="utf-8"))
                port = descriptor["port"]
                token = descriptor["token"]
                if not isinstance(port, int) or not 1 <= port <= 65535:
                    raise ValueError("Invalid activation port")
                if not isinstance(token, str):
                    raise ValueError("Invalid activation token")
                with socket.create_connection(("127.0.0.1", port), timeout=0.25) as sock:
                    sock.settimeout(0.25)
                    sock.sendall(json.dumps({"token": token, "action": action}).encode("utf-8"))
                    if sock.recv(64).strip() == b"ok":
                        return True
            except (OSError, KeyError, ValueError, TypeError, json.JSONDecodeError):
                pass
            time.sleep(0.1)
        return False

    def drain(self) -> list[str]:
        actions = []
        while True:
            try:
                actions.append(self.commands.get_nowait())
            except queue.Empty:
                return actions

    def close(self) -> None:
        """Drop activation before releasing the lock; safe after partial startup."""
        self._closing.set()
        if self._listener is not None:
            self._listener.close()
            self._listener = None
        if self._thread is not None:
            self._thread.join(timeout=1)
            self._thread = None
        if self._handle is not None:
            try:
                descriptor = json.loads(self.info_path.read_text(encoding="utf-8"))
                if descriptor.get("token") == self._token:
                    self.info_path.unlink(missing_ok=True)
            except (OSError, ValueError, TypeError):
                pass
            try:
                _unlock(self._handle)
            finally:
                self._handle.close()
                self._handle = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()
