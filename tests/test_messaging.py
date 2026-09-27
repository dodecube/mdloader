import io
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "host"))

from mdloader_host import messaging


class FakeStdIn:
    def __init__(self, data: bytes):
        self.buffer = io.BytesIO(data)


class FakeStdOut:
    def __init__(self):
        self.buffer = io.BytesIO()


def encode(payload: dict) -> bytes:
    body = json.dumps(payload).encode("utf-8")
    return struct.pack("@I", len(body)) + body


def test_roundtrip(monkeypatch):
    monkeypatch.setattr(sys, "stdin", FakeStdIn(encode({"action": "download", "url": "u"})))
    assert messaging.read_message() == {"action": "download", "url": "u"}


def test_read_returns_none_on_closed_pipe(monkeypatch):
    monkeypatch.setattr(sys, "stdin", FakeStdIn(b""))
    assert messaging.read_message() is None


def test_read_rejects_oversized_header(monkeypatch):
    monkeypatch.setattr(sys, "stdin", FakeStdIn(struct.pack("@I", messaging.MAX_MESSAGE_BYTES + 1)))
    assert messaging.read_message() is None


def test_read_handles_truncated_body(monkeypatch):
    monkeypatch.setattr(sys, "stdin", FakeStdIn(struct.pack("@I", 100) + b"short"))
    assert messaging.read_message() is None


def test_send_message_is_length_prefixed(monkeypatch):
    out = FakeStdOut()
    monkeypatch.setattr(sys, "stdout", out)
    messaging.send_message({"status": "success", "message": "готово"})
    raw = out.buffer.getvalue()
    (length,) = struct.unpack("@I", raw[:4])
    assert length == len(raw) - 4
    assert json.loads(raw[4:].decode("utf-8"))["message"] == "готово"
