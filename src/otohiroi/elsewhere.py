"""Search links for libraries a tool must not crawl. Otohiroi only builds the address; a person opens it."""
from __future__ import annotations

from urllib.parse import quote, urlencode


def links(query: str, kind: str | None = None) -> list[dict]:
    pixabay = "music" if kind == "music" else "sound-effects"
    return [
        {"name": "ニコニ・コモンズ (Niconi Commons)",
         "url": "https://commons.nicovideo.jp/search?" + urlencode({"keywords": query, "materialType": 2}),
         "check": "Needs a niconico account. Conditions are set per item (commercial use can be OK, ask first, or no; "
                  "the allowed places can be limited). The terms limit the licensed territory to Japan (article 25), "
                  "so check before shipping a game outside Japan. Show the license ID (nc...) when publishing elsewhere."},
        {"name": "YouTube Audio Library", "url": "https://studio.youtube.com/",
         "check": "Open Audio Library inside YouTube Studio. YouTube's help only covers use in YouTube videos and its terms "
                  "forbid automated access. Do not treat a track as cleared for a game without its author's permission."},
        {"name": "OpenGameArt", "url": "https://opengameart.org/art-search?" + urlencode({"keys": query}),
         "check": "Made for games. The license differs per item: prefer CC0 and avoid GPL for closed-source games."},
        {"name": "Kenney audio packs", "url": "https://kenney.nl/assets/category:Audio",
         "check": "CC0. Download a pack in the browser, then register the zip with add_pack."},
        {"name": "Pixabay", "url": f"https://pixabay.com/{pixabay}/search/{quote(query)}/",
         "check": "Has its own content license, not CC0. Read it for your use. Its public API has no audio."},
    ]
