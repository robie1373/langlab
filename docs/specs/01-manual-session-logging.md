# Spec 01 — Manual Session Logging + Study-Log Backfill

_Fable 5, 2026-07-06. Closes docs/issues.md "manual session logging" (2026-04-12)._

## Goal

Robie studies away from LangLab constantly — reading (KMS textbook, X4 e-reader),
video (Lingopie), Anki history. None of it can be recorded today, so streaks, XP,
and the heatmap reflect a fraction of real study. Two deliverables:

- **A.** A UI + API path to log a session by hand, counting identically to
  automatic sessions for streaks/badges/XP.
- **B.** A one-shot CLI importer for the historical TSV log
  `~/languages/study-robie.log` (61 entries, 2026-03-23 → 2026-05-20). This
  completes the ~/languages → LangLab migration.

## Decisions already made

- Manual sessions are ordinary rows in `sessions` — no `is_manual` flag.
- New canonical session types: `reading`, `listening`, `video`, `anki` join the
  existing `pimsleur`, `flashcard`, `ai_lesson`, `tutor`, `free`.
- Sessions gain an optional `duration_sec` column.
- **Backdating rule:** a session whose `timestamp` is not today (localtime) earns
  session XP (timestamped at the session's own time) but must NOT roll the
  jackpot and must NOT trigger the daily-goal check. Jackpots and goal pings are
  live-play rewards; backdated entries are bookkeeping.
- The backfill importer bypasses `log_session` entirely (no XP, no jackpot): raw
  history should light up streaks/heatmap/total_days (which derive from the
  `sessions` table — see `get_progress`) without minting 61 sessions' worth of XP.

## Part A — server

### 1. Migration (`db.py::_migrate`)

Add, using the existing `PRAGMA table_info` pattern (table: `sessions`):

```sql
ALTER TABLE sessions ADD COLUMN duration_sec INTEGER
```

### 2. `achievements.py`

Extend `XP_SESSION`:

```python
XP_SESSION = {
    'pimsleur':   500,
    'flashcard':  100,
    'ai_lesson':  750,
    'tutor':      1000,
    'reading':    300,
    'listening':  300,
    'video':      300,
    'anki':       100,
    'free':       300,
}
```

### 3. `db.py::log_xp`

Add optional `timestamp: str = None` parameter; use it instead of `_now_iso()`
when provided. All existing call sites unchanged.

### 4. `db.py::log_session`

- Accept and store `duration_sec` (`body.get('duration_sec')`).
- Compute `backdated`: parse `body.get('timestamp')`; backdated iff its local
  date ≠ today's local date. (No timestamp in body → not backdated.)
- If backdated: pass the session's timestamp to `log_xp`; skip `_roll_jackpot`
  (return `jackpot: None`) and skip the entire daily-goal block.
- If not backdated: behavior unchanged.

### 5. `db.py::check_and_award` — multimodal badge

The set at the "multi-modal" check currently hardcodes
`{'pimsleur','flashcard','ai_lesson','tutor','free'}`. Change the fifth slot so
any of `free/reading/listening/video/anki` satisfies it:

```python
core = {'pimsleur', 'flashcard', 'ai_lesson', 'tutor'}
solo = {'free', 'reading', 'listening', 'video', 'anki'}
if core.issubset(session_types_this_week) and (solo & session_types_this_week):
    award('multimodal')
```

### 6. `server.py`

`POST /api/sessions` already routes to `log_session` — no route change. Update
the response only if needed (jackpot may now be null for backdated sessions;
the frontend already handles null).

## Part B — frontend

### Placement

Progress view (`view-progress`). Add a `+ Log a session` button in the view's
header row, opening a modal (build the modal in `index.html`, hidden by default,
styled in `pandr.css` using existing design-system variables).

### Modal fields

| Field | Control | Default | Required |
|---|---|---|---|
| Type | `<select>`: Reading, Listening, Video, Anki, Pimsleur, Other | Reading | yes |
| When | `<input type="datetime-local">` | now | yes |
| Duration (minutes) | `<input type="number" min="1">` | empty | no |
| Language | `<select>` from users' languages | user's `default_lang` | yes |
| What (lesson/source) | `<input type="text" placeholder="e.g. KMS chapter 3">` | empty | no |
| Notes | `<textarea>` | empty | no |

Type values map: Reading→`reading`, Listening→`listening`, Video→`video`,
Anki→`anki`, Pimsleur→`pimsleur`, Other→`free`. "What" posts as `lesson_path`,
minutes ×60 as `duration_sec`. Convert the datetime-local value to an ISO-8601
string **with the local UTC offset** (e.g. `2026-07-06T14:30:00-04:00`), not a
bare naive string — `date(timestamp,'localtime')` must resolve correctly.

### Behavior

- Submit → `POST /api/sessions` → on success: close modal, `showToast('Session logged')`,
  `checkAchievements(user.id)`, re-render the progress view (re-fetch progress data).
- If the response contains a non-null `jackpot`, show it with the existing
  jackpot toast pattern (see `flashcards.js::showJackpot` — extract it to
  `toast.js` as `showJackpot(jp)` and import from both places rather than
  duplicating).
- Escape or ✕ closes the modal without posting.

## Part C — backfill importer

New file `scripts/import_study_log.py`, stdlib only, style of
`scripts/import_apkg.py` (argparse, `--dry-run`).

```
python3 scripts/import_study_log.py ~/languages/study-robie.log --user robie [--db data/study.db] [--dry-run]
```

### Input format (TSV, two variants — both present in the real file)

- 3 columns: `timestamp  language  mp3-path` (e.g. `korean/pimsleur/unit-1/lesson-01.mp3`)
  → `session_type='pimsleur'`, `lesson_path` = path minus the leading
  `<language>/` and the `.mp3` suffix (→ `pimsleur/unit-1/lesson-01`),
  `duration_sec=NULL`.
- 4–5 columns: `timestamp  language  free:<subtype>  duration_sec  [note]`
  → mapping: `free:reading`→`reading`; `free:books:*`→`reading` with the subtype
  appended to notes (e.g. note becomes `kp262 — <original note>`); `free:anki`→`anki`;
  `free:other`→`free`. Unknown `free:*` subtypes → `free` (keep subtype in notes).
  Column 4 is duration in seconds; column 5 (optional) is notes.

Skip blank lines. A malformed line (unparseable timestamp or <3 columns) is an
error: print it and exit non-zero without writing anything.

### Behavior

- Resolve `--user` name → `users.id`; error if missing.
- **Idempotent:** skip any line where a `sessions` row with the same
  `(user_id, timestamp)` already exists; count and report skips.
- Insert directly into `sessions` (user_id, timestamp, language, session_type,
  lesson_path, notes, duration_sec). **Do not call `log_session`** — no XP, no
  jackpot, no goal side effects.
- After inserting, **rebuild streak chapters** for the user:
  1. `DELETE FROM streak_chapters WHERE user_id=?`
  2. Collect `SELECT DISTINCT date(timestamp,'localtime') ... ORDER BY day` for
     the user; split into runs of consecutive calendar days.
  3. Every run **except the most recent** becomes a chapter row
     (`start_date`, `end_date`, `length`, `was_best` = 1 iff length strictly
     exceeds the max length of all earlier runs). The most recent run is the
     live streak, not a chapter.
- `--dry-run`: print the parsed mapping table (timestamp, type, lesson_path,
  duration, notes) and the would-be chapter list; write nothing.
- Report at the end: `imported N, skipped M, chapters rebuilt K`.

### Post-import (manual, one time — put this in the final report to Robie, do not run it)

Run against production after shipping:

```
ssh root@langlab.home.lab
cd /var/lib/langlab && python3 /nix/store/.../scripts/import_study_log.py …
```

(The operator locates the deployed source path; the importer takes `--db /var/lib/langlab/study.db`.)

## Tests

Unit (`tests/test_db.py`, `tests/test_server.py`, new `tests/test_import_study_log.py`):

- `log_session` stores `duration_sec`; returns it in `get_sessions` rows.
- Backdated session: XP event carries the session's timestamp; no jackpot; no
  daily-goal XP even when today's reviews exceed the goal.
- Today-dated manual session: behaves exactly like the current flow (jackpot
  rolls, goal check runs).
- `log_xp` honors explicit timestamp.
- Importer: parses both TSV variants; the `free:books:kp262` line maps to
  `reading` + note prefix; idempotency (second run imports 0); streak-chapter
  rebuild produces the correct runs for a hand-built date set with two gaps;
  malformed line aborts with no partial writes (wrap in one transaction).
- Multimodal badge: awarded with `reading` filling the fifth slot.

E2E (`tests/e2e/`): open progress view → log a manual session via the modal →
progress heatmap/session list reflects it.

## Acceptance criteria

- [ ] A session logged via the modal appears in `GET /api/sessions/<id>` and
      moves `today_reviews`-independent stats (heatmap, total_days, streak).
- [ ] A backdated session neither rolls a jackpot nor awards daily-goal XP.
- [ ] Running the importer twice on the real log file yields `imported 61` then
      `imported 0, skipped 61` (both under `--db` pointing at a scratch copy).
- [ ] Streaks/heatmap/total_days reflect the imported history; XP total is
      unchanged by the import.
- [ ] Full unit suite green; docs updated.
