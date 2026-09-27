import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "host"))

import pytest

from mdloader_host.naming import build_track_filename, safe_filename, strip_artist_prefix


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('a<b>c:d"e/f\\g|h?i*j', "a b c d e f g h i j"),
        ("  spaced  out  ", "spaced out"),
        ("CON", "CON_res"),
        ("", "Unknown"),
        ("trailing dots...", "trailing dots"),
    ],
)
def test_safe_filename(raw, expected):
    assert safe_filename(raw) == expected


def test_safe_filename_truncates():
    assert len(safe_filename("x" * 500)) == 200


@pytest.mark.parametrize(
    ("title", "artist", "expected"),
    [
        ("Tame Impala - Breathe Deeper", "Tame Impala", "Breathe Deeper"),
        ("Tame Impala — Breathe Deeper", "Tame Impala", "Breathe Deeper"),
        ("tame impala: Breathe Deeper", "Tame Impala", "Breathe Deeper"),
        ("Breathe Deeper", "Tame Impala", "Breathe Deeper"),
        ("Tame Impala", "Tame Impala", "Tame Impala"),  # never blank out the title
    ],
)
def test_strip_artist_prefix(title, artist, expected):
    assert strip_artist_prefix(title, artist) == expected


def test_build_track_filename():
    assert build_track_filename("Tame Impala", "Tame Impala - Breathe Deeper") == "Tame Impala - Breathe Deeper.mp3"
    assert build_track_filename("", "Some Track") == "Some Track.mp3"
    assert build_track_filename("NA", "Some Track") == "Some Track.mp3"
