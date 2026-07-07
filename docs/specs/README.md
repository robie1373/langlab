# LangLab Feature Specs — Executor Ground Rules

_Authored by Fable 5, 2026-07-06, from a design session with Robie. These specs are
written to be executed by a smaller model without further judgment calls. Where a
decision was needed, it has already been made and is stated in the spec. Do not
re-open decided questions; if a spec is genuinely wrong (contradicts the code you
find), stop and report rather than improvising._

## Execution order

Specs are numbered by priority. Do them in order; each is one self-contained work
session ending in green tests and a commit.

| Spec | Feature | Why this order |
|------|---------|----------------|
| [01](01-manual-session-logging.md) | Manual session logging + study-log backfill | Makes LangLab the system of record for ALL study; lights up streaks/XP with real history |
| [02](02-deck-management.md) | Flashcard deck management + session config | Fixes the entry point to the daily review loop |
| [03](03-lesson-persistence.md) | Generated-lesson persistence + history | AI lessons stop evaporating |
| [04](04-reading-passages.md) | Vocab-aware reading passage generator | Robie's primary study mode is reading; feeds the X4 pipeline |
| [05](05-progress-polish.md) | Streak Chronicle, CEFR estimate, leaderboard, login visual | Cosmetic/motivational layer; cheap after the above |

## Hard constraints (violating any of these fails the work)

1. **Python stdlib only.** No pip packages, no venv. `sqlite3`, `http.server`,
   `json`, `re`, `urllib` etc. The deployed host runs `python3 server.py` with
   nothing installed.
2. **Vanilla JS ES modules, no build step, no framework.** Frontend files are
   served as-is from `frontend/`.
3. **No romanization for Korean anywhere.** 한글 only. Never add romanized Korean
   to UI, prompts, or generated content.
4. **SQLite date comparisons must use the `'localtime'` modifier** when comparing
   stored UTC timestamps to calendar dates (see existing `date(timestamp,'localtime')`
   calls in `db.py`). Getting this wrong breaks streaks after ~8pm EDT — it has
   happened before.
5. **All tests green before commit:** `python3 -m unittest discover -s tests -v`.
   Every new endpoint and every new `Database` method gets unit tests in the
   existing style (in-memory SQLite, no files on disk). E2E tests (`tests/e2e/`,
   Playwright via `flake.nix`) should be extended where a spec says so.
6. **Schema changes:** new tables go in the `SCHEMA` string in `db.py`
   (`CREATE TABLE IF NOT EXISTS` — idempotent). New columns on existing tables go
   in `Database._migrate()` using the existing `PRAGMA table_info` pattern.
   Never edit an existing `CREATE TABLE` for a column addition — deployed DBs
   won't re-run it.
7. **Documentation:** after each spec, update `docs/api.md` (new endpoints) and
   `docs/issues.md` (close the matching issue with date). Do not update
   `BEARING.md` — it is historical; The Ledger (`~/ledger2/langlab.md`) is
   authoritative and is updated by The Bearing, not by this work.

## Code conventions (match these exactly)

- **Server routing:** regex dispatch inside `do_GET` / `do_POST` in `server.py`
  (`elif m := re.match(r'^/api/...$', path):`). Responses via `self._json(data)`
  and `self._json({'error': msg}, status)`. Request bodies via `self._read_body()`.
  There is currently no `do_DELETE`; spec 03 adds one — follow the same dispatch shape.
- **DB layer:** all SQL lives in `db.py` `Database` methods; handlers call them.
  Rows out via `_row_to_dict`. Commit inside each method.
- **Frontend modules:** one JS file + one CSS file per view. Each module exports
  `init<Name>(currentUser)`; views are `<div id="view-x" class="view">` blocks in
  `index.html`; navigation via `navigate(viewId)` in `main.js` (add new views to
  its nav list). Toasts via `showToast` (`ui.js`) and the PandR toasts in `toast.js`.
  Fire `checkAchievements(user.id)` (from `progress.js`) after anything that could
  earn a badge.
- **CSS:** use the design-system variables in `main.css`. New view CSS files must
  be `<link>`ed in `index.html`.
- **Commits:** small and atomic, imperative mood, no "I"/"Claude"/"we". Prefix
  not needed (single repo).

## Deployment reality (so you don't chase ghosts)

- Production runs on the `langlab` NixOS VM (192.168.20.11) from a **pinned flake
  input** (`github:robie1373/langlab`). Shipping = commit + push to `main`; the
  host picks it up at its next `flake.lock` bump (weekly patch automation, or
  Robie bumps manually). You cannot hot-deploy from here.
- Access is **plain HTTP** at `http://langlab.home.lab` (LAN only, since
  2026-07-06). Anything requiring a browser secure context (SpeechRecognition,
  clipboard API, etc.) will NOT work in production until the VLAN 20 Let's
  Encrypt proxy exists. Do not build features that depend on a secure context;
  `speechSynthesis` (TTS) is fine.
- Dev server: `cd ~/proj/langlab && python3 server.py` (port 8080, data in
  `./data/`). Gemini features need `GEMINI_API_KEY` in the environment.

## Definition of done (per spec)

- [ ] All acceptance criteria in the spec checked off
- [ ] Unit tests added; full suite green
- [ ] E2E tests added/updated if the spec says so
- [ ] `docs/api.md` and `docs/issues.md` updated
- [ ] Committed (and pushed only if asked)
