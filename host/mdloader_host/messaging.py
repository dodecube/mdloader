"""Chrome/Firefox native messaging wire protocol (4-byte length prefix + JSON)."""

from __future__ import annotations

import json
import logging
import struct
import sys
from typing import Any

log = logging.getLogger("mdloader")

_LENGTH = struct.Struct("@I")
MAX_MESSAGE_BYTES = 1024 * 1024  # Firefox refuses anything larger than 1 MiB.


def read_message() -> dict[str, Any] | None:
    """Read one message from stdin. Returns ``None`` when the browser closed the pipe."""
    raw_length = sys.stdin.buffer.read(_LENGTH.size)
    if len(raw_length) < _LENGTH.size:
        return None
    (length,) = _LENGTH.unpack(raw_length)
    if length == 0 or length > MAX_MESSAGE_BYTES:
        log.error("Refusing message of %d bytes", length)
        return None
    payload = sys.stdin.buffer.read(length)
    if len(payload) < length:
        log.error("Truncated message: expected %d bytes, got %d", length, len(payload))
        return None
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        log.exception("Could not decode incoming message")
        return None


def send_message(message: dict[str, Any]) -> None:
    """Write one message to stdout. Never raises — a broken pipe just ends the session."""
    encoded = json.dumps(message, ensure_ascii=False).encode("utf-8")
    if len(encoded) > MAX_MESSAGE_BYTES:
        encoded = json.dumps({"status": "error", "message": "Response too large"}).encode("utf-8")
    try:
        sys.stdout.buffer.write(_LENGTH.pack(len(encoded)))
        sys.stdout.buffer.write(encoded)
        sys.stdout.buffer.flush()
    except (BrokenPipeError, OSError):
        log.warning("stdout closed; browser disconnected")


def send_progress(message: str, progress: int | None = None) -> None:
    payload: dict[str, Any] = {"status": "progress", "message": message}
    if progress is not None:
        payload["progress"] = progress
    send_message(payload)


def send_error(message: str) -> None:
    send_message({"status": "error", "message": message})


def send_success(message: str) -> None:
    send_message({"status": "success", "message": message, "progress": 100})


def configure_logging() -> None:
    """Native hosts must keep stdout clean — all diagnostics go to stderr."""
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
