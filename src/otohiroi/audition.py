"""A local page for choosing by ear, because an agent can read a title but cannot hear the sound."""
from __future__ import annotations

import html
import time
import webbrowser
from pathlib import Path

from otohiroi import library

_STYLE = """
:root{color-scheme:light dark;--bg:#f6f5f1;--card:#fff;--text:#1d1c1a;--dim:#6d6a64;--line:#dedbd3;--warn:#a34a00}
@media (prefers-color-scheme:dark){:root{--bg:#191816;--card:#24221f;--text:#f1eee8;--dim:#a7a297;--line:#3a3732;--warn:#ffb26b}}
body{margin:0;background:var(--bg);color:var(--text);font:15px/1.6 system-ui,"Yu Gothic UI",sans-serif}
main{max-width:720px;margin:0 auto;padding:24px 16px 48px}
h1{font-size:20px;margin:0 0 4px}p.lead{color:var(--dim);margin:0 0 20px}
article{display:grid;grid-template-columns:44px 1fr;gap:4px 12px;background:var(--card);border:1px solid var(--line);
border-radius:10px;padding:14px;margin-bottom:12px}
.no{grid-row:span 3;font-size:26px;font-weight:700;text-align:center}
h3{font-size:17px;margin:28px 0 2px}h3+p.meta{margin:0 0 10px}
h2{font-size:16px;margin:0;overflow-wrap:anywhere}.meta{color:var(--dim);font-size:13px;overflow-wrap:anywhere}
.warn{color:var(--warn);font-size:13px;grid-column:2}audio{width:100%;height:36px;grid-column:2}a{color:inherit}
"""


def _source_of(sound: dict) -> str | None:
    if sound["id"].startswith("local:"):
        return library.file_of(sound).as_uri()
    url = sound.get("preview_url") or ""
    return url if url.startswith("https://") else None


def _card(number: int, sound: dict) -> str:
    esc = lambda value: html.escape(str(value), quote=True)  # noqa: E731
    length = f"{sound['duration_s']:.1f} s" if sound.get("duration_s") else "length unknown"
    meta = " / ".join([sound["kind"], length, sound["license"].upper(), sound["author"], sound["source"]])
    link = sound.get("landing_url") or ""
    title = esc(sound["title"])
    heading = f'<a href="{esc(link)}" rel="noreferrer">{title}</a>' if link.startswith("https://") else title
    src = _source_of(sound)
    player = f'<audio controls preload="none" src="{esc(src)}"></audio>' if src else '<div class="meta">No preview</div>'
    warning = f'<div class="warn">{esc(sound["warning"])}</div>' if sound.get("warning") else ""
    return (f'<article><div class="no">{number}</div><h2>{heading}</h2>'
            f'<div class="meta">{esc(meta)}</div>{player}{warning}</article>')


def _section_cards(sections: list[tuple[str, str, list[dict]]]) -> str:
    parts, number = [], 0
    for heading, detail, sounds in sections:
        if heading:
            parts.append(f"<h3>{html.escape(heading)}</h3><p class=\"meta\">{html.escape(detail)}</p>")
        for sound in sounds:
            number += 1
            parts.append(_card(number, sound))
    return "\n".join(parts)


def write_page(sounds: list[dict], label: str | None, sections: list[tuple[str, str, list[dict]]] | None = None) -> Path:
    folder = library.home() / "audition"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"audition-{time.strftime('%Y%m%d-%H%M%S')}.html"
    title = html.escape(label or "Audition")
    cards = _section_cards(sections if sections is not None else [("", "", sounds)])
    path.write_text(
        "<!doctype html><html lang=\"ja\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none';media-src https: file:;style-src 'unsafe-inline'\">"
        f"<title>{title}</title><style>{_STYLE}</style></head><body><main><h1>{title}</h1>"
        "<p class=\"lead\">聴いて、気に入った番号をAIに伝えてください。 / Listen, then tell your agent the numbers you like.</p>"
        f"{cards}</main></body></html>",
        encoding="utf-8",
    )
    return path


def open_page(path: Path) -> bool:
    try:
        return webbrowser.open(path.as_uri())
    except webbrowser.Error:
        return False
