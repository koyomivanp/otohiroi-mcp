"""Freesound through its official API, using a key that belongs to the person running Otohiroi.

Freesound's API terms give each application its own key and forbid fetching content outside the API,
so Otohiroi ships no key and only downloads Freesound audio when the user has supplied theirs.
"""
from __future__ import annotations

import os

from otohiroi import net

API = "https://freesound.org/apiv2/sounds"
KEY_ENV = "FREESOUND_API_KEY"
KEY_URL = "https://freesound.org/apiv2/apply/"
_LICENSE_CODES = {"creative commons 0": "cc0", "attribution": "by", "attribution noncommercial": "by-nc",
                  "sampling+": "sampling+"}
_LICENSE_URL_PARTS = (("/publicdomain/zero/", "cc0"), ("/licenses/by-nc/", "by-nc"), ("/licenses/by/", "by"),
                      ("/sampling+/", "sampling+"))


def api_key() -> str | None:
    return os.environ.get(KEY_ENV) or None


def _licence_code(value: str) -> str | None:
    lowered = (value or "").lower()
    for part, code in _LICENSE_URL_PARTS:
        if part in lowered:
            return code
    return _LICENSE_CODES.get(lowered)


def download_preview(sound_id: int, key: str) -> tuple[bytes, str, str | None]:
    """The high quality preview, plus the license Freesound reports today. Original files need OAuth2."""
    info = net.get_json(f"{API}/{int(sound_id)}/?fields=id,license,previews",
                        headers={"Authorization": f"Token {key}"})
    url = info["previews"]["preview-hq-ogg"]
    return net.get_bytes(url), ".ogg", _licence_code(info.get("license"))
