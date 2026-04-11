# LangLab — Session Checkpoint

## Status: Phase 2 complete, 134/134 tests green

## What was built

### Phase 1 (complete)
- `server.py` — Python stdlib HTTP server (no frameworks)
- `db.py` — SQLite database layer with FSRS v5 integration
- `fsrs.py` — FSRS v5 spaced repetition algorithm
- `docker-compose.yml` + `Dockerfile` — containerized deployment
- `scripts/ingest_vtt.py` — ingest Pimsleur VTT + MP3 into DB
- `frontend/js/main.js` — SPA router, user picker, dark mode
- `frontend/js/player.js` — VTT player with vocab indicators, word rating card
- `frontend/js/ui.js` — shared UI helpers (showView, showToast, showLoading)
- `frontend/css/main.css` — design system (CSS variables, layout, player styles)
- `frontend/index.html` — SPA shell
- Users: Robie (Korean/Pimsleur) + Anna (Spanish)

### Phase 2 (complete, this session)
- `frontend/js/flashcards.js` + `frontend/css/flashcards.css` — FSRS flashcard review loop, flip animation, Again/Hard/Good/Easy, keyboard shortcuts, session wrap-up
- `frontend/js/gemini.js` — Gemini REST API client, model fallback (gemini-2.0-flash → gemini-1.5-flash), retry with backoff, streaming support
- `frontend/js/speech.js` — Web Speech API wrapper, language-configurable TTS + STT
- `frontend/js/lesson.js` + `frontend/css/lessons.css` — AI-generated lessons via Gemini, language-aware (Korean: 한글-only no romanization; Spanish: Castilian), phases: vocab → grammar → reading/dialogue → culture → summary
- `frontend/js/tutor.js` + `frontend/css/tutor.css` — Conversational AI tutor, voice input/output, per-language system prompts (Korean tutor 지수 for Robie; Spanish tutor Elena for Anna), per-turn feedback panel, goodbye detection
- `frontend/js/vocab.js` + `frontend/css/vocab.css` — Vocabulary browser, state filters (New/Learning/Review), reps + due date
- `frontend/js/progress.js` — Session history + vocab stats by state
- `scripts/import_apkg.py` — Import Anki .apkg decks into LangLab DB; `--dry-run`, configurable field mapping
- `frontend/index.html` — All phase-2 view HTML wired in (no more "coming soon" placeholders)
- `frontend/js/main.js` — All modules wired up; Gemini API key loaded on startup

### Tests
- `tests/test_fsrs.py` — 36 tests, FSRS algorithm
- `tests/test_db.py` — 48 tests, DB layer
- `tests/test_server.py` — 6 tests, HTTP server integration
- `tests/test_import_apkg.py` — 44 tests, .apkg importer + /api/config + AI session types
- **Total: 134/134 passing**

### Bug fixed this session
`db.py` `upsert_word`: was using `cur.lastrowid or SELECT...`. In SQLite 3.51.2, `last_insert_rowid()` is NOT updated when `ON CONFLICT DO UPDATE` fires after another INSERT on the same connection. Fixed to always use explicit SELECT — reliable across all SQLite versions.

## Repo
`git@github.com:robie1373/langlab.git` — branch `main`, commit `8931e30`

## Running the server
```bash
cd ~/proj/langlab && nix-shell -p python3 --run 'python3 server.py'
```
Serves on port 8080. DB at `data/study.db`.

## Running tests
```bash
cd ~/proj/langlab && nix-shell -p python3 --run 'python3 -m unittest discover -v tests 2>&1 | grep -E "^(Ran|OK|FAIL|ERROR)"'
```

## Ingesting Pimsleur lessons
```bash
cd ~/proj/langlab && nix-shell -p python3 --run 'python3 scripts/ingest_vtt.py <path-to-vtt> <path-to-mp3>'
```

## Importing Anki decks
```bash
cd ~/proj/langlab && nix-shell -p python3 --run 'python3 scripts/import_apkg.py deck.apkg --user robie --language korean'
# --dry-run to preview field mapping first
```

## Next priorities (not yet done)
1. Visual review of the full UI (Robie wanted to do this next)
2. Deploy to homeLab (Docker Compose, ntfy pattern)
3. Progress view — flesh out or leave as-is
4. Phase 3 ideas: vocabulary from AI lesson added to user's deck, Korean → Spanish for Anna's lessons via user language setting (deferred to v2.0)

## Key design decisions on record
- No romanization for Korean anywhere — 한글 only
- Lesson language is tied to user's `default_lang`, not a session setting (v2.0 to revisit)
- Anki replaced by own FSRS implementation; .apkg import for existing decks
- Multi-user but no auth — user picker only
- No external Python deps — stdlib only (sqlite3, http.server, zipfile, etc.)
- Frontend: vanilla JS ES modules, no build step, no framework
