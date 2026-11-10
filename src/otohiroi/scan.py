"""Find the sounds a game makes with oscillators, and where the game triggers them.

This is a text scan, not a compiler: it reads JavaScript and TypeScript well enough to list sound functions
and their call sites, and leaves judging what each sound is for to the agent.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".mjs"}
SKIP_DIRS = {"node_modules", "dist", "build", ".git", ".next", "out", "coverage", "vendor", ".otohiroi"}
MAX_FILE_BYTES = 1_000_000
MAX_FILES = 5000
MAX_CALL_SITES = 5

_SYNTH = re.compile(r"createOscillator\s*\(|new\s+OscillatorNode|new\s+Tone\.\w*Synth|\bzzfx\w*\s*\(|\bsfxr\.")
_KEYWORDS = {"if", "for", "while", "switch", "catch", "function", "return", "constructor"}
_HEADER = re.compile(
    r"^[ \t]*(?:export\s+)?(?:default\s+)?(?:async\s+)?"
    r"(?:function\s+([A-Za-z_$][\w$]*)|([A-Za-z_$][\w$]*))\s*\(([^)]*)\)\s*(?::\s*[^{=;]+?)?\s*\{[ \t]*$"
    r"|^[ \t]*(?:export\s+)?const\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*(?::\s*[^=]+?)?\s*=>\s*\{[ \t]*$",
    re.MULTILINE,
)
_OBJECT = re.compile(r"^[ \t]*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)(?:\s*:\s*[^=]+)?\s*=\s*\{[ \t]*$", re.MULTILINE)
_NOT_AN_EVENT = re.compile(r"stop|pause|mute|resume|unlock|fade|init|setup", re.IGNORECASE)
_MUSIC = re.compile(r"music|bgm|song|startLoop|playLoop|melody", re.IGNORECASE)
_WAVE = re.compile(r"[\"'](sine|square|sawtooth|triangle)[\"']")


class ScanError(ValueError):
    pass


@dataclass
class _Function:
    name: str
    params: str
    start: int
    end: int
    body: str
    owner: str | None


def _block_end(text: str, opening: int) -> int:
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return index
    return len(text) - 1


def _functions(text: str) -> list[_Function]:
    objects = [(m.group(1), m.end() - 1, _block_end(text, text.index("{", m.start()))) for m in _OBJECT.finditer(text)]
    found = []
    for match in _HEADER.finditer(text):
        name = match.group(1) or match.group(2) or match.group(4)
        if name in _KEYWORDS:
            continue
        opening = text.rindex("{", match.start(), match.end())
        end = _block_end(text, opening)
        owner = next((label for label, start, stop in objects if start < match.start() and end <= stop), None)
        found.append(_Function(name, " ".join((match.group(3) or match.group(5) or "").split()), match.start(), end,
                               text[opening:end + 1], owner))
    return found


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _comment_above(text: str, offset: int) -> str | None:
    lines = text[:offset].rstrip("\n").rsplit("\n", 1)
    match = re.match(r"\s*//\s*(.+)", lines[-1])
    return match.group(1).strip() if match else None


def _uses_synth(functions: list[_Function]) -> set[int]:
    """Indexes of functions that reach an oscillator, directly or through other functions in the file."""
    reached = {i for i, f in enumerate(functions) if _SYNTH.search(f.body)}
    changed = True
    while changed:
        changed = False
        names = {functions[i].name for i in reached}
        calling = re.compile(r"(?<![\w$.])(?:%s)\s*\(" % "|".join(map(re.escape, names))) if names else None
        for index, function in enumerate(functions):
            if index not in reached and calling and calling.search(function.body):
                reached.add(index)
                changed = True
    return reached


def _is_building_block(function: _Function, index: int, functions: list[_Function], reached: set[int]) -> bool:
    """True for helpers such as tone(), which other sound functions are built from."""
    calling = re.compile(r"(?<![\w$.])" + re.escape(function.name) + r"\s*\(")
    return any(calling.search(functions[i].body) for i in reached if i != index)


def _sources(root: Path) -> list[Path]:
    files = []
    for path in sorted(root.rglob("*")):
        if len(files) >= MAX_FILES:
            break
        if path.suffix.lower() in SUFFIXES and path.is_file() and not SKIP_DIRS.intersection(path.relative_to(root).parts) \
                and path.stat().st_size <= MAX_FILE_BYTES and ".min." not in path.name \
                and path.stem != "otohiroi-sounds":
            files.append(path)
    return files


def _imports(text: str, module: Path) -> bool:
    return re.search(r"""from\s+["'][^"']*\b%s(?:\.\w+)?["']""" % re.escape(module.stem), text) is not None


def _call_sites(function: _Function, module: Path, own: str, inside: list[tuple[int, int]], texts: dict[Path, str],
                root: Path) -> tuple[list[dict], int]:
    prefix = rf"\b{re.escape(function.owner)}\." if function.owner else r"(?<![\w$.])"
    pattern = re.compile(prefix + re.escape(function.name) + r"\s*\(")
    sites, total = [], 0
    for path, text in texts.items():
        if path != module and not _imports(text, module):
            continue
        for match in pattern.finditer(text):
            if path == module and any(start <= match.start() <= end for start, end in inside):
                continue
            total += 1
            if len(sites) < MAX_CALL_SITES:
                line_start = text.rfind("\n", 0, match.start()) + 1
                line_end = text.find("\n", match.start())
                sites.append({"file": path.relative_to(root).as_posix(), "line": _line_of(text, match.start()),
                              "code": text[line_start:None if line_end < 0 else line_end].strip()[:140]})
    return sites, total


def scan(path: str, overrides: dict[Path, str] | None = None) -> dict:
    """overrides supplies the text to read for some files, such as the originals of files already rewritten."""
    root = Path(path).expanduser()
    if not root.is_absolute() or not root.is_dir():
        raise ScanError("Give the absolute path of the game's folder.")
    texts = {file: file.read_text(encoding="utf-8", errors="replace") for file in _sources(root)}
    texts.update({file: text.replace("\r\n", "\n") for file, text in (overrides or {}).items()})
    events, synth_files = [], []
    for module, own in texts.items():
        if not _SYNTH.search(own):
            continue
        synth_files.append(module.relative_to(root).as_posix())
        functions = _functions(own)
        reached = _uses_synth(functions)
        spans = [(functions[i].start, functions[i].end) for i in reached]
        for index, function in enumerate(functions):
            is_music_name = _MUSIC.search(function.name) or _MUSIC.search(function.body)
            if _NOT_AN_EVENT.search(function.name) or (index not in reached and not (is_music_name and function.owner)):
                continue
            if function.owner is None and _is_building_block(function, index, functions, reached):
                continue
            sites, total = _call_sites(function, module, own, [*spans, (function.start, function.end)], texts, root)
            if total == 0:
                continue
            events.append({
                "name": function.name, "owner": function.owner, "params": function.params,
                "call": f"{function.owner + '.' if function.owner else ''}{function.name}({function.params})",
                "kind": "music" if is_music_name else "sfx", "defined_at": f"{module.relative_to(root).as_posix()}:{_line_of(own, function.start)}",
                "comment": _comment_above(own, function.start), "waveforms": sorted(set(_WAVE.findall(function.body))),
                "takes_arguments": bool(function.params), "call_sites": sites, "call_count": total,
            })
    return {"root": str(root), "files_scanned": len(texts), "synth_files": synth_files, "events": events}
