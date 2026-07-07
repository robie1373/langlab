# Spec 02 — Flashcard Deck Management + Session Configuration

_Fable 5, 2026-07-06. Closes docs/issues.md "Flashcard deck management + session
configuration — major rethink" (2026-04-15)._

## Goal

The flashcard **queue screen** is too naive: every card the user owns is pooled
into one undifferentiated queue. Replace the pre-session screen with a deck list
(per-deck status, enable/disable) and session configuration (new-cards cap,
review-only mode). **The review screen itself is good — do not touch the flip
card, rating buttons, keyboard bindings, or done screen** beyond what the queue
hand-off requires.

## Decisions already made

- The `decks` / `deck_words` tables already exist and are populated by the .apkg
  importer (`ensure_deck` / `add_word_to_deck` in `db.py`). They gain an
  `enabled` flag.
- Vocab created outside any deck (word-clicks in the player via `rate_word`)
  gets a per-user system deck named **"From lessons"** (`source='lesson'`).
  A one-time migration files all currently deckless vocab into it; `rate_word`
  files future auto-created entries into it at creation time.
- Session config is **per-user persistent state** in `user_goals`
  (`new_per_session`, default 10; `review_only`, default 0) — not per-session
  ephemeral UI state. The queue screen edits it in place via the goals API.
- Deck filtering happens in SQL in `get_due_cards`, not in the frontend.
- "Study modes" (cram / new-only) from the original issue are **out of scope** —
  review-only + new-cap covers the real need; don't build mode machinery.

## Server

### 1. Migrations (`db.py::_migrate`)

- `decks`: `ALTER TABLE decks ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1`
- `user_goals`: `ALTER TABLE user_goals ADD COLUMN new_per_session INTEGER NOT NULL DEFAULT 10`
  and `ALTER TABLE user_goals ADD COLUMN review_only INTEGER NOT NULL DEFAULT 0`
- **Data migration, idempotent, in `_migrate` after the ALTERs:** for each user
  having `user_vocab` rows whose `word_id` is in none of that user's decks:
  `ensure_deck(user_id, 'From lessons', 'lesson')` then insert the missing
  `deck_words` rows (`INSERT OR IGNORE`).

### 2. `db.py::rate_word`

Where it auto-creates a word + `user_vocab` entry (the by-word-string path),
also file the word: `ensure_deck(user_id, 'From lessons', 'lesson')` +
`add_word_to_deck`.

### 3. New `db.py` methods

```python
def get_decks(self, user_id: int) -> list[dict]
```
Per deck of this user: `id, name, source, enabled, total, new, learning, review, due`.
Counts join `deck_words` → `user_vocab` (same user): `new` = state 0, `learning`
= state 1 or 3, `review` = state 2, `due` = `due_at IS NULL OR due_at <= now`.
A word in two decks counts in both (acceptable; decks are curated sources).

```python
def set_deck_enabled(self, deck_id: int, enabled: bool) -> None
```

### 4. `db.py::get_due_cards` — new signature

```python
def get_due_cards(self, user_id: int, limit: int = 50,
                  new_cap: int = None, review_only: bool = False) -> list[dict]
```

- Add to the WHERE clause: the word must belong to at least one **enabled** deck
  of this user (`EXISTS` subquery over `deck_words JOIN decks`).
- `review_only=True`: exclude `due_at IS NULL` rows entirely.
- `new_cap` (when not None and not review_only): at most `new_cap` new cards
  (`due_at IS NULL`) in the result; due cards keep priority. Implement as two
  queries (due first, then new with `LIMIT new_cap`, concatenated, total capped
  at `limit`) — simpler and testable, same ordering semantics as today
  (due sorted by `due_at` ASC; new randomized).

### 5. `server.py`

- `GET /api/decks/<user_id>` → `get_decks` result.
- `POST /api/decks/<deck_id>` body `{"enabled": 0|1}` → `set_deck_enabled`,
  respond `{"id": <deck_id>, "enabled": <0|1>}`.
- `GET /api/flashcards/due/<user_id>` now reads `user_goals` for
  `new_per_session` / `review_only` and passes them to `get_due_cards`. No new
  query params — config lives server-side.
- `POST /api/goals/<user_id>` (existing) accepts optional `new_per_session` and
  `review_only` alongside `daily_cards`; `GET /api/goals/<user_id>` returns them.

## Frontend

Rework the **queue screen** only (`fc-queue` block in `index.html`,
`flashcards.js` queue functions, `flashcards.css`). Visual quality must match
the review screen: same card aesthetics, design-system variables, rarity-glow
polish level.

Layout, top to bottom:

1. **Header row:** due-count headline (existing `fc-due-number` semantics) +
   the daily goal ring (keep `renderGoalRing` as is).
2. **Deck list:** one card per deck: name, source chip (`imported`/`lesson`),
   counts (`new / learning / review / due` — color-coded consistently with FSRS
   state colors used elsewhere), and an enable toggle (styled checkbox). Toggling
   POSTs `/api/decks/<id>` then re-fetches decks + due queue and re-renders.
   Disabled decks render dimmed.
3. **Session config row:** stepper `New cards per session: [–] 10 [+]`
   (0–50) and a `Review only` checkbox. Changes POST `/api/goals/<user_id>`
   (debounced 300ms) then refresh the due queue.
4. **Start button:** existing `fc-start-btn`; label shows what a session will
   be, e.g. `Start — 23 due + 10 new`. Disabled when the effective queue is empty.

The review flow (`startReview` onward) is unchanged — it consumes whatever
`refresh()` fetched.

## Tests

Unit:
- Migration files deckless vocab into "From lessons" (build a DB with orphan
  `user_vocab`, run `_migrate` — it runs in `Database.__init__` — assert filing).
- `rate_word` by-string files new words into "From lessons".
- `get_decks` counts (fixture with known states/due dates).
- `get_due_cards`: disabled deck's cards excluded; `review_only` excludes new;
  `new_cap=0` ≡ review_only for the new portion; `new_cap=3` yields ≤3 new.
- Endpoints: deck list shape, toggle round-trip, goals round-trip with new fields.

E2E: queue screen renders deck list; toggling a deck changes the due count;
review-only hides new cards from the start label; a full review session still
completes (regression on the untouched review screen).

## Acceptance criteria

- [ ] Every card reachable in review belongs to ≥1 enabled deck; disabling all
      decks empties the queue and disables Start.
- [ ] New-cards cap and review-only persist across sessions and users
      independently.
- [ ] Review screen behavior byte-for-byte unchanged (keyboard map, XP, toasts).
- [ ] Existing 143+ unit tests still green; new tests added; docs updated.
