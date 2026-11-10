"""A local page that lists a game's beeps, plays replacements, and writes the chosen ones into the game."""
from __future__ import annotations

import hashlib
import http.server
import json
import re
import secrets
import shutil
import subprocess
import sys
import threading
import webbrowser
from importlib import resources
from pathlib import Path

from otohiroi import dictionary, scan

GENERATED_STEM = "otohiroi-sounds"
STATE_DIR = ".otohiroi"
ALIASES = {"ui_confirm": "ui_tap", "ui_cancel": "ui_tap", "ui_hover": "ui_tap", "ui_open": "swoosh", "ui_page": "swoosh",
           "reward_pickup": "reward_coin", "reward_levelup": "magic_spell", "jingle_start": "chime_note", "countdown": "ui_tap",
           "foot_run": "foot_generic", "foot_land": "punch_hit", "sword_hit": "punch_hit", "thud_heavy": "punch_hit",
           "crash_wood": "punch_hit", "water_splash": "water_drop", "heal": "magic_spell", "bell_toll": "chime_note",
           "typing": "ui_tap", "shield": "punch_hit", "car_engine": "car_pass"}
_ARG_DEFAULTS = {"near": 1, "fromPan": -0.8, "toPan": 0.8, "pan": 0, "run": False, "big": False}
_STRIP_TYPES = ("let s='';process.stdin.setEncoding('utf8');process.stdin.on('data',d=>s+=d);process.stdin.on('end',()=>"
                "process.stdout.write(require('node:module').stripTypeScriptTypes(s,{mode:'transform'})))")


class StudioError(Exception):
    pass


def _read_data(name: str) -> str:
    return resources.files("otohiroi").joinpath(f"data/{name}").read_text(encoding="utf-8")


def families() -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    current = None
    for line in _read_data("recipes.js").splitlines():
        family = re.match(r"^  ([a-z_]+): \{$", line)
        if family:
            current = family.group(1)
            found[current] = set()
        variant = re.match(r"^    ([A-Z]): \[", line)
        if variant and current:
            found[current].add(variant.group(1))
    return found


def _family_for(event: dict) -> str | None:
    entry = dictionary.for_event(event)
    if entry is None:
        return None
    known = families()
    name = entry["id"] if entry["id"] in known else ALIASES.get(entry["id"])
    return name if name in known else None


def _param_names(params: str) -> list[str] | None:
    if not params.strip():
        return []
    names = []
    depth = 0
    piece = ""
    for char in params + ",":
        if char in "<([{":
            depth += 1
        elif char in ">)]}":
            depth -= 1
        if char == "," and depth == 0:
            if piece.strip():
                match = re.match(r"\s*([A-Za-z_$][\w$]*)", piece)
                if match is None:
                    return None  # destructuring cannot be passed along by name
                names.append(match.group(1))
            piece = ""
        else:
            piece += char
    return names


def _read(path: Path) -> str:
    return path.read_bytes().decode("utf-8")  # read_text would hide the file's line endings


def _write(path: Path, text: str) -> None:
    path.write_bytes(text.encode("utf-8"))


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _bundle(root: Path, module: Path, source: str) -> str | None:
    """The game's own sound code as browser JavaScript, so "current sound" is the real one."""
    is_typescript = module.suffix in (".ts", ".tsx")
    stands_alone = not re.search(r"^\s*import\s", source, re.MULTILINE)
    if stands_alone and not is_typescript:
        return source
    if stands_alone and shutil.which("node"):  # needs no bundler, so it works whichever one the game uses
        done = subprocess.run(["node", "--no-warnings", "-e", _STRIP_TYPES], input=source, capture_output=True, text=True,
                              encoding="utf-8", timeout=60)
        if done.returncode == 0:
            return done.stdout
    script = root / "node_modules" / "esbuild" / "bin" / "esbuild"
    if script.exists() and shutil.which("node"):
        command = ["node", str(script)] if sys.platform == "win32" else [str(script)]
        done = subprocess.run([*command, "--bundle", "--format=esm", "--platform=browser", f"--loader={'ts' if is_typescript else 'js'}",
                               f"--sourcefile={module.name}"], input=source, capture_output=True, text=True, encoding="utf-8",
                              cwd=module.parent, timeout=60)
        return done.stdout if done.returncode == 0 else None
    return None


class Studio:
    def __init__(self, path: str):
        self.root = Path(path).expanduser()
        if not self.root.is_absolute() or not self.root.is_dir():
            raise StudioError("Give the absolute path of the game's folder.")
        self.token = secrets.token_urlsafe(18)
        self.lock = threading.Lock()
        self.server = None
        self.url = ""

    # state -----------------------------------------------------------------
    @property
    def _state_path(self) -> Path:
        return self.root / STATE_DIR / "studio.json"

    def _load(self) -> dict | None:
        return json.loads(self._state_path.read_text(encoding="utf-8")) if self._state_path.exists() else None

    def _originals(self, state: dict | None) -> dict[Path, str]:
        if not state:
            return {}
        return {self.root / rel: _read(self.root / STATE_DIR / "original" / rel)
                for rel in state["modules"]}

    def _check_untouched(self, state: dict) -> None:
        for rel, sha in state["modules"].items():
            if _sha(_read(self.root / rel)) != sha:
                raise StudioError(f"{rel} was edited after Otohiroi changed it. Merge by hand, or restore it with git first.")

    def report(self) -> dict:
        state = self._load()
        report = scan.scan(str(self.root), overrides=self._originals(state))
        events, skipped = [], []
        for event in report["events"]:
            if event["kind"] != "sfx":
                continue
            family = _family_for(event)
            params = _param_names(event["params"])
            if family is None or params is None:
                skipped.append(event["name"])
                continue
            entry = dictionary.for_event(event)
            args = ["__index__" if p == "index" else _ARG_DEFAULTS.get(p, 0) for p in params]
            events.append({**event, "family": family, "params": params, "args": args, "indexed": "index" in params,
                           "label": (entry.get("ja") or [""])[0]})
        return {"root": str(self.root), "events": events, "skipped": skipped, "applied": state is not None,
                "choices": state["choices"] if state else {}, "synth_files": report["synth_files"]}

    # writing the game ------------------------------------------------------
    def apply(self, choices: dict) -> dict:
        with self.lock:
            if not choices:
                return self.undo() if self._load() else {"message": "チェックされた音がありません。", "changed": []}
            state = self._load()
            if state:
                self._check_untouched(state)
            originals = self._originals(state)
            report = self.report()
            by_name = {e["name"]: e for e in report["events"]}
            known = families()
            for name, choice in choices.items():
                if name not in by_name:
                    raise StudioError(f"{name} is not a sound in this game.")
                if choice.get("variant") not in known[by_name[name]["family"]]:
                    raise StudioError(f"{name} has no variant {choice.get('variant')!r}.")
                if not isinstance(choice.get("level"), (int, float)) or not 0 <= choice["level"] <= 2:
                    raise StudioError(f"{name} has a level outside 0 to 2.")

            modules: dict[Path, list[dict]] = {}
            for name in choices:
                modules.setdefault(self.root / by_name[name]["defined_at"].rsplit(":", 1)[0], []).append(by_name[name])
            restore = [path for path in originals if path not in modules]
            written = {}
            for module, events in modules.items():
                original = originals.get(module) or _read(module)
                written[module] = (original, self._rewrite(module, original, events))
            all_tables = {module: {e["name"]: {"family": e["family"], **choices[e["name"]]} for e in events} for module, events in modules.items()}

            for module in restore:
                _write(module, originals[module])
                self._generated(module).unlink(missing_ok=True)
            hashes = {}
            for module, (original, rewritten) in written.items():
                relative = module.relative_to(self.root).as_posix()
                backup = self.root / STATE_DIR / "original" / relative
                backup.parent.mkdir(parents=True, exist_ok=True)
                _write(backup, original)
                _write(module, rewritten)
                _write(self._generated(module), self._generated_source(module, all_tables[module]))
                hashes[relative] = _sha(rewritten)
            self._state_path.write_text(json.dumps({"modules": hashes, "choices": choices}, ensure_ascii=False, indent=1), encoding="utf-8")
            self._ignore_state()
            return {"message": f"{len(choices)}個の音を反映しました。ゲームを再読み込みして確かめてください。", "changed": sorted(hashes)}

    def undo(self) -> dict:
        state = self._load()
        if state is None:
            return {"message": "元に戻すものはありません。", "changed": []}
        self._check_untouched(state)
        originals = self._originals(state)
        for module, text in originals.items():
            _write(module, text)
            self._generated(module).unlink(missing_ok=True)
        shutil.rmtree(self.root / STATE_DIR)
        return {"message": "元の音に戻しました。", "changed": sorted(state["modules"])}

    def _generated(self, module: Path) -> Path:
        return module.with_name(GENERATED_STEM + (".ts" if module.suffix in (".ts", ".tsx") else ".js"))

    def _generated_source(self, module: Path, table: dict) -> str:
        head = "// @ts-nocheck\n" if module.suffix in (".ts", ".tsx") else ""
        return (f"{head}// Generated by Otohiroi Studio. Re-run the studio to change these sounds.\n{_read_data('recipes.js')}\n"
                f"const CHOSEN = {json.dumps(table, ensure_ascii=False)};\n\n"
                "// context: the game's AudioContext; null means the game has not unlocked audio yet.\n"
                "export function playOtohiroi(name, params, context) {\n  if (context === null) return;\n"
                "  const choice = CHOSEN[name];\n  play(choice.family, choice.variant, params, choice.level, context);\n}\n")

    def _import_path(self, module: Path) -> str:
        if module.suffix in (".js", ".mjs"):
            return f"./{GENERATED_STEM}.js"
        uses_ts = re.search(r"""from\s+["']\.[^"']+\.tsx?["']""", module.read_text(encoding="utf-8"))
        if not uses_ts:
            uses_ts = any(re.search(r"""from\s+["']\.[^"']+\.tsx?["']""", p.read_text(encoding="utf-8", errors="replace"))
                          for p in scan._sources(self.root)[:200])
        return f"./{GENERATED_STEM}{'.ts' if uses_ts else ''}"

    def _rewrite(self, module: Path, source: str, events: list[dict]) -> str:
        windows_endings = "\r\n" in source
        source = source.replace("\r\n", "\n")
        context = _game_context(source)
        functions = scan._functions(source)
        edits = []
        for event in events:
            target = next((f for f in functions if f.name == event["name"] and (f.owner or None) == event["owner"]), None)
            if target is None:
                raise StudioError(f"Could not find {event['name']} in {module.name}.")
            opening = target.end + 1 - len(target.body)
            indent = re.match(r"[ \t]*", source[source.rfind("\n", 0, target.start) + 1:]).group(0)
            args = "{ " + ", ".join(event["params"]) + " }" if event["params"] else "{}"
            call = f'playOtohiroi("{event["name"]}", {args}{", " + context if context else ""});'
            edits.append((opening, target.end + 1, f"{{\n{indent}  {call}\n{indent}}}"))
        for start, end, text in sorted(edits, reverse=True):
            source = source[:start] + text + source[end:]
        source = _keep_unused_helpers(source) if module.suffix in (".ts", ".tsx") else source
        statement = f'import {{ playOtohiroi }} from "{self._import_path(module)}";\n'
        imports = list(re.finditer(r"^import\s.*?;[ \t]*\n", source, re.MULTILINE | re.DOTALL))
        position = imports[-1].end() if imports else 0
        result = source[:position] + statement + source[position:]
        return result.replace("\n", "\r\n") if windows_endings else result

    def _ignore_state(self) -> None:
        ignore = self.root / STATE_DIR / ".gitignore"
        ignore.write_text("*\n", encoding="utf-8")

    # local page ------------------------------------------------------------
    def start(self, open_browser: bool = True) -> str:
        if self.server is None:
            studio = self

            class Handler(http.server.BaseHTTPRequestHandler):
                def log_message(self, *args):
                    pass

                def _reply(self, status: int, body: bytes, kind: str):
                    self.send_response(status)
                    self.send_header("Content-Type", kind)
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(body)

                def _json(self, status: int, data: dict):
                    self._reply(status, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json")

                def _route(self) -> str | None:
                    expected = f"127.0.0.1:{self.server.server_address[1]}"
                    prefix = f"/{studio.token}/"
                    if self.headers.get("Host") != expected or not self.path.startswith(prefix):
                        self._reply(403, b"forbidden", "text/plain")
                        return None
                    return self.path[len(prefix):].split("?")[0]

                def do_GET(self):
                    route = self._route()
                    if route is None:
                        return
                    try:
                        if route == "":
                            self._reply(200, _read_data("studio.html").encode("utf-8"), "text/html; charset=utf-8")
                        elif route == "recipes.js":
                            self._reply(200, _read_data("recipes.js").encode("utf-8"), "text/javascript; charset=utf-8")
                        elif route == "state":
                            self._json(200, studio.page_state())
                        elif route == "current.js" and studio.current_js:
                            self._reply(200, studio.current_js.encode("utf-8"), "text/javascript; charset=utf-8")
                        else:
                            self._reply(404, b"not found", "text/plain")
                    except Exception as error:  # the page shows this; the server must keep running
                        self._json(500, {"error": str(error)})

                def do_POST(self):
                    route = self._route()
                    if route is None:
                        return
                    if self.headers.get("Origin") != f"http://127.0.0.1:{self.server.server_address[1]}" or \
                            self.headers.get("Content-Type") != "application/json":
                        self._reply(403, b"forbidden", "text/plain")
                        return
                    try:
                        body = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", 0)), 1_000_000)) or b"{}")
                        if route == "apply":
                            self._json(200, studio.apply(body.get("choices") or {}))
                        elif route == "undo":
                            with studio.lock:
                                self._json(200, studio.undo())
                        else:
                            self._reply(404, b"not found", "text/plain")
                    except (StudioError, scan.ScanError, OSError, ValueError, KeyError) as error:
                        self._json(400, {"error": str(error)})

            self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            threading.Thread(target=self.server.serve_forever, daemon=True).start()
            self.url = f"http://127.0.0.1:{self.server.server_address[1]}/{self.token}/"
        self.current_js = self._current_bundle()
        if open_browser:
            webbrowser.open(self.url)
        return self.url

    current_js: str | None = None

    def _current_bundle(self) -> str | None:
        state = self._load()
        report = self.report()
        modules = {e["defined_at"].rsplit(":", 1)[0] for e in report["events"]}
        if len(modules) != 1:
            return None  # one sound module is the common shape; several would need a combined bundle
        module = self.root / next(iter(modules))
        source = self._originals(state).get(module) or _read(module)
        return _bundle(self.root, module, source)

    def page_state(self) -> dict:
        report = self.report()
        report["has_current"] = self.current_js is not None
        return report


def _keep_unused_helpers(source: str) -> str:
    """Helpers nothing calls any more would fail strict TypeScript builds, so they are referenced once."""
    unused = []
    code = re.sub(r"//[^\n]*|/\*.*?\*/", "", source, flags=re.DOTALL)  # a mention in a comment is not a use
    for function in scan._functions(source):
        calling = re.compile(r"(?<![\w$.])" + re.escape(function.name) + r"\s*\(")
        top_level = source[function.start] not in " \t\n"  # a function inside another one is not a module-level name
        if top_level and function.owner is None and len(calling.findall(code)) == 1 and not source[function.start:].startswith("export"):
            unused.append(function.name)
    if not unused:
        return source
    return f"{source.rstrip()}\n\n// Otohiroi replaced the sounds that used these. Safe to delete.\nvoid [{', '.join(unused)}];\n"


def _game_context(source: str) -> str | None:
    """The game's module-level AudioContext variable, if it has one the replaced functions can reach."""
    match = re.search(r"([A-Za-z_$][\w$]*)\s*=\s*new\s+(?:window\.)?(?:webkit)?AudioContext\b", source, re.IGNORECASE)
    if match and re.search(rf"^(?:export\s+)?(?:let|var|const)\s+{re.escape(match.group(1))}\b", source, re.MULTILINE):
        return match.group(1)
    return None


_studios: dict[str, Studio] = {}


def open_studio(path: str, open_browser: bool = True) -> dict:
    studio = _studios.get(path) or Studio(path)
    _studios[path] = studio
    url = studio.start(open_browser)
    report = studio.report()
    return {"url": url, "opened": open_browser, "sounds": [e["name"] for e in report["events"]], "no_recipe_yet": report["skipped"],
            "already_applied": report["choices"]}
