"""yt-dlp driver: builds the command, streams progress, classifies failures."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .config import Config
from .messaging import send_progress
from .naming import junk_metadata_regex
from .process import popen_stream, run

log = logging.getLogger("mdloader.downloader")

_PROGRESS_RE = re.compile(r"(\d+(?:\.\d+)?)%")
_ITEM_RE = re.compile(r"Downloading item (\d+) of (\d+)")


def _overall(index: int, total: int, percent: float) -> int:
    """Прогресс всего плейлиста: завершённые треки + доля текущего."""
    if total <= 0:
        return int(percent)
    done = max(index - 1, 0)
    return min(99, int((done + percent / 100) / total * 100))

# Matched against yt-dlp's ERROR lines, in order.
_ERROR_HINTS: tuple[tuple[str, str], ...] = (
    ("Video unavailable", "Видео недоступно или удалено"),
    ("Private video", "Видео приватное"),
    ("Sign in", "Требуется авторизация — включите cookies"),
    ("Unsupported URL", "Неподдерживаемый URL"),
    ("Too many requests", "YouTube ограничил частоту запросов, попробуйте позже"),
    ("HTTP Error 429", "YouTube ограничил частоту запросов, попробуйте позже"),
    ("is not a valid URL", "Некорректный URL"),
)


@dataclass
class DownloadResult:
    ok: bool
    message: str
    files: list[Path]
    folder: Path | None = None


def validate_url(url: str) -> tuple[bool, str]:
    """Accept ``ytsearch:`` queries and anything with a scheme + host."""
    url = (url or "").strip()
    if not url:
        return False, "Пустой URL"
    if url.startswith(("ytsearch:", "ytsearch1:", "ytsearch5:")):
        return True, url
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False, "Некорректный формат URL"
    return True, url


def probe_yt_dlp(config: Config) -> tuple[bool, str]:
    result = run([str(config.yt_dlp_path), "--version"], timeout=15)
    if result is None:
        return False, "yt-dlp не запускается — проверьте путь в config.json"
    if result.returncode != 0:
        return False, f"yt-dlp вернул ошибку: {result.stderr.strip()}"
    version = result.stdout.strip()
    log.info("yt-dlp %s", version)
    return True, version


def _classify(line: str) -> str | None:
    for needle, message in _ERROR_HINTS:
        if needle.lower() in line.lower():
            return message
    return None


# Плейлист складывается в подпапку: берём тег album, а если его нет —
# название плейлиста. Синтаксис "%(a,b|default)s" — штатный механизм
# альтернативных полей в yt-dlp.
PLAYLIST_TEMPLATE = "%(album,playlist_title,playlist|Unknown Album)s/%(title)s.%(ext)s"
TRACK_TEMPLATE = "%(title)s.%(ext)s"


def build_command(config: Config, url: str, use_cookies: bool, playlist: bool = False) -> list[str]:
    template = PLAYLIST_TEMPLATE if playlist else TRACK_TEMPLATE
    cmd = [
        str(config.yt_dlp_path),
        "--ignore-config",
        "-f", "bestaudio[ext=m4a]/bestaudio/best",
        "-x",
        "--audio-format", "mp3",
        "--audio-quality", "192K",
        "--embed-metadata",
        "--write-thumbnail",
        "--convert-thumbnails", "jpg",
        "--newline",
        "--progress",
        "--yes-playlist" if playlist else "--no-playlist",
        "--replace-in-metadata", "title", junk_metadata_regex(), "",
        "--ffmpeg-location", str(config.ffmpeg_dir),
        "-o", str(config.download_dir / template),
    ]
    if playlist:
        # Нумерация внутри альбома и продолжение при единичных сбоях.
        cmd += ["--parse-metadata", "%(playlist_index)s:%(track_number)s", "--ignore-errors"]
    if use_cookies:
        if config.cookies_path.exists():
            cmd += ["--cookies", str(config.cookies_path)]
            log.info("Using cookies from %s", config.cookies_path)
        else:
            log.warning("Cookies requested but %s is missing", config.cookies_path)
    cmd.append(url)
    return cmd


def download(config: Config, url: str, use_cookies: bool = False, playlist: bool = False) -> DownloadResult:
    """Run yt-dlp, relaying progress to the extension. Returns the new mp3 files."""
    config.download_dir.mkdir(parents=True, exist_ok=True)
    before = {p for p in config.download_dir.rglob("*.mp3")}

    process = popen_stream(build_command(config, url, use_cookies, playlist), cwd=config.download_dir)
    error_lines: list[str] = []
    friendly_error: str | None = None
    item_index = item_total = 0

    assert process.stdout is not None
    for raw_line in process.stdout:
        line = raw_line.strip()
        if not line:
            continue
        log.debug("yt-dlp: %s", line)

        item_match = _ITEM_RE.search(line)
        if item_match:
            item_index, item_total = int(item_match.group(1)), int(item_match.group(2))
            send_progress(f"📀 Трек {item_index} из {item_total}", _overall(item_index, item_total, 0))
            continue

        if "[download]" in line and "%" in line:
            match = _PROGRESS_RE.search(line)
            if match:
                percent = float(match.group(1))
                if item_total:
                    send_progress(
                        f"📥 Трек {item_index}/{item_total}: {percent:.0f}%",
                        _overall(item_index, item_total, percent),
                    )
                else:
                    send_progress(f"📥 Загрузка: {percent:.1f}%", int(20 + percent * 0.6))
        elif "Extracting URL" in line:
            send_progress("📥 Получение информации о видео...", 10)
        elif "[ExtractAudio]" in line or "[ffmpeg]" in line:
            send_progress("🔄 Конвертация в MP3...", 85)
        elif "[Metadata]" in line:
            send_progress("🏷️ Запись метаданных...", 92)

        if "ERROR:" in line:
            error_lines.append(line)
            friendly_error = friendly_error or _classify(line)

    returncode = process.wait()
    new_files = sorted(p for p in config.download_dir.rglob("*.mp3") if p not in before)
    folders = {f.parent for f in new_files if f.parent != config.download_dir}
    folder = next(iter(folders)) if len(folders) == 1 else None

    # --ignore-errors у плейлиста даёт ненулевой код, даже когда часть треков скачалась.
    if returncode == 0 or (playlist and new_files):
        suffix = f" ({len(new_files)} трек(ов))" if playlist else ""
        return DownloadResult(True, f"Загрузка завершена{suffix}", new_files, folder)

    message = friendly_error or ("\n".join(error_lines[-3:]) if error_lines else f"yt-dlp завершился с кодом {returncode}")
    return DownloadResult(False, message, new_files, folder)
