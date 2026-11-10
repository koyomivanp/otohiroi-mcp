"""Audio processing through ffmpeg, when it is installed. Everything still works without it, minus conversion."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

ENCODERS = {".ogg": ["-c:a", "libvorbis", "-q:a", "6"], ".mp3": ["-c:a", "libmp3lame", "-q:a", "2"],
            ".wav": ["-c:a", "pcm_s16le"], ".flac": ["-c:a", "flac"]}
_TRIM = ("silenceremove=start_periods=1:start_threshold=-60dB,areverse,"
         "silenceremove=start_periods=1:start_threshold=-60dB,areverse")
SHORT_CLIP_S = 3.0  # loudness measurement needs a few seconds of audio; shorter clips are peak normalised
TIMEOUT_S = 300


def available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=TIMEOUT_S, stdin=subprocess.DEVNULL)


def duration_s(path: Path) -> float | None:
    if not available():
        return None
    done = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)])
    try:
        return round(float(json.loads(done.stdout)["format"]["duration"]), 3)
    except (ValueError, KeyError, json.JSONDecodeError):
        return None


def _max_volume_db(path: Path, trim: bool) -> float | None:
    filters = f"{_TRIM + ',' if trim else ''}volumedetect"
    done = _run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(path), "-af", filters, "-f", "null", "-"])
    match = re.search(r"max_volume:\s*(-?[\d.]+) dB", done.stderr)
    return float(match.group(1)) if match else None


def convert(source: Path, target: Path, trim: bool, loudness_lufs: float | None) -> None:
    filters = [_TRIM] if trim else []
    if loudness_lufs is not None:
        length = duration_s(source)
        if length is not None and length >= SHORT_CLIP_S:
            filters.append(f"loudnorm=I={loudness_lufs}:TP=-1.5:LRA=11")
        else:
            peak = _max_volume_db(source, trim)
            if peak is not None:
                filters.append(f"volume={-1.0 - peak:.2f}dB")
    args = ["ffmpeg", "-y", "-hide_banner", "-nostdin", "-i", str(source), "-vn", "-map_metadata", "-1"]
    if filters:
        args += ["-af", ",".join(filters)]
    args += ["-ar", "44100", *ENCODERS[target.suffix], str(target)]
    done = _run(args)
    if done.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {done.stderr[-400:]}")
