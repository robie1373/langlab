# Bearing Delegation — langlab
_The Bearing communicates with this project through this file._
_Last updated: 2026-04-13_

---

## Pending

- [ ] **Manual session logging UI.** Need a UI to log a session by hand (away from LangLab).
      Dropdown of session types + optional fields (language, lesson path, notes, date).
      Manual sessions must be treated identically to auto-logged for streaks/XP/badges.
      `POST /api/sessions` already supports a `timestamp` override — UI just needs building.

- [ ] **Flashcard deck picker.** Flashcard queue screen needs a way to select which decks
      are included, see status of each (new/learning/review counts), and filter by language.
      Currently all user vocab is pooled into one queue.

- [ ] **CEFR tracker.** Phase A: estimated level computed from vocab mastered count +
      session count (A1: ~150 mastered + 10 lessons; A2: ~500 mastered; etc.). Always
      aspirational framing — "Estimated: working toward A2". Phase B: Gemini-generated
      simulated mastery test, earns permanent designation badge. Can always retake,
      no penalty. Framed as a reward to seek, not a gate to pass.

- [ ] **Streak Chronicle UI.** The DB already stores streak_chapters (past run lengths +
      badges earned per chapter). Need a UI: a "trophy shelf" row in the progress view
      showing each chapter as a card with its length and whether it was a personal best.
      The "New Game+" framing — total_days always grows even if streak resets.

- [ ] **Leaderboard (Anna's UI only).** Weekly XP: Anna vs. Robie. Opt-in via
      `show_leaderboard` field in user_goals (already in DB). Anna's progress view only.
      Robie's UI must never show it.

- [ ] **Login page parallax visual.** User picker redesign: each user tile is a floating
      cloud with their colour (Robie = forest green, Anna = royal blue). Subtle parallax
      PandR elements (badge icons, XP numbers) drifting in background.

- [ ] **Bulk ingest timeout strategy.** 18 lessons × ~300 clips = ~5400 ffmpeg calls.
      A browser upload will time out. Current fix: use CLI for bulk, web UI for
      one-off additions. Longer term: server-sent events (SSE) progress stream, or
      accept a server-side directory path instead of file upload for bulk ingest.
      Not urgent — CLI works fine for now.

## In Progress

- [ ] **NixOS homelab deployment.** Shelved pending other projects. Full steps in
      ~/proj/langlab/DEPLOY_TODO.md. Still needs: "LangLab env" 1Password item
      (GEMINI_API_KEY + CLAUDE_API_KEY), then langlab-env.age encryption, then
      nixos-anywhere with flipper on VLAN 20.

## Completed

- [x] **Progress & Rewards (PandR) suite** — full gamification suite (2026-04-12/13):
      - Streaks: current/best/total_days. "New Game+" framing — missed day resets streak
        quietly, total_days never goes down, streak_chapters table archives past runs.
      - 52-week GitHub-style heat map in progress view.
      - 27 achievement badges across 7 groups (first_steps, streaks, chapters, lifetime,
        volume, mastery, exploration). Real-time toast on award.
      - XP system: 50–150/review (by rating), 200–2500/mastery (by rarity), 100–1000/session
        (by type), 500 XP/daily goal met.
      - Card rarity: Fundamental (gold) / Essential (purple) / Interesting (green) / Niche (white).
        Assigned from frequency rank at ingest. JSON frequency lists for Korean (7000 words)
        and Spanish (7000 words) in `frequency_data/`. Borders + glow on flashcard faces.
      - Daily goal ring (SVG) on flashcard queue screen. GET/POST /api/goals/<id>.
      - Jackpot: pity-guaranteed once every ~3 sessions. 20%→60%→90%→100% probability
        over sessions 1–5. 4 prize types. Jackpot returned in POST /api/sessions response.
      - Real-time toasts: badge awarded, XP event, mastery achievement, jackpot.
        Toast fires immediately on the triggering event, not batched at session end.
      - checkAchievements() wired into flashcard review, session log, tutor end, AI lesson.
      - SQLite localtime bug fixed: all date() calls now use 'localtime' modifier so UTC
        timestamps compare correctly to local calendar date (was wrong after ~8pm EDT).
      - 143 unit tests passing. 20 new e2e tests in tests/e2e/test_progress.py.
      New API endpoints: GET /api/progress/<id>, GET /api/achievements/<id>,
      POST /api/achievements/check/<id>, GET /api/goals/<id>, POST /api/goals/<id>,
      POST /api/admin/backfill-rarity/<language>.
      POST /api/sessions now returns {id, jackpot, goal} instead of bare int.

- [x] **Flashcard fixes** (2026-04-12):
      - Ordering: new cards now randomised via RANDOM(), not insertion order.
      - End-session: "End" button + Escape key during review — shows partial results if
        any cards were rated, returns to queue screen otherwise.

- [x] Phase 1 — server, SQLite + FSRS v5, VTT player SPA, Docker deploy (2026-04-10)
- [x] Phase 2 — flashcards, AI lessons (Gemini), conversational tutor with voice I/O,
      vocab browser, Anki .apkg import, progress view. 134/134 tests green. (2026-04-11)
- [x] Mobile UI fixes + hamburger menu (2026-04-11)
- [x] LANGLAB_DATA_DIR env var support in server.py (2026-04-11)
- [x] NixOS service module, host config, disko, secrets wired in nixos-config (2026-04-11)
- [x] Library / admin view (⚙ nav tab) with:
      - GET /api/admin/library — vocab + lesson counts
      - POST /api/admin/import-apkg — multipart .apkg upload → vocab
      - POST /api/admin/ingest-vtt — multipart VTT+MP3 → lessons + word audio clips
      - Drag-and-drop UI, unit name field, log panel (2026-04-12)
- [x] VTT ingest parity with CLI: correct pimsleur/<unit>/<lesson> paths,
      ffmpeg word audio clip extraction, Nix store ffmpeg fallback (2026-04-12)
- [x] CLI script (ingest_vtt.py) fixed: added `import os`, `import glob`,
      Nix store ffmpeg PATH injection (2026-04-12)
- [x] Full data load: Pimsleur Unit 1 (18 lessons, ~1813 clips) + TTMIK 500 words
      imported. Audio symlinks bridging source tree → data dir for dev. (2026-04-12)
- [x] docs/ directory: index.md, api.md, issues.md, runbooks/start-server.md,
      runbooks/data-load.md (2026-04-12)
- [x] Test suite expanded: 190/190 green. Added TestLibraryStats (db.py),
      TestAdminLibraryEndpoint (server.py), TestParseVttText, TestPairKorean,
      TestTcToSecs, TestIngestVttParseVtt, TestIngestVttPairEntries (2026-04-12)
- [x] E2E test suite: 59/59 passing via flake.nix + Playwright. Covers all views,
      mobile hamburger menu, flashcard review flow, player text rendering. (2026-04-12)
      Fixed two real app bugs discovered by tests:
      1. startSession race: navigate(defaultView) was called after slow async inits,
         clobbering user navigation. Fixed: navigate fires immediately after buildAppBar.
      2. Player never rendered text: loadLesson used lesson metadata (no entries).
         Fixed: loadLesson now fetches full lesson data from /api/lessons/<lang>/<path>
         on first use, cached on the lesson object. (2026-04-12)

## Notes to The Bearing

---

## Context

**LangLab supersedes:**
- `~/languages/` — study CLI and session log infrastructure (BEARING.md archived, CLAUDE.md slimmed; data remains authoritative)
- **habla** (homeLab VMID 104) — Castilian Spanish Docker app
- **teacha** — earlier standalone language tool

**~/languages/ still owns (until migration complete):**
- `study-robie.log` — authoritative Korean session log (TSV)
- `korean/pimsleur/unit-1/` — Pimsleur VTT + MP3 source files (symlinked into LangLab data dir)
- `flashcard-archive/` — Anki source decks (importable via `scripts/import_apkg.py`)
- `study.sh` — day-to-day CLI for logging sessions

**Anki state (as of 2026-04-07, for reference):** 905 lifetime reviews, 81.3% retention.
Lang/Pimsleur companion L1 complete through Lessons 01–04. Korean Core 5k (4,996 cards) not started.
LangLab's FSRS replaces Anki going forward; existing decks can be imported via import_apkg.py.

**Users:** Robie (Korean — Pimsleur Unit 1 loaded) + Anna (Spanish, no Pimsleur yet — waiting on library CDs;
Language Transfer Complete Spanish suggested as interim)

**Stack:** Python stdlib HTTP server, SQLite, FSRS v5, vanilla JS SPA, Gemini API

**Deploy target:** homeLab NixOS (shelved; all infra ready, blocked on API keys +
VLAN 20 access)

**Key path conventions (important for data integrity):**
- Lessons: `pimsleur/<unit-name>/<lesson-stem>` (e.g. `pimsleur/unit-1/lesson-01`)
- Full MP3: `DATA_DIR/languages/<lang>/pimsleur/<unit>/<stem>.mp3`
- Word clips: `DATA_DIR/languages/<lang>/clips/<lang>/pimsleur/<unit>/<clip>.mp3`
- DB audio_path field: relative to `DATA_DIR/languages/` (served at `/audio/<path>`)
- These paths must match between CLI scripts and server endpoints — they now do.

**ffmpeg note:** Not on PATH in Nix dev environment. Both server.py and
ingest_vtt.py now fall back to glob `/nix/store/*ffmpeg*/bin/ffmpeg`. On NixOS
deployment, ffmpeg will be in PATH via system packages in langlab.nix.
