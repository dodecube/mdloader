"""Backwards-compatible entry point.

The implementation now lives in ``host/mdloader_host/``; this shim keeps any
existing native-host registration that points at ``msg.py`` working.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "host"))

from mdloader_host.host import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
