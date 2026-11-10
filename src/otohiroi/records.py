"""The sound record every source produces, and the checks that apply to all of them."""
from __future__ import annotations

import re

LICENSES = {
    # code: (commercial use, credit required, share-alike)
    "cc0": (True, False, False),
    "pdm": (True, False, False),
    "by": (True, True, False),
    "by-sa": (True, True, True),
}
MUSIC_WORDS = {"music", "bgm", "soundtrack", "song", "melody", "orchestral", "instrumental", "jingle", "chiptune",
               "chiptunes", "bpm"}
AMBIENCE_WORDS = {"ambience", "ambiance", "ambient", "atmosphere", "atmos", "drone", "soundscape", "background"}

# "CC0" is whatever the uploader declared. These names suggest the audio was taken from someone else's work.
_SUSPECT = re.compile(
    r"final fantasy|dragon quest|mario|zelda|sonic the|pok[eé]mon|nintendo|sega|capcom|street fighter|"
    r"star wars|lightsaber|minecraft|fortnite|disney|marvel|naruto|dragon ?ball|one piece|gundam|evangelion|ghibli|"
    r"ripped|\bfrom the (movie|game|film)\b",
    re.IGNORECASE,
)


SYNTHETIC_WORDS = {"beep", "bleep", "blip", "synth", "synthesized", "synthesizer", "8bit", "chiptune", "chip", "retro",
                   "arcade", "sfxr", "bfxr", "electronic", "digital", "computer", "generated"}


def words(*texts) -> set[str]:
    return {w for text in texts for w in re.findall(r"[^\W_]+", str(text).lower())}


def sounds_synthetic(record: dict) -> bool:
    return bool(words(record["title"], *record["tags"]) & SYNTHETIC_WORDS)


def guess_kind(title: str, tags: list[str], duration_s: float | None, source: str) -> str:
    if source == "jamendo":
        return "music"
    found = words(title, *tags)
    long_enough = duration_s is None or duration_s >= 6
    if long_enough and found & MUSIC_WORDS:
        return "music"
    if (duration_s is None or duration_s >= 10) and found & AMBIENCE_WORDS:
        return "ambience"
    return "sfx"


def suspect_reason(title: str, tags: list[str]) -> str | None:
    match = _SUSPECT.search(" ".join([title, *tags]))
    if match is None:
        return None
    return (f"The name mentions {match.group(0)!r}. Licenses here are declared by uploaders, so this may be "
            "someone else's audio. Have a human check it before shipping.")


def license_terms(code: str) -> dict:
    commercial, credit, share_alike = LICENSES.get(code, (False, True, False))
    return {"commercial_use": commercial, "credit_required": credit, "share_alike": share_alike}


def matches_license(record: dict, mode: str) -> bool:
    if mode == "cc0":
        return record["license"] in ("cc0", "pdm")
    if mode == "commercial":
        return record["commercial_use"] is True
    return True


def matches_filters(record: dict, kind: str | None, min_seconds: float | None, max_seconds: float | None,
                    loop_only: bool) -> bool:
    if kind and record["kind"] != kind:
        return False
    duration = record.get("duration_s")
    if (min_seconds is not None or max_seconds is not None) and duration is None:
        return False
    if min_seconds is not None and duration < min_seconds:
        return False
    if max_seconds is not None and duration > max_seconds:
        return False
    return not loop_only or record.get("loop") is True
