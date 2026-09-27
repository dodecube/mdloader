"""Runtime configuration for the mdloader native host.

Paths are resolved in this order (first hit wins):

1. environment variables ``MDLOADER_DOWNLOAD_DIR`` / ``MDLOADER_YT_DLP`` /
   ``MDLOADER_FFMPEG_DIR`` / ``MDLOADER_COOKIES``;
2. ``config.json`` next to the repository root (gitignored, user specific);
3. ``config.example.json`` shipped with the repository.

Keeping the paths out of the source means the machine specific ``E:/home/...``
layout never has to be committed again.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
USER_CONFIG = REPO_ROOT / "config.json"
EXAMPLE_CONFIG = REPO_ROOT / "config.example.json"

_ENV_MAP = {
    "download_dir": "MDLOADER_DOWNLOAD_DIR",
    "yt_dlp_path": "MDLOADER_YT_DLP",
    "ffmpeg_dir": "MDLOADER_FFMPEG_DIR",
    "cookies_path": "MDLOADER_COOKIES",
}

_EXE_SUFFIX = ".exe" if os.name == "nt" else ""


@dataclass(frozen=True)
class Config:
    """Resolved paths used by the downloader."""

    download_dir: Path
    yt_dlp_path: Path
    ffmpeg_dir: Path
    cookies_path: Path

    @property
    def ffmpeg_bin(self) -> Path:
        return self.ffmpeg_dir / f"ffmpeg{_EXE_SUFFIX}"

    @property
    def ffprobe_bin(self) -> Path:
        return self.ffmpeg_dir / f"ffprobe{_EXE_SUFFIX}"

    def missing_dependencies(self) -> list[str]:
        """Return human readable messages for every missing required path."""
        checks = {
            "yt-dlp": self.yt_dlp_path,
            "ffmpeg": self.ffmpeg_bin,
            "ffprobe": self.ffprobe_bin,
        }
        missing = [f"{name} not found at: {path}" for name, path in checks.items() if not path.exists()]
        if not self.download_dir.exists():
            try:
                self.download_dir.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                missing.append(f"download_dir cannot be created at {self.download_dir}: {exc}")
        return missing


def _read_json(path: Path) -> dict:
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc


def load_config() -> Config:
    data = _read_json(EXAMPLE_CONFIG)
    data.update(_read_json(USER_CONFIG))
    for key, env_var in _ENV_MAP.items():
        value = os.environ.get(env_var)
        if value:
            data[key] = value

    missing_keys = [key for key in _ENV_MAP if not data.get(key)]
    if missing_keys:
        raise SystemExit(
            "Missing configuration keys: "
            + ", ".join(missing_keys)
            + f"\nCopy {EXAMPLE_CONFIG.name} to config.json and fill in the paths."
        )

    return Config(
        download_dir=Path(data["download_dir"]),
        yt_dlp_path=Path(data["yt_dlp_path"]),
        ffmpeg_dir=Path(data["ffmpeg_dir"]),
        cookies_path=Path(data["cookies_path"]),
    )
