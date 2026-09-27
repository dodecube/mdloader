"""Thin ``subprocess`` wrappers that never leak a console window on Windows."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

log = logging.getLogger("mdloader.process")

# Without this every yt-dlp/ffmpeg call would flash a console window,
# because the native host itself is started by the browser without one.
_NO_WINDOW = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}


def run(
    cmd: list[str],
    *,
    timeout: int = 60,
    encoding: str = "utf-8",
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str] | None:
    """Run ``cmd`` to completion. Returns ``None`` on timeout or a missing binary."""
    log.debug("run: %s", " ".join(cmd))
    try:
        return subprocess.run(  # noqa: S603 - argument list is built from config, never a shell string
            cmd,
            capture_output=True,
            text=True,
            encoding=encoding,
            errors="replace",
            timeout=timeout,
            cwd=str(cwd) if cwd else None,
            check=False,
            **_NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        log.error("Timed out after %ss: %s", timeout, cmd[0])
    except (FileNotFoundError, OSError) as exc:
        log.error("Could not start %s: %s", cmd[0], exc)
    return None


def popen_stream(cmd: list[str], cwd: Path | None = None) -> subprocess.Popen[str]:
    """Start ``cmd`` with stdout+stderr merged into one line-buffered stream."""
    log.debug("popen: %s", " ".join(cmd))
    return subprocess.Popen(  # noqa: S603
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        cwd=str(cwd) if cwd else None,
        **_NO_WINDOW,
    )
