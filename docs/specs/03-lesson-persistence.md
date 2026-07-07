# Spec 03 — Generated-Lesson Persistence + History

_Fable 5, 2026-07-06. Closes docs/issues.md "Lesson persistence and history"
(2026-04-15)._

## Goal

AI-generated lessons (Gemini, `lesson.js`) are currently discarded when a new
one is generated. They should persist per user and accumulate; the lessons view
opens with a growing history list; any past lesson can be reopened; deletion is
explicit per lesson.

## Decisions already made

- Storage is a JSON blob per lesson (same philosophy as `lessons.entries_json`) —
  the Gemini lesson structure stays schema-free.
- Saving happens automatically the moment generation succeeds — no save button.
- History is per user. No sharing between users.
- Add `do_DELETE` to the server (first DELETE route in the codebase).

## Server

### 1. Schema (`db.py` SCHEMA string — new table, `IF NOT EXISTS`)

```sql
CREATE TABLE IF NOT EXISTS generated_lessons (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    language    TEXT    NOT NULL,
    title       TEXT    NOT NULL,
    level       TEXT,
    topic       TEXT,
    lesson_json TEXT    NOT NULL,
    created_at  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_genlessons_user ON generated_lessons(user_id, created_at);
```

### 2. `db.py` methods

```python
def save_generated_lesson(self, user_id, language, title, level, topic, lesson: dict) -> int
def get_generated_lessons(self, user_id: int) -> list[dict]   # metadata only: id, language, title, level, topic, created_at — newest first
def get_generated_lesson(self, lesson_id: int) -> Optional[dict]  # full row, lesson_json parsed to 'lesson'
def delete_generated_lesson(self, lesson_id: int) -> bool     # True if a row was deleted
```

### 3. `server.py` routes

- `POST /api/lessons/generated` body
  `{user_id, language, title, level?, topic?, lesson}` → `{"id": N}`.
  400 if `lesson` missing/not an object or `title` empty.
- `GET /api/lessons/generated/<user_id>` → metadata list.
- `GET /api/lessons/generated/item/<id>` → full lesson; 404 if absent.
- `DELETE /api/lessons/generated/item/<id>` → `{"deleted": true}`; 404 if absent.
  Add `do_DELETE(self)` following the `do_GET`/`do_POST` dispatch shape; keep
  the security headers path identical (they're set in `_send_headers`).

Note the path shapes: `/generated/<int>` is a user listing while
`/generated/item/<int>` is a lesson — the `item/` segment exists to keep the two
integer routes unambiguous. Order the regexes so `item/` matches first.

## Frontend (`lesson.js`, `lessons.css`, `index.html`)

- **On successful generation:** extract a title from the lesson JSON (its title
  field if the prompt already yields one; otherwise first vocab phase heading;
  fallback `"<Language> lesson — <date>"`), POST to
  `/api/lessons/generated`, keep the returned id on the in-memory lesson.
- **View entry state:** when the lessons view opens (`onLessonVisible`), fetch
  the history list. If non-empty, show a **history screen**: "New lesson" button
  on top, then lesson rows (title, level/topic chips, created date, 🗑 button).
  If empty, go straight to the existing generation screen (which gains a small
  "← History" link once history exists).
- **Opening a row** fetches the full lesson and enters the existing lesson
  renderer exactly as a fresh generation would (same phase navigation).
- **Delete:** 🗑 → inline confirm (button swaps to "Delete? ✓ / ✗", no browser
  `confirm()`) → DELETE → remove row. No undo.
- Completing a lesson keeps its existing behavior (session logging, badges).

## Tests

Unit: CRUD round-trip on the four methods; DELETE endpoint 200/404; POST
validation 400s; metadata list omits `lesson_json` (response size discipline);
newest-first ordering.

E2E: generate is not testable without a Gemini key — instead seed a lesson via
the API in the test, then: history list renders, opening renders the lesson
phases, delete removes the row.

## Acceptance criteria

- [ ] Generating a lesson while another exists no longer destroys the previous
      one; both appear in history.
- [ ] History survives server restart (it's in the DB).
- [ ] Delete removes exactly the chosen lesson after inline confirmation.
- [ ] Full suite green; `docs/api.md` documents all four routes incl. the
      `item/` path-shape note; issue closed in `docs/issues.md`.
