# LangLab REST API Reference

> Base URL: `http://localhost:8080`
> All API responses are JSON unless noted.
> All `POST` endpoints accept `Content-Type: application/json` unless noted.

---

## Users

### `GET /api/users`

Returns all users.

**Response `200`:**
```json
[
  {
    "id": 1,
    "name": "robie",
    "display_name": "Robie",
    "default_lang": "korean"
  },
  {
    "id": 2,
    "name": "anna",
    "display_name": "Anna",
    "default_lang": "spanish"
  }
]
```

---

## Config

### `GET /api/config`

Returns runtime API key availability (values are empty strings if not set).
Used by the frontend to decide whether AI features are available.

**Response `200`:**
```json
{
  "gemini_api_key": "AIza...",
  "claude_api_key": ""
}
```

---

## Lessons

### `GET /api/lessons/<lang>`

Lists all lessons for a language, sorted by `lesson_path`.

**Parameters:**
- `lang` — language code (`korean`, `spanish`, …)

**Response `200`:**
```json
[
  {
    "id": 1,
    "language": "korean",
    "lesson_path": "pimsleur/unit-1/lesson-01",
    "title": "Lesson 01",
    "mp3_path": "korean/pimsleur/unit-1/lesson-01.mp3"
  }
]
```

Returns `[]` for an unknown language (not a 404).

---

### `GET /api/lessons/<lang>/<lesson_path>`

Returns the full lesson data including all VTT entries.

**Parameters:**
- `lang` — language code
- `lesson_path` — path like `pimsleur/unit-1/lesson-01`

**Response `200`:**
```json
{
  "id": 1,
  "language": "korean",
  "lesson_path": "pimsleur/unit-1/lesson-01",
  "title": "Lesson 01",
  "mp3_path": "korean/pimsleur/unit-1/lesson-01.mp3",
  "entries": [
    {
      "start": 9.38,
      "end": 9.78,
      "lines": ["안녕하세요."],
      "korean": ["안녕하세요."]
    }
  ]
}
```

**Response `404`:** Lesson not found.

---

## Vocabulary

### `GET /api/vocab/<user_id>`

Returns all vocabulary entries for a user, with FSRS scheduling state.

**Response `200`:**
```json
[
  {
    "id": 42,
    "language": "korean",
    "word": "안녕하세요",
    "translation": "Hello",
    "audio_path": "korean/clips/korean/pimsleur/unit-1/lesson-01_abc123.mp3",
    "state": 2,
    "stability": 14.3,
    "due_at": 1713052800,
    "reps": 5,
    "lapses": 0
  }
]
```

**FSRS state values:** `0` = New, `1` = Learning, `2` = Review, `3` = Relearning

---

### `POST /api/vocab/rate`

Rate a word from the VTT player (inline word-click review). Creates the word
and vocab entry if they don't exist yet (for transcript words not yet formally ingested).

**Body (by word_id):**
```json
{
  "user_id": 1,
  "word_id": 42,
  "rating": 3,
  "time_ms": 1500
}
```

**Body (by word string — auto-creates entry):**
```json
{
  "user_id": 1,
  "word": "감사합니다",
  "language": "korean",
  "rating": 3,
  "translation": "Thank you",
  "source_lesson": "pimsleur/unit-1/lesson-01"
}
```

**Rating values:** `1` = Again, `2` = Hard, `3` = Good, `4` = Easy

**Response `200`:**
```json
{
  "word_id": 42,
  "state": 1,
  "due_at": 1713052800,
  "reps": 1
}
```

---

## Flashcards

### `GET /api/flashcards/due/<user_id>`

Returns due cards for a user (up to 50). New cards (no `due_at`) are always included.

**Response `200`:**
```json
[
  {
    "word_id": 42,
    "word": "안녕하세요",
    "translation": "Hello",
    "audio_path": "korean/clips/...",
    "state": 0,
    "stability": 0.0,
    "difficulty": 0.0,
    "reps": 0,
    "lapses": 0,
    "elapsed_days": 0.0,
    "scheduled_days": 0.0,
    "due_at": null,
    "last_review": 0.0
  }
]
```

---

### `POST /api/flashcards/review`

Record a flashcard review and advance the FSRS schedule.

**Body:**
```json
{
  "user_id": 1,
  "word_id": 42,
  "rating": 3,
  "session_id": 7,
  "time_ms": 2300
}
```

`session_id` and `time_ms` are optional.

**Response `200`:**
```json
{
  "word_id": 42,
  "state": 1,
  "due_at": 1713052800,
  "scheduled_days": 1.0,
  "reps": 1
}
```

---

## Sessions

### `POST /api/sessions`

Log a study session.

**Body:**
```json
{
  "user_id": 1,
  "language": "korean",
  "session_type": "pimsleur",
  "lesson_path": "pimsleur/unit-1/lesson-06",
  "notes": ""
}
```

**`session_type` values:** `pimsleur`, `flashcard`, `ai_lesson`, `tutor`, `free`

`lesson_path` and `notes` are optional.

**Response `200`:**
```json
{
  "id": 7,
  "jackpot": {
    "type": "xp_bonus",
    "label": "XP Surge",
    "desc":  "Next 5 reviews earn 3× XP",
    "xp":    500
  },
  "goal": {
    "user_id":      1,
    "daily_cards":  20,
    "today_reviews": 3
  }
}
```

`jackpot` is `null` if no jackpot was triggered this session.
`goal.today_reviews` is the number of flashcard reviews logged today (local date).

---

### `GET /api/sessions/<user_id>`

Returns the 100 most recent sessions for a user, newest first.

**Response `200`:**
```json
[
  {
    "id": 7,
    "user_id": 1,
    "timestamp": "2026-04-12T14:00:00+00:00",
    "language": "korean",
    "session_type": "pimsleur",
    "lesson_path": "pimsleur/unit-1/lesson-06",
    "notes": null
  }
]
```

---

## Progress & Rewards

### `GET /api/progress/<user_id>`

Returns streak data, heat map, and XP total for the progress view.

**Response `200`:**
```json
{
  "streak":      7,
  "best_streak": 14,
  "total_days":  42,
  "heatmap":     { "2026-04-12": 2, "2026-04-11": 1 },
  "xp_total":    12450
}
```

`heatmap` is a map of `YYYY-MM-DD → session count` for the past 365 days (local date).
`total_days` is lifetime distinct study days — never decreases even if streak resets.

---

### `GET /api/achievements/<user_id>`

Returns badge definitions and earned achievements.

**Response `200`:**
```json
{
  "earned":       [{ "key": "first_review", "earned_at": "2026-04-12T..." }],
  "badge_defs":   [{ "key": "first_review", "name": "First Step", "desc": "...", "icon": "👣", "group": "first_steps" }],
  "badge_groups": ["first_steps", "streaks", "chapters", "lifetime", "volume", "mastery", "exploration"],
  "group_labels": { "first_steps": "First Steps", "streaks": "Streaks", ... }
}
```

---

### `POST /api/achievements/check/<user_id>`

Check and award any newly earned badges. Call after each session or review event.

**Body:** `{}` (empty)

**Response `200`:**
```json
{ "awarded": [{ "key": "streak_7", "name": "Week Warrior", "icon": "🔥", ... }] }
```

`awarded` is empty `[]` if no new badges were earned (idempotent).

---

### `GET /api/goals/<user_id>`

Returns the user's daily goal settings plus today's review count.

**Response `200`:**
```json
{
  "user_id":        1,
  "daily_cards":    20,
  "today_reviews":  7,
  "show_leaderboard": 0
}
```

---

### `POST /api/goals/<user_id>`

Update goal settings.

**Body:**
```json
{ "daily_cards": 30 }
```

**Response `200`:** Updated goal object (same shape as GET).

---

### `GET /api/flashcards/due/<user_id>`

_(Updated)_ Now also returns `rarity` field on each card.

```json
{
  "word_id":  42,
  "word":     "안녕하세요",
  "rarity":   "fundamental",
  ...
}
```

**Rarity values:** `fundamental` (gold), `essential` (purple), `interesting` (green), `niche` (white/gray)

---

### `POST /api/flashcards/review`

_(Updated)_ Response now includes `just_mastered` and `rarity`.

```json
{
  "word_id":      42,
  "state":        2,
  "due_at":       1713052800,
  "scheduled_days": 21.0,
  "reps":         4,
  "just_mastered": true,
  "rarity":       "essential"
}
```

`just_mastered = true` when the card first crosses the mastery threshold:
`state == 2 AND stability >= 21 days AND reps >= 3`.

---

## Admin / Library

### `GET /api/admin/library`

Returns lesson counts per language and vocab counts per user.

**Response `200`:**
```json
{
  "lessons": {
    "korean": 18
  },
  "vocab": {
    "1": { "name": "Robie", "language": "korean", "count": 1897 },
    "2": { "name": "Anna",  "language": "spanish", "count": 0 }
  }
}
```

---

### `POST /api/admin/import-apkg`

Import an Anki `.apkg` deck. Accepts `multipart/form-data`.

**Form fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | yes | `.apkg` file |
| `user_id` | text | yes | Target user ID |
| `language` | text | yes | Language code |
| `deck_name` | text | no | Deck name (defaults to filename stem) |

**Response `200`:**
```json
{
  "imported": 500,
  "skipped": 3,
  "deck": "TTMIK First 500 Korean Words"
}
```

**Response `400`:** Missing `user_id` or `file`.
**Response `500`:** Import error (invalid `.apkg`, DB error, etc.)

---

### `POST /api/admin/ingest-vtt`

Ingest Pimsleur VTT + MP3 lesson files. Accepts `multipart/form-data`.
Extracts word audio clips via ffmpeg if available.

**Form fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `files` | file(s) | yes | VTT files (required) and matching MP3 files (optional) |
| `language` | text | yes | Language code |
| `user_id` | text | yes | Target user ID |
| `unit_name` | text | no | Unit name, e.g. `unit-1` (default: `unit-1`) |

VTT and MP3 files are paired by stem: `lesson-01.vtt` + `lesson-01.mp3`.
Lesson path stored as `pimsleur/<unit_name>/<stem>`.

**Response `200`:**
```json
{
  "lessons": 18,
  "words": 4800,
  "clips": 1813,
  "ffmpeg": true
}
```

`ffmpeg: false` means ffmpeg was not found — VTTs were ingested but no word audio clips were extracted.

**Response `400`:** No VTT files provided.
**Response `500`:** Ingest error.

---

### `POST /api/admin/backfill-rarity/<language>`

Re-assign rarity to all existing words for a language using the current frequency data file.
Run once after deploying frequency_data/<language>.json to an existing DB.

**Body:** `{}` (empty)

**Response `200`:**
```json
{ "updated": 1813 }
```

---

## Static files

### `GET /`

Serves `frontend/index.html` (SPA entry point).

### `GET /css/<file>`, `GET /js/<file>`

Serves static frontend assets from `frontend/`.

### `GET /audio/<path>`

Serves audio files from `DATA_DIR/languages/<path>`. Supports HTTP range
requests for audio seeking.

**Response `404`:** File not found.

---

## Error format

All error responses use the same envelope:
```json
{ "error": "Human-readable message" }
```

---

## Security headers

All responses include:

| Header | Value |
|--------|-------|
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `SAMEORIGIN` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
