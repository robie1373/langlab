# Spec 04 — Vocab-Aware Reading Passage Generator

_Fable 5, 2026-07-06. Implements the TASKS.md / BEARING "vocab-aware reading
passage generator". Reading is Robie's primary real-world study mode; this is
also the feature that makes the Xtein X4 a real Korean reading tool._

## Goal

Generate short reading passages from the user's actual vocabulary: ~90% words
the user knows, ~10% deliberately new. Passages persist, are readable in a new
**Read** view (with tap-to-rate on Korean words), and export as standalone
language-tagged HTML for the X4 pipeline (Calibre `ebook-convert` →
epub-to-xtc-converter).

## Decisions already made

- **Generation runs in the frontend** via the existing `gemini.js` client (the
  key is already exposed to the frontend via `/api/config`; passages follow the
  established pattern — do not build a server-side Gemini proxy).
- **Output format is language-tagged HTML** — every paragraph carries a script
  class: `<p class="ko">` for Korean, `<p class="en">` for English glosses/notes.
  This is a hard contract: the X4 pipeline applies per-language font sizes off
  these classes. No Markdown, no untagged paragraphs, no romanization.
- New words introduced by a passage become real vocab: upserted with
  `source='passage'`, entered into `user_vocab` (state New), and filed into a
  per-user deck **"Passages"** — they flow into the flashcard queue via the
  spec-02 machinery.
- Known-words selection is server-side (SQL), passed to the prompt by the
  frontend.
- Reading a passage logs a `reading` session (spec 01's type) via an explicit
  **Finish reading** button — not on open.

## Server

### 1. Schema (SCHEMA string)

```sql
CREATE TABLE IF NOT EXISTS passages (
    id             INTEGER PRIMARY KEY,
    user_id        INTEGER NOT NULL REFERENCES users(id),
    language       TEXT    NOT NULL,
    title          TEXT    NOT NULL,
    level          TEXT,
    html           TEXT    NOT NULL,
    new_words_json TEXT    NOT NULL DEFAULT '[]',
    created_at     TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_passages_user ON passages(user_id, created_at);
```

### 2. `db.py` methods

```python
def get_known_words(self, user_id: int, language: str) -> dict
```
Returns `{"mastered": [...], "learning": [...]}` of word strings for that
language. Mastered = `state=2 AND stability>=21 AND reps>=3` (the existing
mastery definition — keep in sync with `review_card`). Learning = any other
`user_vocab` row with `reps>=1`. Order both by `frequency_rank` ASC NULLS LAST;
cap mastered at 400 and learning at 200 (prompt-size budget).

```python
def save_passage(self, user_id, language, title, level, html, new_words: list) -> int
def get_passages(self, user_id) -> list[dict]           # metadata: id, language, title, level, created_at, new word count — newest first
def get_passage(self, passage_id) -> Optional[dict]     # full row, new_words_json parsed
def delete_passage(self, passage_id) -> bool
```

`save_passage` additionally, for each `{word, translation}` in `new_words`:
`upsert_word(language, word, translation, source='passage', ...)`,
`ensure_user_vocab`, and file into deck "Passages"
(`ensure_deck(user_id, 'Passages', 'lesson')` + `add_word_to_deck`).

**HTML acceptance check in `save_passage`:** every `<p` tag in `html` must carry
class `ko` or `en` (regex scan). Reject otherwise (`ValueError` → 400) — bad
passages must not reach the X4 pipeline.

### 3. `server.py` routes

- `GET  /api/vocab/known/<user_id>?language=korean` → `get_known_words`
  (language defaults to the user's `default_lang`).
- `POST /api/passages` body `{user_id, language, title, level?, html, new_words?}` → `{"id": N}`.
- `GET  /api/passages/<user_id>` → metadata list.
- `GET  /api/passages/item/<id>` → full passage (same `item/` disambiguation as spec 03).
- `DELETE /api/passages/item/<id>` → `{"deleted": true}` (spec 03's `do_DELETE`).
- `GET  /api/passages/item/<id>/export` → `text/html`, a **complete standalone
  document**: `<!doctype html><html lang="ko"><head><meta charset="utf-8">
  <title>…</title></head><body>` + stored html + `</body></html>` with a
  `Content-Disposition: attachment; filename="passage-<id>.html"` header.
  No CSS, no JS in the export — the pipeline owns styling.

## Prompt (frontend, add to `gemini.js` consumers as `passage.js`)

System/instruction content, exactly this contract (Korean example; parametrize
language):

- You are writing a short Korean reading passage for a learner.
- Use ONLY these known words plus grammatical particles/conjugations:
  `<mastered + learning lists>`.
- Introduce EXACTLY 3–6 new words not on the list, each useful and A1–A2 level.
  Wrap every occurrence of a new word in `<b>…</b>`.
- Length: 80–150 Korean words, 3–6 paragraphs. Simple connected narrative —
  daily-life topics.
- NO romanization anywhere.
- Output STRICT JSON: `{"title": "...", "html": "...", "new_words":
  [{"word": "...", "translation": "..."}]}` where `html` uses `<p class="ko">`
  for every Korean paragraph and `<p class="en">` for the single final
  comprehension-gloss paragraph (1–2 sentence English summary). No other tags
  except `<b>`.

Parse with the existing JSON-extraction pattern in `lesson.js` (Gemini fences
JSON in markdown sometimes — reuse that stripping logic; extract it to a shared
helper if it's currently local).

## Frontend — new **Read** view

New files `frontend/js/passages.js` + `frontend/css/passages.css`; new
`view-passages` block; add to `main.js` nav (label: **Read**, order: after
Lessons).

- **List screen:** "New passage" button (level picker: A1/A2/B1 chips, default
  A1) + passage rows (title, level, date, new-word count, 🗑 inline-confirm
  delete, ⬇ export link pointing at the export route).
- **Generate:** fetch known words → prompt Gemini → validate JSON → POST
  `/api/passages` → open reader. Loading state + error toast on failure
  (missing key → same messaging pattern the lessons view uses).
- **Reader screen:** render stored html directly. `ko` paragraphs large type;
  `en` paragraph visually secondary; `<b>` new words highlighted. **Tap/click
  any Korean word** → the word-rating popover pattern from `player.js`
  (rate via `POST /api/vocab/rate` with `source_lesson='passage/<id>'`).
  Word segmentation: split `ko` paragraph text nodes on whitespace — Korean is
  space-delimited enough for this; strip trailing punctuation from the lookup.
- **Finish reading** button at the bottom: `POST /api/sessions`
  `{user_id, language, session_type:'reading', lesson_path:'passage/<id>'}` →
  jackpot/goal toasts as usual → `checkAchievements` → back to list.

## Tests

Unit: `get_known_words` mastery/learning split + caps + ordering; `save_passage`
creates words/vocab/deck rows exactly once (idempotent on word collision);
`ko|en` class validation rejects unclassed `<p>`; export route returns a full
document with attachment header; passages CRUD; list metadata excludes `html`.

E2E (seed a passage via API, no Gemini): Read view lists it; reader renders ko/en
styling; export link downloads; Finish logs a session (assert via sessions API).

## Acceptance criteria

- [ ] A generated passage persists, renders, exports as standalone tagged HTML
      that the X4 pipeline can consume unmodified.
- [ ] Its new words appear as New cards in the "Passages" deck in the flashcard
      queue.
- [ ] Finishing a passage logs a `reading` session with `lesson_path=passage/<id>`.
- [ ] A passage whose HTML lacks language classes is rejected server-side.
- [ ] Full suite green; docs updated.
