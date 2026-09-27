"""Filename and tag-string helpers (pure functions — easy to unit test)."""

from __future__ import annotations

import re

# Bracketed noise yt-dlp should strip from the title, e.g. "(Official Video)".
JUNK_WORDS = (
    "official",
    "lyrics",
    "video",
    "audio",
    "hd",
    "4k",
    "official video",
    "official audio",
    "lyric video",
    "remastered",
    "high res",
    "full video",
)

_FORBIDDEN_CHARS = re.compile(r'[<>:"/\\|?*]')
_DASHES = r"[-—–:]"
_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def junk_metadata_regex() -> str:
    """Regex passed to ``yt-dlp --replace-in-metadata title``."""
    pattern = "|".join(re.escape(word) for word in JUNK_WORDS)
    return rf" (?i)[(\[]({pattern})[)\]]"


def safe_filename(text: str, max_length: int = 200) -> str:
    """Make ``text`` usable as a Windows filename component."""
    if not text:
        return "Unknown"
    text = _FORBIDDEN_CHARS.sub(" ", text)
    text = "".join(ch for ch in text if ch.isprintable())
    text = re.sub(r"\s+", " ", text).strip()
    text = text.rstrip(". ")  # Windows cannot store trailing dots or spaces.
    if not text:
        return "Unknown"
    if text.upper() in _WINDOWS_RESERVED:
        text += "_res"
    return text[:max_length].strip()


def strip_artist_prefix(title: str, artist: str) -> str:
    """Turn ("Tame Impala - Breathe Deeper", "Tame Impala") into "Breathe Deeper"."""
    if not title or not artist:
        return title
    cleaned = re.sub(rf"^\s*{re.escape(artist)}\s*{_DASHES}\s*", "", title, flags=re.IGNORECASE).strip()
    return cleaned or title


def build_track_filename(artist: str, title: str, extension: str = ".mp3") -> str:
    """Compose ``Artist - Title.mp3``, or just ``Title.mp3`` when the artist is unknown."""
    clean_title = safe_filename(strip_artist_prefix(title, artist))
    if not artist or artist.strip().upper() in {"NA", "UNKNOWN ARTIST"}:
        return f"{clean_title}{extension}"
    return f"{safe_filename(artist)} - {clean_title}{extension}"
