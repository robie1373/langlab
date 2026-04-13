# LangLab Documentation

Language learning suite — VTT player, flashcards, AI lessons, conversational tutor.

> Last updated: 2026-04-13

---

## Contents

| Document | Description |
|----------|-------------|
| [api.md](api.md) | Full REST API reference |
| [issues.md](issues.md) | Issue and feature queue |
| [runbooks/data-load.md](runbooks/data-load.md) | Load Pimsleur VTTs and Anki decks |
| [runbooks/start-server.md](runbooks/start-server.md) | Start / stop the development server |

---

## Stack

| Layer | Technology |
|-------|-----------|
| Server | Python stdlib `http.server`, no framework |
| Database | SQLite (WAL mode, foreign keys on) |
| Spaced repetition | FSRS v5 (custom `fsrs.py`) |
| AI | Gemini API (lessons + tutor) |
| Frontend | Vanilla JS ES modules, no build step |

**Entry points:**
- `server.py` — HTTP server and all API handlers
- `db.py` — database layer (includes all PandR logic)
- `fsrs.py` — FSRS v5 algorithm
- `achievements.py` — badge definitions, XP constants, badge groups
- `frequency_data/korean.json` — Korean word frequency (7000 words, OpenSubtitles)
- `frequency_data/spanish.json` — Spanish word frequency (7000 words, OpenSubtitles)
- `scripts/ingest_vtt.py` — CLI: bulk Pimsleur VTT + MP3 → DB
- `scripts/import_apkg.py` — CLI: Anki `.apkg` → DB

---

## Users

| Username | Language | Notes |
|----------|----------|-------|
| robie | Korean | Pimsleur Unit 1 loaded |
| anna | Spanish | No content loaded yet |

---

## Data paths (important for integrity)

All paths are relative to `LANGLAB_DATA_DIR` (default: `./data`).

| What | Path |
|------|------|
| SQLite DB | `study.db` |
| Full lesson MP3 | `languages/<lang>/pimsleur/<unit>/<stem>.mp3` |
| Word audio clips | `languages/<lang>/clips/<lang>/pimsleur/<unit>/<clip>.mp3` |
| `audio_path` DB field | Relative to `languages/` — served at `/audio/<path>` |

The CLI ingest script writes clips to `<unit-dir>/clips/` (source tree).
On the dev machine, symlinks bridge the source tree into the data dir:
- `data/languages/korean/pimsleur` → `~/languages/korean/pimsleur`
- `data/languages/korean/clips` → `~/languages/korean/pimsleur/unit-1/clips`

On the homelab NixOS deployment, `LANGLAB_DATA_DIR` is set to a proper data
volume and the web ingest endpoint writes directly to the correct paths.

---

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `LANGLAB_DATA_DIR` | `./data` | Data root (DB + audio files) |
| `GEMINI_API_KEY` | `""` | Gemini API key for AI lessons and tutor |
| `CLAUDE_API_KEY` | `""` | Claude API key (reserved) |

---

## Tests

```bash
python3 -m unittest discover -s tests -v
```

All tests use in-memory SQLite. No files written to disk. **143 unit tests** (test_db.py, test_server.py, test_vtt.py).
E2E test suite via Playwright: **tests/e2e/** — covers navigation, player, flashcards, admin, mobile, progress view.
