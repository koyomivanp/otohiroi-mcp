"""Turns what a game calls a sound, or a Japanese sound word, into searches that work on sound libraries."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib import resources


@lru_cache(maxsize=1)
def entries() -> list[dict]:
    return json.loads(resources.files("otohiroi").joinpath("data/events.json").read_text(encoding="utf-8"))


def _tokens(text: str) -> list[str]:
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    return re.findall(r"[a-z0-9]+", spaced.lower())


def _contains(tokens: list[str], phrase: list[str]) -> bool:
    size = len(phrase)
    return any(tokens[i:i + size] == phrase for i in range(len(tokens) - size + 1))


def lookup(text: str) -> dict | None:
    """The best entry for a code name, English phrase or Japanese word. Longer aliases win over shorter ones."""
    tokens = _tokens(text)
    best, best_length = None, 0
    for entry in entries():
        for alias in entry.get("aliases", []):
            phrase = alias.split()
            if len(alias) > best_length and _contains(tokens, phrase):
                best, best_length = entry, len(alias)
        for word in entry.get("ja", []):
            if word in text and len(word) * 2 > best_length:  # a Japanese character says about as much as two letters
                best, best_length = entry, len(word) * 2
    return best


def for_event(event: dict) -> dict | None:
    return lookup(event["name"]) or (lookup(event["comment"]) if event.get("comment") else None)
