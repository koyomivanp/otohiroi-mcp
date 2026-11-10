import json
import shutil
import subprocess
import sys
import zipfile

import anyio
import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from otohiroi import audition, dictionary, elsewhere, fetch, freesound, library, net, openverse, scan, server, studio
from otohiroi.records import guess_kind, matches_filters, suspect_reason


def verse(**changes):
    item = {"id": "11111111-1111-1111-1111-111111111111", "title": "Sword Hit", "creator": "someone", "duration": 1500,
            "source": "freesound", "license": "cc0", "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
            "foreign_landing_url": "https://freesound.org/people/someone/sounds/12345/",
            "url": "https://cdn.freesound.org/previews/1/1-hq.mp3", "tags": [{"name": "metal"}]}
    return {**item, **changes}


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("OTOHIROI_HOME", str(tmp_path / "home"))
    monkeypatch.delenv(freesound.KEY_ENV, raising=False)
    server._seen.clear()


def tone(path, seconds=0.5):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
                    str(path)], check=True)


needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")


def test_only_listed_https_hosts():
    net.check_url("https://api.openverse.org/v1/audio/")
    for bad in ("http://api.openverse.org/", "https://evil.example/", "https://api.openverse.org.evil.example/", "file:///etc/passwd"):
        with pytest.raises(net.NetError):
            net.check_url(bad)


def test_kind_guess():
    assert guess_kind("Retro Game Music Loop", [], 58, "freesound") == "music"
    assert guess_kind("Music stinger blip", [], 1, "freesound") == "sfx"
    assert guess_kind("Forest", ["ambience"], 60, "freesound") == "ambience"
    assert guess_kind("anything", [], 3, "jamendo") == "music"


def test_suspect_names_are_flagged():
    assert suspect_reason("I am dreaming or Final Fantasy menu kind", [])
    assert suspect_reason("Sword hit", ["metal"]) is None


def test_filters_leave_out_unknown_length_when_length_matters():
    assert not matches_filters({"kind": "sfx", "duration_s": None}, None, None, 2, False)
    assert matches_filters({"kind": "sfx", "duration_s": 1}, "sfx", None, 2, False)


def test_openverse_record_keeps_freesound_id_and_terms():
    record = openverse.normalise(verse(license="by"))
    assert record["freesound_id"] == 12345
    assert record["commercial_use"] and record["credit_required"]


def test_unknown_licence_is_not_commercial():
    assert openverse.normalise(verse(license="by-nc"))["commercial_use"] is False


def test_search_drops_what_the_licence_mode_excludes(monkeypatch):
    monkeypatch.setattr(openverse, "search", lambda *a: [openverse.normalise(verse(license="by-nc"))])
    assert server.search_sounds("sword", license="commercial")["results"] == []


def test_empty_search_is_retried_with_fewer_words(monkeypatch):
    asked = []

    def only_two_words(query, *rest):
        asked.append(query)
        return [openverse.normalise(verse())] if query == "chiptune loop" else []
    monkeypatch.setattr(openverse, "search", only_two_words)
    found = server.search_sounds("calm chiptune loop")
    assert asked == ["calm chiptune loop", "chiptune loop"]
    assert len(found["results"]) == 1 and "chiptune loop" in found["notes"][0]


def test_search_survives_openverse_being_down(monkeypatch):
    def down(*args):
        raise net.NetError("offline")
    monkeypatch.setattr(openverse, "search", down)
    assert "offline" in server.search_sounds("sword")["notes"][0]


def test_freesound_needs_the_users_key(tmp_path):
    result = fetch.fetch(openverse.normalise(verse()), str(tmp_path / "out"))
    assert result["status"] == "manual_download_needed"
    assert freesound.KEY_ENV in result["reason"]
    assert not list((tmp_path / "out").glob("*"))


def test_jamendo_is_manual(tmp_path):
    result = fetch.fetch(openverse.normalise(verse(source="jamendo", license="by")), str(tmp_path))
    assert result["status"] == "manual_download_needed"


def test_licence_change_stops_the_download(tmp_path, monkeypatch):
    monkeypatch.setenv(freesound.KEY_ENV, "k")
    monkeypatch.setattr(freesound, "download_preview", lambda *a: (b"x", ".ogg", "by-nc"))
    with pytest.raises(fetch.FetchError, match="by-nc"):
        fetch.fetch(openverse.normalise(verse()), str(tmp_path))


def test_key_goes_only_in_the_freesound_header(monkeypatch):
    calls = []
    monkeypatch.setattr(net, "get_json", lambda url, headers=None: calls.append((url, headers)) or {
        "license": "http://creativecommons.org/publicdomain/zero/1.0/", "previews": {"preview-hq-ogg": "https://cdn.freesound.org/a.ogg"}})
    monkeypatch.setattr(net, "get_bytes", lambda url, headers=None: calls.append((url, headers)) or b"audio")
    assert freesound.download_preview(5, "secret") == (b"audio", ".ogg", "cc0")
    assert "secret" not in calls[0][0] and calls[0][1]["Authorization"] == "Token secret"
    assert calls[1][1] is None


def test_warning_blocks_fetch_until_allowed(tmp_path):
    with pytest.raises(fetch.FetchError, match="Final Fantasy"):
        fetch.fetch(openverse.normalise(verse(title="Final Fantasy menu")), str(tmp_path))


def test_pack_without_licence_is_refused(tmp_path):
    (tmp_path / "a.wav").write_bytes(b"x")
    with pytest.raises(library.LibraryError, match="license"):
        library.add_pack(str(tmp_path))


def test_custom_label_needs_a_commercial_answer(tmp_path):
    (tmp_path / "a.wav").write_bytes(b"x")
    with pytest.raises(library.LibraryError, match="commercial_use"):
        library.add_pack(str(tmp_path), license="niconi-commons")


def test_zip_slip_is_refused(tmp_path):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("../../evil.wav", b"x")
    with pytest.raises(library.LibraryError, match="Unsafe"):
        library.add_pack(str(archive), license="cc0")


@needs_ffmpeg
def test_zip_pack_to_project_records_the_licence(tmp_path, monkeypatch):
    tone(tmp_path / "impactMetal_light_000.ogg")
    archive = tmp_path / "kenney_impact-sounds.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.write(tmp_path / "impactMetal_light_000.ogg", "Audio/impactMetal_light_000.ogg")
        bundle.writestr("License.txt", "License: (Creative Commons Zero, CC0)")
    added = library.add_pack(str(archive), name="Kenney Impact Sounds", source_url="https://kenney.nl/assets/impact-sounds")
    assert added == {"pack": "kenney-impact-sounds", "license": "cc0", "sounds": 1, "folder": added["folder"]}
    monkeypatch.setattr(openverse, "search", lambda *a: [])
    found = server.search_sounds("metal impact")["results"]
    assert found[0]["title"] == "impact Metal light 000"
    dest = tmp_path / "game" / "Audio"
    result = server.fetch_sound(found[0]["id"], str(dest), format="wav")
    assert result["status"] == "fetched" and result["path"].endswith(".wav")
    ledger = json.loads((dest / "sounds.license.json").read_text(encoding="utf-8"))
    assert ledger[0]["license"] == "cc0" and ledger[0]["page"].startswith("https://kenney.nl")
    server.fetch_sound(found[0]["id"], str(dest), format="wav")
    assert (dest / "CREDITS.md").read_text(encoding="utf-8").count("impact Metal") == 1


@needs_ffmpeg
def test_region_limit_is_carried_to_the_credits(tmp_path):
    tone(tmp_path / "bell.wav")
    library.add_pack(str(tmp_path / "bell.wav"), name="nico", license="niconi-commons", commercial_use=False, region="jp")
    sound = library.search(["bell"])[0]
    result = fetch.fetch(sound, str(tmp_path / "out"), format="original")
    assert "JP" in result["notes"][0]
    assert "region: JP" in (tmp_path / "out" / "CREDITS.md").read_text(encoding="utf-8")


def test_audition_page_escapes_uploader_text():
    page = audition.write_page([openverse.normalise(verse(title="<script>alert(1)</script>"))], "x")
    text = page.read_text(encoding="utf-8")
    assert "<script>" not in text and "&lt;script&gt;" in text and "default-src 'none'" in text


def test_nothing_online_is_contacted_for_elsewhere_links(monkeypatch):
    monkeypatch.setattr(net, "_open", lambda *a: pytest.fail("network used"))
    names = {link["name"] for link in elsewhere.links("和風 太鼓")}
    assert any("コモンズ" in name for name in names) and "YouTube Audio Library" in names


def test_real_client_sees_the_tools():
    async def run():
        params = StdioServerParameters(command=sys.executable, args=["-c", "from otohiroi.server import main; main()"])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return {tool.name for tool in (await session.list_tools()).tools}
    assert anyio.run(run) == {"search_sounds", "get_sound", "audition_sounds", "fetch_sound", "add_pack", "list_packs",
                              "find_elsewhere", "scan_game", "suggest_search", "find_replacements", "open_sound_studio"}


GAME_SOUND = """
let ctx: AudioContext | null = null;
export function unlockSound(): void { ctx = new AudioContext(); }

function tone(
  freq: number,
  length: number,
  type: OscillatorType = "square",
): void {
  const osc = ctx!.createOscillator();
  osc.type = type;
  osc.start();
}

export const sound = {
  tap(): void {
    tone(660, 0.07, "triangle");
  },
  // Footfall of a chick.
  step(near: number): void {
    tone(330, 0.05, "sine");
  },
  neverUsed(): void {
    tone(1, 1);
  },
  music(id: string | null): void {
    startLoop(id);
  },
  homeStop(): void {
    fadeOut(homeLoop);
  },
};
"""
GAME_MAIN = """
import { sound } from "./sound.ts";
function step() { return 1; }
button.onclick = () => { sound.tap(); };
sound.step(0.5);
other.step(1);
sound.music("walk");
sound.homeStop();
"""


def game(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "sound.ts").write_text(GAME_SOUND, encoding="utf-8")
    (tmp_path / "src" / "main.ts").write_text(GAME_MAIN, encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "lib.js").write_text("ctx.createOscillator();", encoding="utf-8")
    return tmp_path


def test_scan_finds_triggered_sounds_only(tmp_path):
    report = scan.scan(str(game(tmp_path)))
    events = {e["name"]: e for e in report["events"]}
    assert set(events) == {"tap", "step", "music"}
    assert report["synth_files"] == ["src/sound.ts"]
    assert events["tap"]["waveforms"] == ["triangle"] and events["tap"]["kind"] == "sfx"
    assert events["music"]["kind"] == "music"


def test_scan_ignores_same_named_methods_on_other_objects(tmp_path):
    step = next(e for e in scan.scan(str(game(tmp_path)))["events"] if e["name"] == "step")
    assert step["call_count"] == 1 and step["call_sites"][0]["code"] == "sound.step(0.5);"
    assert step["comment"] == "Footfall of a chick." and step["takes_arguments"]


def test_scan_needs_an_absolute_folder():
    with pytest.raises(ValueError):
        scan.scan("relative/path")


def test_dictionary_reads_code_names_and_sound_words():
    assert dictionary.lookup("carPass")["id"] == "car_pass"
    assert dictionary.lookup("car")["id"] == "car_engine"
    assert dictionary.lookup("piyo")["id"] == "chick_chirp"
    assert dictionary.lookup("シュッ")["id"] == "swoosh"
    assert dictionary.lookup("xyzzy") is None


def test_recipes_are_listed_and_aliases_point_at_them():
    known = studio.families()
    assert len(known) >= 20 and known["ui_tap"] == {"A", "B", "C"}
    assert set(studio.ALIASES.values()) <= set(known)
    ids = {entry["id"] for entry in dictionary.entries()}
    assert set(studio.ALIASES) <= ids


def choose(variant="A", level=1):
    return {"variant": variant, "level": level}


def test_apply_replaces_only_chosen_sounds_and_undo_restores_bytes(tmp_path):
    root = game(tmp_path)
    module = root / "src" / "sound.ts"
    before = module.read_bytes()
    room = studio.Studio(str(root))
    assert {e["name"] for e in room.report()["events"]} == {"tap", "step"}
    room.apply({"step": choose("B", 0.5)})
    text = module.read_text(encoding="utf-8")
    assert 'playOtohiroi("step", { near }, ctx);' in text
    assert 'import { playOtohiroi } from "./otohiroi-sounds.ts";' in text
    assert 'tone(660, 0.07, "triangle");' in text  # tap was not ticked
    assert (root / "src" / "otohiroi-sounds.ts").read_text(encoding="utf-8").startswith("// @ts-nocheck")
    room.undo()
    assert module.read_bytes() == before
    assert not (root / "src" / "otohiroi-sounds.ts").exists() and not (root / ".otohiroi").exists()


def test_windows_line_endings_survive_apply_and_undo(tmp_path):
    root = game(tmp_path)
    module = root / "src" / "sound.ts"
    module.write_bytes(GAME_SOUND.replace("\n", "\r\n").encode())
    before = module.read_bytes()
    room = studio.Studio(str(root))
    room.apply({"tap": choose()})
    assert b'playOtohiroi("tap", {}, ctx);\r\n' in module.read_bytes()
    room.undo()
    assert module.read_bytes() == before


def test_sounds_are_not_listed_twice_after_apply(tmp_path):
    room = studio.Studio(str(game(tmp_path)))
    room.apply({"tap": choose()})
    assert sorted(e["name"] for e in room.report()["events"]) == ["step", "tap"]


def test_applying_again_starts_from_the_original(tmp_path):
    root = game(tmp_path)
    room = studio.Studio(str(root))
    room.apply({"tap": choose(), "step": choose()})
    room.apply({"tap": choose("C")})
    text = (root / "src" / "sound.ts").read_text(encoding="utf-8")
    assert text.count("import { playOtohiroi }") == 1 and "tone(330, 0.05" in text
    assert room.report()["choices"] == {"tap": choose("C")}


def test_edits_made_after_apply_are_never_overwritten(tmp_path):
    root = game(tmp_path)
    room = studio.Studio(str(root))
    room.apply({"tap": choose()})
    module = root / "src" / "sound.ts"
    module.write_text(module.read_text(encoding="utf-8") + "\n// mine\n", encoding="utf-8")
    with pytest.raises(studio.StudioError, match="edited"):
        room.undo()
    assert "// mine" in module.read_text(encoding="utf-8")


@pytest.mark.parametrize("bad", [{"nope": choose()}, {"tap": choose("Z")}, {"tap": choose(level=9)}])
def test_bad_choices_change_nothing(tmp_path, bad):
    root = game(tmp_path)
    before = (root / "src" / "sound.ts").read_bytes()
    with pytest.raises(studio.StudioError):
        studio.Studio(str(root)).apply(bad)
    assert (root / "src" / "sound.ts").read_bytes() == before


def test_helpers_left_unused_are_kept_for_strict_builds():
    kept = studio._keep_unused_helpers("// Like tone(), but later.\nfunction tone() {\n  osc();\n}\nfunction used() {\n  osc();\n}\nused();\n")
    assert kept.endswith("void [tone];\n")


def test_inner_functions_are_not_listed_as_unused_helpers():
    source = "function outer() {\n  const queue = () => {\n    work();\n  };\n  queue();\n}\nouter();\n"
    assert "void [" not in studio._keep_unused_helpers(source.replace("  queue();\n", ""))


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_current_sound_loads_without_a_bundler(tmp_path):
    bundled = studio._bundle(tmp_path, tmp_path / "sound.ts", "export const a: number = 1;\n")
    assert bundled is not None and "number" not in bundled and "const a" in bundled


def test_module_level_context_is_passed_along():
    assert studio._game_context("let context = null;\nfunction f(){ context = new AudioContext(); }") == "context"
    assert studio._game_context("function f(){ const ctx = new AudioContext(); }") is None


def test_studio_refuses_requests_without_its_token_or_origin(tmp_path):
    import urllib.error
    import urllib.request
    room = studio.Studio(str(game(tmp_path)))
    url = room.start(open_browser=False)
    base = url.rsplit("/", 2)[0]
    with pytest.raises(urllib.error.HTTPError) as denied:
        urllib.request.urlopen(base + "/wrong-token/state")
    assert denied.value.code == 403
    assert json.load(urllib.request.urlopen(url + "state"))["events"]
    forged = urllib.request.Request(url + "apply", data=b'{"choices":{"tap":{"variant":"A","level":1}}}', method="POST",
                                    headers={"Content-Type": "application/json", "Origin": "https://evil.example"})
    with pytest.raises(urllib.error.HTTPError) as blocked:
        urllib.request.urlopen(forged)
    assert blocked.value.code == 403 and not (tmp_path / ".otohiroi").exists()
    room.server.shutdown()


def test_every_dictionary_entry_is_usable():
    for entry in dictionary.entries():
        assert entry["queries"] and all(1 <= len(q.split()) <= 3 for q in entry["queries"]), entry["id"]
        assert entry.get("aliases") or entry.get("ja"), entry["id"]


def test_natural_only_leaves_out_beeps(monkeypatch):
    monkeypatch.setattr(openverse, "search", lambda *a: [openverse.normalise(verse(title="8bit beep")),
                                                         openverse.normalise(verse(id="22222222-2222-2222-2222-222222222222"))])
    assert [r["title"] for r in server.search_sounds("x", natural_only=True)["results"]] == ["Sword Hit"]


def test_find_replacements_groups_by_event_and_leaves_the_game_alone(tmp_path, monkeypatch):
    root = game(tmp_path)
    before = (root / "src" / "sound.ts").read_bytes()
    counter = iter(range(1000))
    monkeypatch.setattr(openverse, "search", lambda *a: [openverse.normalise(
        verse(id=f"{next(counter):08d}-1111-1111-1111-111111111111", duration=500))])
    result = server.find_replacements(str(root), per_event=1, open_browser=False)
    assert set(result["numbers"]) == {"tap", "step"}  # music is left out
    text = open(result["page"], encoding="utf-8").read()
    assert "<h3>tap</h3>" in text and "<h3>step</h3>" in text
    assert (root / "src" / "sound.ts").read_bytes() == before


def test_replacements_skip_avoided_words_and_repeats(tmp_path, monkeypatch):
    root = game(tmp_path)
    (root / "src" / "sound.ts").write_text(GAME_SOUND.replace("tap()", "rumble()").replace("step(near", "ghost(near"), encoding="utf-8")
    (root / "src" / "main.ts").write_text(GAME_MAIN.replace("sound.tap", "sound.rumble").replace("sound.step", "sound.ghost"), encoding="utf-8")
    monkeypatch.setattr(openverse, "search", lambda *a: [openverse.normalise(verse(title="Stomach rumble", duration=2000)),
                                                         openverse.normalise(verse(id="22222222-2222-2222-2222-222222222222", title="Deep tremor", duration=2000))])
    numbers = server.find_replacements(str(root), per_event=2, open_browser=False)
    rumble, ghost = numbers["numbers"]["rumble"], numbers["numbers"]["ghost"]
    assert [server._seen[i]["title"] for i in rumble.values()] == ["Deep tremor"]
    assert not set(rumble.values()) & set(ghost.values())


def test_event_without_a_dictionary_entry_is_handed_to_the_agent(tmp_path, monkeypatch):
    root = game(tmp_path)
    source = (root / "src" / "sound.ts").read_text(encoding="utf-8").replace("tap()", "qwerty()")
    (root / "src" / "sound.ts").write_text(source, encoding="utf-8")
    (root / "src" / "main.ts").write_text(GAME_MAIN.replace("sound.tap", "sound.qwerty"), encoding="utf-8")
    monkeypatch.setattr(openverse, "search", lambda *a: [])
    assert server.find_replacements(str(root), open_browser=False)["needs_your_words"][0]["name"] == "qwerty"
