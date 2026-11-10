"""Search through the public Openverse API, which indexes Freesound, Jamendo and Wikimedia audio."""
from __future__ import annotations

import re
import urllib.parse

from otohiroi import net
from otohiroi.records import guess_kind, license_terms, suspect_reason, words

API = "https://api.openverse.org/v1/audio/"
PAGE_SIZE = 20  # the most an anonymous client may ask for
LICENSE_QUERY = {"cc0": "cc0,pdm", "commercial": "cc0,pdm,by,by-sa"}
DEFAULT_SOURCES = "freesound,jamendo"  # Wikimedia is mostly pronunciations and classical recordings
_UUID = re.compile(r"^[0-9a-fA-F-]{36}$")
_FREESOUND_ID = re.compile(r"/sounds?/(\d+)")


def normalise(item: dict) -> dict:
    tags = [t["name"] for t in item.get("tags") or [] if t.get("name")]
    title = item.get("title") or "untitled"
    duration = item["duration"] / 1000 if item.get("duration") else None
    source = item.get("source") or ""
    code = item.get("license") or ""
    record = {
        "id": f"openverse:{item['id']}",
        "source": source,
        "title": title,
        "author": item.get("creator") or "unknown",
        "kind": guess_kind(title, tags, duration, source),
        "duration_s": duration,
        "loop": True if "loop" in words(title, *tags) or "looping" in words(title, *tags) else None,
        "tags": tags[:12],
        "license": code,
        "license_url": item.get("license_url"),
        "landing_url": item.get("foreign_landing_url"),
        "preview_url": item.get("url"),
        "region": None,
        "warning": suspect_reason(title, tags),
        **license_terms(code),
    }
    match = _FREESOUND_ID.search(record["landing_url"] or "") if source == "freesound" else None
    if match:
        record["freesound_id"] = int(match.group(1))
    return record


def search(query: str, license_mode: str, source: str | None, page: int) -> list[dict]:
    params = {"q": query, "page": page, "page_size": PAGE_SIZE, "mature": "false",
              "source": source or DEFAULT_SOURCES}
    if license_mode in LICENSE_QUERY:
        params["license"] = LICENSE_QUERY[license_mode]
    data = net.get_json(f"{API}?{urllib.parse.urlencode(params)}")
    # "LL-Q..." files are Lingua Libre word pronunciations, which swamp Wikimedia results.
    return [normalise(item) for item in data.get("results") or [] if not (item.get("title") or "").startswith("LL-Q")]


def get(uuid: str) -> dict:
    if not _UUID.match(uuid):
        raise net.NetError(f"{uuid!r} is not an Openverse id.")
    return normalise(net.get_json(f"{API}{uuid}/"))
