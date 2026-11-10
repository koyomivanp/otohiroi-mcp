# Otohiroi MCP

**English** | [日本語](README.ja.md)

Otohiroi (音拾い, "picking up sounds") gives Claude Code, Cursor, Claude Desktop and other [MCP](https://modelcontextprotocol.io) clients a way to find free sound effects and BGM for your game. Ask for "a short metal sword hit" or "a calm chiptune loop". The agent searches, you choose by ear, and the file lands in your project with its license on record.

Otohiroi is an index and a helper. It hosts no audio. Files come from their original sources to your machine.

```
"a short metal sword hit"
  └─ search_sounds     keywords, length, loop, license
  └─ audition_sounds   a numbered listening page, because the agent cannot hear
  └─ fetch_sound       trim, match loudness, convert, write CREDITS.md and sounds.license.json
```

## Install

Needs [uv](https://docs.astral.sh/uv/). [ffmpeg](https://ffmpeg.org) is optional and enables conversion and loudness matching.

```bash
claude mcp add otohiroi -- uvx --from git+https://github.com/koyomivanp/otohiroi-mcp otohiroi
```

Other clients:

```json
{"mcpServers": {"otohiroi": {"command": "uvx", "args": ["--from", "git+https://github.com/koyomivanp/otohiroi-mcp", "otohiroi"]}}}
```

## Tools

| Tool | What it does |
|---|---|
| `open_sound_studio` | Detects a JavaScript or TypeScript game's beeps and opens a local page: tick sounds, pick replacements by ear, apply them to the game, undo at any time. Replacements are synthesised, so they need no audio files or keys. |
| `find_replacements` | Finds the sounds a JavaScript or TypeScript game makes with oscillators, then opens one listening page of natural replacements, grouped by event. Changes nothing in the game. |
| `scan_game` | Lists those oscillator sounds and where each one is triggered. |
| `suggest_search` | Turns a game event or a Japanese sound word (シュッ, ぽよん) into searches that work. |
| `search_sounds` | Searches online indexes and your packs. Filters by kind, length, loop and license. CC0 only by default. |
| `get_sound` | Returns the full record of one sound. |
| `audition_sounds` | Opens a local page with up to 12 numbered players. |
| `fetch_sound` | Saves a sound to your project and records its license. |
| `add_pack` | Registers a folder, zip or file you downloaded, so it can be searched and fetched. |
| `list_packs` | Lists your packs and shows whether Freesound downloads are on. |
| `find_elsewhere` | Builds search links for libraries you browse yourself. |

## Sources

| Source | Search | Listen | Download |
|---|---|---|---|
| Freesound (through [Openverse](https://openverse.org)) | No key | Yes | With your own free `FREESOUND_API_KEY` (192 kbps preview). Otherwise you get the page link. |
| Jamendo (through Openverse) | No key | Yes | Page link |
| Wikimedia Commons (through Openverse) | No key | Yes | Automatic |
| Your packs, such as [Kenney](https://kenney.nl/assets/category:Audio) | Local | Yes | Automatic |
| Niconi Commons, YouTube Audio Library, OpenGameArt, Pixabay | Link only | On their sites | By hand, then `add_pack` |

### Why some libraries are links only

Otohiroi follows each library's rules, even when that makes it less convenient.

- **YouTube Audio Library:** YouTube's terms forbid automated access and downloading outside what the service provides, and its help pages only cover use in YouTube videos.
- **Niconi Commons:** there is no public API and conditions differ per item. Its terms also limit the licensed territory to Japan, so a game sold abroad needs extra care. Use `add_pack` with `region="JP"` to keep that on record.
- **OpenGameArt and Kenney:** their robots.txt files turn away AI agents. Download in your browser, then use `add_pack`.

## Using the sounds responsibly

Licenses come from what uploaders declared. Otohiroi flags names that suggest borrowed audio, but it cannot prove that a sound is clean, and this is not legal advice. Check anything important before you ship.

Freesound's API is free for non-commercial use, and its terms say commercial use is negotiated separately. Whether fetching sounds for a game you sell counts is not stated, so ask Freesound if that matters to you.

## Settings

| Variable | Effect |
|---|---|
| `FREESOUND_API_KEY` | Your own key from [Freesound](https://freesound.org/apiv2/apply/). Never share it. |
| `OTOHIROI_HOME` | Where packs and listening pages are kept. |

## Development

```bash
uv sync
uv run pytest
```

## License

Code: [MIT](LICENSE). Each sound keeps its own license.

Inspired by [Sozai Search MCP](https://github.com/kanaworksai-hue/sozai-search-mcp). Otohiroi is independent and is not affiliated with or endorsed by any library named here.
