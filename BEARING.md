# Bearing Delegation — langlab
_The Bearing communicates with this project through this file._
_Last updated: 2026-04-12_

---

## Pending

- [ ] **Progress view — streaks and achievements.** Robie asked for this explicitly.
      The current progress view shows session counts and vocab stats. Needs:
      - Study streak (consecutive days with any session logged)
      - Achievements (e.g. "100 words reviewed", "first lesson complete", "7-day streak")
      - Retention curve or FSRS forecast would be nice but is secondary
      Design: add a `/api/progress/<user_id>` endpoint that returns streak + achievement
      data derived from the sessions and reviews tables. Frontend: new section in
      progress.js / view-progress.

- [ ] **Bulk ingest timeout strategy.** 18 lessons × ~300 clips = ~5400 ffmpeg calls.
      A browser upload will time out. Current fix: use CLI for bulk, web UI for
      one-off additions. Longer term: server-sent events (SSE) progress stream, or
      accept a server-side directory path instead of file upload for bulk ingest.
      Not urgent — CLI works fine for now.

## In Progress

- [ ] **Full Pimsleur Unit 1 data load.** The ingest_vtt.py CLI script was fixed
      (Nix ffmpeg PATH, added `import os`, `import glob`) but the ingest run was
      interrupted before completing. The DB is currently empty (was wiped during
      testing). Next step — run this from the langlab directory:

      ```bash
      cd ~/proj/langlab
      python scripts/ingest_vtt.py \
        --lang korean \
        --unit-dir ~/languages/korean/pimsleur/unit-1 \
        --db data/study.db \
        --user robie
      ```

      Then import the Anki vocab deck:
      ```bash
      python scripts/import_apkg.py \
        ~/languages/flashcard-archive/TTMIKs_First_500_Korean_Words_by_Retro_picturesaudio.apkg \
        --user robie --language korean \
        --deck-name "TTMIK First 500 Korean Words"
      ```

      Then start the server and verify in the browser:
      ```bash
      python server.py
      # open http://localhost:8080
      ```

- [ ] **NixOS homelab deployment.** Shelved pending other projects. Full steps in
      ~/proj/langlab/DEPLOY_TODO.md. Still needs: "LangLab env" 1Password item
      (GEMINI_API_KEY + CLAUDE_API_KEY), then langlab-env.age encryption, then
      nixos-anywhere with flipper on VLAN 20.

## Completed

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

## Notes to The Bearing

---

## Context

**Relationship to ~/languages/:**
LangLab is on the path to replacing ~/languages/ functionality. Migration is
incremental — ~/languages/ remains source of truth for now. Specifically:
- `~/languages/study-robie.log` — still authoritative Korean session log
- `~/languages/korean/pimsleur/unit-1/` — Pimsleur VTT + MP3 source files
- `~/languages/flashcard-archive/` — Anki deck source files

**Users:** Robie (Korean) + Anna (Spanish, no Pimsleur yet — waiting on library CDs;
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
