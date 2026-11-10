"""The Otohiroi MCP server (stdio) and a small command line."""
from __future__ import annotations

import argparse
import json
import sys
from typing import Literal

from mcp.server import MCPServer

from otohiroi import __version__, audition, dictionary, elsewhere, fetch as fetching, freesound, library, net, openverse, scan, studio
from otohiroi.records import matches_filters, matches_license, sounds_synthetic, words

INSTRUCTIONS = """\
Otohiroi finds openly licensed sound effects and BGM for games, lets a human choose by ear, and puts the
chosen files in the project with their license on record.

How to work:
- Search in English, 1-3 keywords, the main noun last. Every word must match, so fewer is better. Translate other
  languages first, and describe the sound itself ("sword hit", not "the sound for when an enemy gets hurt").
  Put other wordings and moods in `alternatives` ("calm chiptune", "relaxing 8bit").
- To improve a game's beeps, start with open_sound_studio on its folder. It detects the sounds and opens a page where
  the user ticks sounds, picks synthesised replacements by ear and applies them to the game (with undo).
  After they apply, tell them to reload the game and judge by ear. You cannot confirm how it sounds.
- find_replacements instead lists real recordings for each sound, to use or to learn from. scan_game gives just the list.
- suggest_search turns a game event or Japanese sound word (シュッ, ぽよん) into searches that work.
- You cannot hear audio. Do not pick by title alone: send the best candidates to audition_sounds and let the
  user tell you the numbers they like. Then call fetch_sound.
- If fetch_sound returns manual_download_needed, pass the page link and the reason to the user.
- Results with `warning` may be someone else's audio despite their license. Tell the user.
- Licenses are declared by uploaders and are not legal advice. Say so when the user is about to ship.
- find_elsewhere gives search links for libraries Otohiroi must not crawl, such as Niconi Commons and the YouTube
  Audio Library. Give the links and their `check` text to the user. Never scrape or download from those sites.
"""

Kind = Literal["sfx", "music", "ambience"]
LicenseMode = Literal["cc0", "commercial", "any"]
Source = Literal["freesound", "jamendo", "wikimedia_audio", "local"]

server = MCPServer("otohiroi", instructions=INSTRUCTIONS)
_seen: dict[str, dict] = {}  # records from this session, so a chosen id does not cost another API call


def _public(sound: dict) -> dict:
    short = {k: sound.get(k) for k in ("id", "title", "kind", "duration_s", "loop", "license", "commercial_use",
                                       "credit_required", "source", "author", "warning", "region")}
    return {k: v for k, v in short.items() if v is not None}


def _lookup(sound_id: str) -> dict:
    if sound_id in _seen:
        return _seen[sound_id]
    if sound_id.startswith("local:"):
        sound = library.get(sound_id)
    elif sound_id.startswith("openverse:"):
        sound = openverse.get(sound_id.split(":", 1)[1])
    else:
        sound = None
    if sound is None:
        raise ValueError(f"No sound {sound_id!r}. Use an id from search_sounds.")
    _seen[sound_id] = sound
    return sound


def _interleave(groups: list[list[dict]]) -> list[dict]:
    merged: dict[str, dict] = {}
    for index in range(max(map(len, groups), default=0)):
        for group in groups:
            if index < len(group):
                merged.setdefault(group[index]["id"], group[index])
    return list(merged.values())


def _search_online(text: str, license: str, source: str | None, page: int, notes: list[str]) -> list[dict]:
    """Openverse requires every word to match, so an empty result is retried without the leading modifiers."""
    terms = text.split()
    while True:
        results = openverse.search(" ".join(terms), license, source, page)
        if results or len(terms) <= 1:
            break
        terms = terms[1:]
    if results and " ".join(terms) != " ".join(text.split()):
        notes.append(f"Nothing matched {text!r}, so these results are for {' '.join(terms)!r}.")
    return results


@server.tool()
def search_sounds(query: str, alternatives: list[str] | None = None, kind: Kind | None = None,
                  license: LicenseMode = "cc0", min_seconds: float | None = None, max_seconds: float | None = None,
                  loop_only: bool = False, source: Source | None = None, limit: int = 10, page: int = 1,
                  natural_only: bool = False) -> dict:
    """Search sound effects and BGM by English keywords across online indexes and packs added with add_pack.

    license: cc0 = no conditions (default); commercial = also CC BY / BY-SA, which need credit; any = everything,
    including non-commercial. natural_only leaves out sounds described as beeps, synths or 8-bit.
    Results are short; use audition_sounds to let the user listen.
    """
    queries = [query, *(alternatives or [])][:3]
    limit = max(1, min(limit, 20))
    notes: list[str] = []
    groups: list[list[dict]] = []
    if source in (None, "local") and page == 1:
        groups.append(library.search(queries))
    if source != "local":
        for text in queries:
            try:
                groups.append(_search_online(text, license, source, max(1, min(page, 12)), notes))
            except net.NetError as error:
                notes.append(f"Online search failed for {text!r}: {error}")
    candidates = [s for s in _interleave(groups) if matches_license(s, license)
                  and matches_filters(s, kind, min_seconds, max_seconds, loop_only)
                  and not (natural_only and sounds_synthetic(s))]
    candidates.sort(key=lambda s: s.get("warning") is not None)  # sort is stable: relevance stays otherwise
    results = candidates[:limit]
    _seen.update({s["id"]: s for s in results})
    if not results:
        notes.append("Nothing matched. Try other words, fewer filters, or find_elsewhere for libraries to open by hand.")
    return {"results": [_public(s) for s in results], "matched": len(candidates), "notes": notes}


@server.tool()
def get_sound(sound_id: str) -> dict:
    """The full record of one sound: tags, license address, page link, preview address."""
    return _lookup(sound_id)


@server.tool()
def audition_sounds(sound_ids: list[str], label: str | None = None, open_browser: bool = True) -> dict:
    """Make a local listening page numbering up to 12 candidates and open it, so the user can choose by ear."""
    sounds = [_lookup(sound_id) for sound_id in sound_ids[:12]]
    path = audition.write_page(sounds, label)
    opened = audition.open_page(path) if open_browser else False
    return {"page": str(path), "opened": opened, "numbers": {i: s["id"] for i, s in enumerate(sounds, 1)}}


@server.tool()
def fetch_sound(sound_id: str, dest: str, format: Literal["ogg", "wav", "mp3", "flac", "original"] = "ogg",
                normalize: bool = True, trim_silence: bool | None = None, loudness_lufs: float | None = None,
                allow_warning: bool = False) -> dict:
    """Save a sound into a project folder (absolute path) and record its license in CREDITS.md and sounds.license.json.

    By default it trims silence from one-shot effects and matches loudness. Set FREESOUND_API_KEY to enable Freesound.
    May return status manual_download_needed with a page for the user to open.
    """
    return fetching.fetch(_lookup(sound_id), dest, format, normalize, trim_silence, loudness_lufs, allow_warning)


@server.tool()
def add_pack(path: str, name: str | None = None, license: str | None = None, commercial_use: bool | None = None,
             author: str | None = None, source_url: str | None = None, region: str | None = None,
             note: str | None = None) -> dict:
    """Register a folder, .zip or audio file the user already downloaded so it can be searched and fetched.

    A CC0 license file is detected. Otherwise pass license (cc0, by, by-sa, or a label such as niconi-commons) and,
    for labels, commercial_use as stated by the source. Pass region='JP' for licenses limited to Japan.
    """
    return library.add_pack(path, name, license, commercial_use, author, source_url, region, note)


@server.tool()
def open_sound_studio(path: str, open_browser: bool = True) -> dict:
    """Detect a JavaScript or TypeScript game's oscillator sound effects and open a local page to improve them.

    path is the absolute path of the game's folder. The user ticks sounds, picks replacements by ear and presses
    apply on the page, which writes them into the game. Undo is on the same page. Music is left alone.
    """
    return studio.open_studio(path, open_browser)


@server.tool()
def scan_game(path: str) -> dict:
    """List the sounds a JavaScript or TypeScript game makes with oscillators, and where each one is triggered.

    path is the absolute path of the game's folder. Nothing is changed.
    """
    report = scan.scan(path)
    for event in report["events"]:
        entry = dictionary.for_event(event)
        event["suggested"] = _suggestion(entry)
    return report


def _suggestion(entry: dict | None) -> dict | None:
    if entry is None:
        return None
    kind = None if entry.get("kind_any") else entry.get("kind", "sfx")
    return {"entry": entry["id"], "queries": entry["queries"], "kind": kind, "max_seconds": entry.get("max_seconds")}


@server.tool()
def suggest_search(text: str) -> dict:
    """Turn a game event, code name or Japanese sound word (シュッ, 被弾, ぽよん) into searches that work on sound libraries."""
    suggestion = _suggestion(dictionary.lookup(text))
    if suggestion is None:
        return {"found": False, "hint": "Not in the dictionary. Describe the physical sound in 1-3 English words."}
    return {"found": True, **suggestion}


@server.tool()
def find_replacements(path: str, per_event: int = 4, events: list[str] | None = None, license: LicenseMode = "cc0",
                      open_browser: bool = True) -> dict:
    """Scan a game for oscillator sound effects, search natural replacements for each, and open one page grouped by event.

    Music is left out. events limits it to those names. Nothing in the game is changed. Events listed under
    needs_your_words had no dictionary entry: read their call sites and use search_sounds yourself.
    """
    report = scan.scan(path)
    per_event = max(1, min(per_event, 6))
    sections, numbers, unmatched, empty, notes = [], {}, [], [], []
    number = 0
    used: set[str] = set()
    for event in report["events"]:
        if event["kind"] != "sfx" or (events and event["name"] not in events):
            continue
        entry = dictionary.for_event(event)
        if entry is None:
            unmatched.append({k: event[k] for k in ("name", "comment", "call_sites")})
            continue
        wanted = _suggestion(entry)
        found = search_sounds(wanted["queries"][0], alternatives=wanted["queries"][1:], kind=wanted["kind"],
                              max_seconds=wanted["max_seconds"], license=license, limit=20, natural_only=True)
        notes.extend(n for n in found["notes"] if n.startswith("Online search failed"))
        avoid = set(entry.get("avoid", []))
        sounds = [_seen[r["id"]] for r in found["results"] if r["id"] not in used
                  and not words(_seen[r["id"]]["title"], *_seen[r["id"]]["tags"]) & avoid][:per_event]
        if not sounds:
            empty.append(event["name"])
            continue
        used.update(sound["id"] for sound in sounds)
        sections.append((event["name"], f"{event['call_count']} call site(s), {event['defined_at']}", sounds))
        numbers[event["name"]] = {}
        for sound in sounds:
            number += 1
            numbers[event["name"]][number] = sound["id"]
    if not sections:
        return {"page": None, "opened": False, "numbers": {}, "needs_your_words": unmatched, "no_results": empty, "notes": notes}
    page = audition.write_page([], "Replace the beeps", sections)
    opened = audition.open_page(page) if open_browser else False
    return {"page": str(page), "opened": opened, "numbers": numbers, "needs_your_words": unmatched, "no_results": empty, "notes": notes}


@server.tool()
def list_packs() -> dict:
    """Packs registered with add_pack, and whether Freesound downloads are enabled."""
    return {"packs": library.list_packs(), "freesound_key_set": freesound.api_key() is not None}


@server.tool()
def find_elsewhere(query: str, kind: Kind | None = None) -> dict:
    """Search links, with what to check, for libraries a person must browse themselves (Niconi Commons, YouTube Audio Library and others)."""
    return {"links": elsewhere.links(query, kind)}


def main() -> None:
    parser = argparse.ArgumentParser(prog="otohiroi", description="Free sound effects and BGM for AI agents.")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command")
    search = commands.add_parser("search", help="search from the terminal")
    search.add_argument("query")
    search.add_argument("--kind", choices=["sfx", "music", "ambience"])
    search.add_argument("--license", choices=["cc0", "commercial", "any"], default="cc0")
    pack = commands.add_parser("add-pack", help="register a downloaded folder or .zip")
    pack.add_argument("path")
    pack.add_argument("--name")
    pack.add_argument("--license")
    pack.add_argument("--region")
    room = commands.add_parser("studio", help="open the sound studio for a game folder")
    room.add_argument("path")
    args = parser.parse_args()
    if args.command == "studio":
        print(studio.open_studio(args.path)["url"])
        input("Press Enter to close the studio.\n")
        return
    if args.command is None:
        server.run("stdio")
        return
    if args.command == "search":
        output = search_sounds(args.query, kind=args.kind, license=args.license)
    else:
        output = library.add_pack(args.path, args.name, args.license, region=args.region)
    json.dump(output, sys.stdout, ensure_ascii=False, indent=2)
    print()
