"""Packs the user downloaded themselves, kept in a local folder and searched alongside online sources."""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

from otohiroi import media
from otohiroi.records import guess_kind, license_terms, suspect_reason, words

AUDIO_SUFFIXES = {".wav", ".ogg", ".mp3", ".flac", ".m4a", ".aif", ".aiff"}
MAX_UNPACKED_BYTES = 4 * 1024 * 1024 * 1024
_CC0_TEXT = re.compile(r"creative commons zero|\bCC0\b|publicdomain/zero", re.IGNORECASE)
_NOT_WORD = re.compile(r"[^a-z0-9]+")


class LibraryError(Exception):
    pass


def home() -> Path:
    configured = os.environ.get("OTOHIROI_HOME")
    if configured:
        return Path(configured)
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "otohiroi"
    return Path.home() / ".local" / "share" / "otohiroi"


def packs_dir() -> Path:
    return home() / "packs"


def _slug(text: str) -> str:
    return _NOT_WORD.sub("-", text.lower()).strip("-") or "pack"


def _humanise(stem: str) -> str:
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", stem)
    return re.sub(r"[_\-.]+", " ", spaced).strip()


def _unzip(archive: Path, target: Path) -> None:
    with zipfile.ZipFile(archive) as bundle:
        members = bundle.infolist()
        if sum(m.file_size for m in members) > MAX_UNPACKED_BYTES:
            raise LibraryError("The archive unpacks to more than 4 GB.")
        root = target.resolve()
        for member in members:
            if not (root / member.filename).resolve().is_relative_to(root):
                raise LibraryError(f"Unsafe path in the archive: {member.filename}")
        bundle.extractall(target)


def _detect_licence(root: Path) -> str | None:
    for path in root.rglob("*"):
        if path.is_file() and path.stat().st_size < 200_000 and re.search(r"licen[sc]e|copying", path.name, re.I):
            if _CC0_TEXT.search(path.read_text(encoding="utf-8", errors="replace")):
                return "cc0"
    return None


def add_pack(path: str, name: str | None = None, license: str | None = None, commercial_use: bool | None = None,
             author: str | None = None, source_url: str | None = None, region: str | None = None,
             note: str | None = None) -> dict:
    source = Path(path).expanduser()
    if not source.is_absolute():
        raise LibraryError("Give an absolute path to the folder or .zip.")
    if not source.exists():
        raise LibraryError(f"{source} does not exist.")
    slug = _slug(name or source.stem)
    with tempfile.TemporaryDirectory() as temporary:
        staging = Path(temporary) / "files"
        if source.is_dir():
            shutil.copytree(source, staging)
        elif source.suffix.lower() == ".zip":
            _unzip(source, staging)
        elif source.suffix.lower() in AUDIO_SUFFIXES:
            staging.mkdir()
            shutil.copy2(source, staging / source.name)
        else:
            raise LibraryError("Expected a folder, a .zip or an audio file.")

        code = (license or _detect_licence(staging) or "").lower()
        if not code:
            raise LibraryError("No license file saying CC0 was found. Read the source's terms and pass license "
                               "(cc0, by, by-sa, or custom) yourself.")
        terms = license_terms(code)
        if code not in ("cc0", "pdm", "by", "by-sa"):
            if commercial_use is None:
                raise LibraryError(f"License {code!r} is not one Otohiroi can interpret. Pass commercial_use "
                                   "true or false, as stated by the source for this item.")
            terms["commercial_use"] = commercial_use

        files = sorted(p for p in staging.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_SUFFIXES
                       and "__MACOSX" not in p.parts)
        if not files:
            raise LibraryError("No audio files found there.")

        target = packs_dir() / slug
        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(staging), target)

    sounds = []
    pack_words = _humanise(name or source.stem)
    for index, original in enumerate(files):
        relative = original.relative_to(staging)
        title = _humanise(relative.stem)
        tags = sorted(words(pack_words, *[_humanise(part) for part in relative.parts[:-1]]))
        duration = media.duration_s(target / relative)
        sounds.append({
            "id": f"local:{slug}:{index}", "source": f"local/{slug}", "title": title, "author": author or "see pack",
            "kind": guess_kind(title, tags, duration, "local"), "duration_s": duration,
            "loop": True if "loop" in words(title, *tags) else None, "tags": tags, "license": code,
            "license_url": None, "landing_url": source_url, "preview_url": None, "path": relative.as_posix(),
            "region": region.upper() if region else None, "warning": suspect_reason(title, tags), "note": note,
            **terms,
        })
    (target / "otohiroi-pack.json").write_text(json.dumps({"name": name or source.stem, "sounds": sounds},
                                                          ensure_ascii=False, indent=1), encoding="utf-8")
    return {"pack": slug, "license": code, "sounds": len(sounds), "folder": str(target)}


def all_sounds() -> list[dict]:
    found = []
    if packs_dir().exists():
        for manifest in sorted(packs_dir().glob("*/otohiroi-pack.json")):
            found.extend(json.loads(manifest.read_text(encoding="utf-8"))["sounds"])
    return found


def search(queries: list[str]) -> list[dict]:
    wanted = words(*queries)
    scored = []
    for sound in all_sounds():
        title_words, tag_words = words(sound["title"]), words(*sound["tags"])
        score = 2 * len(wanted & title_words) + len(wanted & tag_words)
        if score:
            scored.append((score, sound))
    scored.sort(key=lambda pair: -pair[0])
    return [sound for _, sound in scored]


def get(sound_id: str) -> dict | None:
    return next((s for s in all_sounds() if s["id"] == sound_id), None)


def file_of(sound: dict) -> Path:
    pack = sound["id"].split(":")[1]
    root = (packs_dir() / pack).resolve()
    path = (root / sound["path"]).resolve()
    if not path.is_relative_to(root):
        raise LibraryError("The pack manifest points outside its folder.")
    return path


def list_packs() -> list[dict]:
    packs: dict[str, dict] = {}
    for sound in all_sounds():
        slug = sound["id"].split(":")[1]
        entry = packs.setdefault(slug, {"pack": slug, "license": sound["license"], "sounds": 0,
                                        "region": sound["region"], "source_url": sound["landing_url"]})
        entry["sounds"] += 1
    return list(packs.values())
