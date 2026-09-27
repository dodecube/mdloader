"""Post-processing: cover art, ID3 tags and final file naming."""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from PIL import Image

from .config import Config
from .naming import build_track_filename, strip_artist_prefix
from .process import run

log = logging.getLogger("mdloader.media")

TEMP_SUFFIXES = (".webp", ".webm", ".part", ".temp", ".jpg", ".ytdl")


def read_tags(config: Config, media_path: Path) -> dict[str, str]:
    """Return the ID3/format tags of ``media_path`` (empty dict when unreadable)."""
    cmd = [
        str(config.ffprobe_bin),
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        str(media_path),
    ]
    for encoding in ("utf-8", "cp1251"):
        result = run(cmd, timeout=30, encoding=encoding)
        if result is None or result.returncode != 0:
            continue
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            continue
        tags = payload.get("format", {}).get("tags") or {}
        # ffprobe tag case is inconsistent between muxers; normalise to lowercase.
        return {str(key).lower(): str(value) for key, value in tags.items()}
    log.warning("Could not read tags from %s", media_path.name)
    return {}


def crop_to_square(image_path: Path) -> bool:
    """Centre-crop a thumbnail so players show a square cover."""
    try:
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            width, height = img.size
            size = min(width, height)
            left = (width - size) // 2
            top = (height - size) // 2
            cropped = img.crop((left, top, left + size, top + size))
        cropped.save(image_path, "JPEG", quality=95)
        return True
    except (OSError, ValueError) as exc:
        log.warning("Pillow could not crop %s: %s", image_path.name, exc)
        return False


def _remux(config: Config, mp3_path: Path, extra_args: list[str], inputs: list[str]) -> bool:
    """Run ffmpeg into a temp file and atomically replace the original on success."""
    temp_output = mp3_path.with_suffix(mp3_path.suffix + ".tmp.mp3")
    cmd = [str(config.ffmpeg_bin), "-y", "-i", str(mp3_path), *inputs, *extra_args, str(temp_output)]
    result = run(cmd, timeout=60)
    if result is not None and result.returncode == 0 and temp_output.exists():
        temp_output.replace(mp3_path)
        return True
    if result is not None and result.returncode != 0:
        log.warning("ffmpeg failed for %s: %s", mp3_path.name, (result.stderr or "").strip()[-400:])
    temp_output.unlink(missing_ok=True)
    return False


def embed_thumbnail(config: Config, mp3_path: Path, thumbnail_path: Path) -> bool:
    return _remux(
        config,
        mp3_path,
        extra_args=[
            "-c", "copy",
            "-map", "0",
            "-map", "1",
            "-id3v2_version", "3",
            "-metadata:s:v", "title=Album cover",
            "-metadata:s:v", "comment=Cover (front)",
            "-disposition:v", "attached_pic",
        ],
        inputs=["-i", str(thumbnail_path)],
    )


def clean_title_tag(config: Config, mp3_path: Path) -> bool:
    """Drop a duplicated ``Artist - `` prefix from the ID3 title tag."""
    tags = read_tags(config, mp3_path)
    artist = tags.get("artist", "").strip()
    title = tags.get("title", "").strip()
    if not artist or not title or artist.upper() == "NA":
        return False
    new_title = strip_artist_prefix(title, artist)
    if new_title == title:
        return False
    ok = _remux(
        config,
        mp3_path,
        extra_args=[
            "-map", "0",
            "-c", "copy",
            "-id3v2_version", "3",
            "-metadata", f"title={new_title}",
            "-metadata", f"artist={artist}",
        ],
        inputs=[],
    )
    if ok:
        log.info("Cleaned ID3 title: %r -> %r", title, new_title)
    return ok


def unique_path(path: Path) -> Path:
    """``Track.mp3`` -> ``Track (1).mp3`` when the target already exists."""
    if not path.exists():
        return path
    stem, parent, suffix = path.stem, path.parent, path.suffix
    for counter in range(1, 1000):
        candidate = parent / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"Could not find a free filename for {path}")


def rename_from_tags(config: Config, mp3_path: Path) -> Path:
    """Rename to ``Artist - Title.mp3``; returns the (possibly unchanged) path."""
    tags = read_tags(config, mp3_path)
    artist = tags.get("artist", "").strip()
    title = tags.get("title", "").strip() or mp3_path.stem
    new_name = build_track_filename(artist, title)
    if new_name == mp3_path.name:
        return mp3_path
    target = unique_path(mp3_path.with_name(new_name))
    try:
        mp3_path.rename(target)
    except OSError as exc:
        log.warning("Rename failed for %s: %s", mp3_path.name, exc)
        return mp3_path
    log.info("Renamed %s -> %s", mp3_path.name, target.name)
    return target


def process_downloads(config: Config, mp3_files: list[Path]) -> None:
    """Embed covers, tidy tags and rename — only for the files we just downloaded."""
    for mp3_path in mp3_files:
        if not mp3_path.exists():
            continue
        try:
            thumbnail = mp3_path.with_suffix(".jpg")
            if thumbnail.exists() and crop_to_square(thumbnail):
                embed_thumbnail(config, mp3_path, thumbnail)
            thumbnail.unlink(missing_ok=True)
            clean_title_tag(config, mp3_path)
            rename_from_tags(config, mp3_path)
        except Exception:  # noqa: BLE001 - one bad file must not kill the batch
            log.exception("Post-processing failed for %s", mp3_path.name)


def cleanup(download_dir: Path) -> int:
    """Remove leftover thumbnails and partial downloads."""
    removed = 0
    for entry in download_dir.iterdir():
        if entry.is_file() and entry.suffix.lower() in TEMP_SUFFIXES:
            try:
                entry.unlink()
                removed += 1
            except OSError as exc:
                log.warning("Could not remove %s: %s", entry.name, exc)
    log.info("Cleanup removed %d file(s)", removed)
    return removed
