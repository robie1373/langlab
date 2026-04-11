"""
LangLab database layer.
SQLite via the stdlib sqlite3 module — no external dependencies.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import fsrs


SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id           INTEGER PRIMARY KEY,
    name         TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    default_lang TEXT NOT NULL DEFAULT 'korean'
);

CREATE TABLE IF NOT EXISTS words (
    id            INTEGER PRIMARY KEY,
    language      TEXT NOT NULL,
    word          TEXT NOT NULL,
    translation   TEXT,
    source        TEXT,           -- 'pimsleur', 'imported', 'manual'
    source_lesson TEXT,
    audio_path    TEXT,           -- relative path under data/languages/
    UNIQUE(language, word)
);

CREATE TABLE IF NOT EXISTS user_vocab (
    user_id        INTEGER NOT NULL REFERENCES users(id),
    word_id        INTEGER NOT NULL REFERENCES words(id),
    stability      REAL    DEFAULT 0.0,
    difficulty     REAL    DEFAULT 0.0,
    elapsed_days   REAL    DEFAULT 0.0,
    scheduled_days REAL    DEFAULT 0.0,
    reps           INTEGER DEFAULT 0,
    lapses         INTEGER DEFAULT 0,
    state          INTEGER DEFAULT 0,  -- 0:New 1:Learning 2:Review 3:Relearning
    due_at         INTEGER,            -- unix timestamp
    last_review    REAL    DEFAULT 0.0,
    first_seen     TEXT    NOT NULL,
    PRIMARY KEY(user_id, word_id)
);

CREATE TABLE IF NOT EXISTS decks (
    id       INTEGER PRIMARY KEY,
    user_id  INTEGER NOT NULL REFERENCES users(id),
    name     TEXT NOT NULL,
    source   TEXT NOT NULL    -- 'lesson', 'imported', 'manual'
);

CREATE TABLE IF NOT EXISTS deck_words (
    deck_id  INTEGER NOT NULL REFERENCES decks(id),
    word_id  INTEGER NOT NULL REFERENCES words(id),
    PRIMARY KEY(deck_id, word_id)
);

CREATE TABLE IF NOT EXISTS sessions (
    id           INTEGER PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES users(id),
    timestamp    TEXT NOT NULL,
    language     TEXT NOT NULL,
    session_type TEXT NOT NULL,  -- 'pimsleur', 'flashcard', 'ai_lesson', 'tutor', 'free'
    lesson_path  TEXT,
    notes        TEXT
);

CREATE TABLE IF NOT EXISTS reviews (
    id               INTEGER PRIMARY KEY,
    session_id       INTEGER REFERENCES sessions(id),
    user_id          INTEGER NOT NULL REFERENCES users(id),
    word_id          INTEGER NOT NULL REFERENCES words(id),
    timestamp        TEXT NOT NULL,
    rating           INTEGER NOT NULL,  -- 1:Again 2:Hard 3:Good 4:Easy
    stability_before REAL,
    stability_after  REAL,
    scheduled_days   REAL,
    time_ms          INTEGER
);

-- lesson metadata stored as JSON blobs; allows arbitrary lesson structures
-- without schema churn as we add AI lessons, Spanish content, etc.
CREATE TABLE IF NOT EXISTS lessons (
    id           INTEGER PRIMARY KEY,
    language     TEXT NOT NULL,
    lesson_path  TEXT NOT NULL,   -- e.g. 'pimsleur/unit-1/lesson-01'
    title        TEXT NOT NULL,
    mp3_path     TEXT,            -- relative path under data/languages/
    entries_json TEXT NOT NULL,   -- JSON array of entry objects
    UNIQUE(language, lesson_path)
);

CREATE INDEX IF NOT EXISTS idx_user_vocab_user   ON user_vocab(user_id);
CREATE INDEX IF NOT EXISTS idx_user_vocab_due    ON user_vocab(user_id, due_at);
CREATE INDEX IF NOT EXISTS idx_reviews_user      ON reviews(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user     ON sessions(user_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_lessons_lang      ON lessons(language);
"""

SEED_USERS = [
    ('robie',  'Robie',  'korean'),
    ('anna',   'Anna',   'spanish'),
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row) -> dict:
    return dict(row)


class Database:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._seed()

    def _seed(self):
        for name, display, lang in SEED_USERS:
            self._conn.execute(
                "INSERT OR IGNORE INTO users (name, display_name, default_lang) VALUES (?,?,?)",
                (name, display, lang)
            )
        self._conn.commit()

    # ── users ──────────────────────────────────────────────────────────────

    def get_users(self) -> list[dict]:
        rows = self._conn.execute("SELECT * FROM users ORDER BY id").fetchall()
        return [_row_to_dict(r) for r in rows]

    def get_user(self, user_id: int) -> Optional[dict]:
        row = self._conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return _row_to_dict(row) if row else None

    # ── lessons ────────────────────────────────────────────────────────────

    def get_lesson_list(self, language: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT id, language, lesson_path, title, mp3_path FROM lessons WHERE language=? ORDER BY lesson_path",
            (language,)
        ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def get_lesson_data(self, language: str, lesson_path: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM lessons WHERE language=? AND lesson_path=?",
            (language, lesson_path)
        ).fetchone()
        if not row:
            return None
        d = _row_to_dict(row)
        d['entries'] = json.loads(d.pop('entries_json'))
        return d

    def upsert_lesson(self, language: str, lesson_path: str, title: str,
                      mp3_path: Optional[str], entries: list) -> int:
        entries_json = json.dumps(entries, ensure_ascii=False)
        cur = self._conn.execute(
            """INSERT INTO lessons (language, lesson_path, title, mp3_path, entries_json)
               VALUES (?,?,?,?,?)
               ON CONFLICT(language, lesson_path) DO UPDATE SET
                 title=excluded.title, mp3_path=excluded.mp3_path,
                 entries_json=excluded.entries_json""",
            (language, lesson_path, title, mp3_path, entries_json)
        )
        self._conn.commit()
        return cur.lastrowid

    # ── words & vocab ───────────────────────────────────────────────────────

    def upsert_word(self, language: str, word: str, translation: Optional[str],
                    source: str, source_lesson: Optional[str],
                    audio_path: Optional[str]) -> int:
        self._conn.execute(
            """INSERT INTO words (language, word, translation, source, source_lesson, audio_path)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(language, word) DO UPDATE SET
                 translation=COALESCE(excluded.translation, translation),
                 audio_path=COALESCE(excluded.audio_path, audio_path)""",
            (language, word, translation, source, source_lesson, audio_path)
        )
        self._conn.commit()
        return self._conn.execute(
            "SELECT id FROM words WHERE language=? AND word=?", (language, word)
        ).fetchone()['id']

    def ensure_user_vocab(self, user_id: int, word_id: int):
        self._conn.execute(
            "INSERT OR IGNORE INTO user_vocab (user_id, word_id, first_seen) VALUES (?,?,?)",
            (user_id, word_id, _now_iso())
        )
        self._conn.commit()

    def get_user_vocab(self, user_id: int) -> list[dict]:
        rows = self._conn.execute(
            """SELECT w.*, uv.state, uv.stability, uv.due_at, uv.reps, uv.lapses
               FROM user_vocab uv JOIN words w ON w.id = uv.word_id
               WHERE uv.user_id=? ORDER BY w.language, w.word""",
            (user_id,)
        ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def rate_word(self, body: dict) -> dict:
        """Apply a comprehension rating from the player word-click card.

        Accepts either word_id (known word) or word+language (on-the-fly
        creation for words in transcripts not yet formally ingested).
        """
        user_id = int(body['user_id'])
        rating  = int(body['rating'])   # 1-4
        time_ms = body.get('time_ms')

        if 'word_id' in body:
            word_id = int(body['word_id'])
        else:
            # Auto-create the word entry from the raw transcript token
            word_id = self.upsert_word(
                language      = body['language'],
                word          = body['word'],
                translation   = body.get('translation'),
                source        = 'transcript',
                source_lesson = body.get('source_lesson'),
                audio_path    = None,
            )

        self.ensure_user_vocab(user_id, word_id)

        row = self._conn.execute(
            "SELECT * FROM user_vocab WHERE user_id=? AND word_id=?",
            (user_id, word_id)
        ).fetchone()

        card = fsrs.Card.from_row(_row_to_dict(row))
        stability_before = card.stability
        updated, _ = fsrs.review(card, rating)

        self._conn.execute(
            """UPDATE user_vocab SET
               stability=?, difficulty=?, elapsed_days=?, scheduled_days=?,
               reps=?, lapses=?, state=?, due_at=?, last_review=?
               WHERE user_id=? AND word_id=?""",
            (updated.stability, updated.difficulty, updated.elapsed_days,
             updated.scheduled_days, updated.reps, updated.lapses,
             updated.state, updated.due_at, updated.last_review,
             user_id, word_id)
        )

        # Log the review (not tied to a flashcard session — player inline review)
        self._conn.execute(
            """INSERT INTO reviews
               (user_id, word_id, timestamp, rating, stability_before, stability_after, scheduled_days, time_ms)
               VALUES (?,?,?,?,?,?,?,?)""",
            (user_id, word_id, _now_iso(), rating, stability_before,
             updated.stability, updated.scheduled_days, time_ms)
        )
        self._conn.commit()

        return {
            'word_id': word_id,
            'state':   updated.state,
            'due_at':  updated.due_at,
            'reps':    updated.reps,
        }

    # ── decks ──────────────────────────────────────────────────────────────

    def ensure_deck(self, user_id: int, name: str, source: str) -> int:
        row = self._conn.execute(
            "SELECT id FROM decks WHERE user_id=? AND name=?", (user_id, name)
        ).fetchone()
        if row:
            return row['id']
        cur = self._conn.execute(
            "INSERT INTO decks (user_id, name, source) VALUES (?,?,?)",
            (user_id, name, source)
        )
        self._conn.commit()
        return cur.lastrowid

    def add_word_to_deck(self, deck_id: int, word_id: int):
        self._conn.execute(
            "INSERT OR IGNORE INTO deck_words (deck_id, word_id) VALUES (?,?)",
            (deck_id, word_id)
        )
        self._conn.commit()

    # ── flashcard reviews ──────────────────────────────────────────────────

    def get_due_cards(self, user_id: int, limit: int = 50) -> list[dict]:
        now = int(datetime.now(timezone.utc).timestamp())
        rows = self._conn.execute(
            """SELECT w.id as word_id, w.word, w.translation, w.audio_path,
                      uv.state, uv.stability, uv.difficulty, uv.reps, uv.lapses,
                      uv.elapsed_days, uv.scheduled_days, uv.due_at, uv.last_review
               FROM user_vocab uv JOIN words w ON w.id = uv.word_id
               WHERE uv.user_id=? AND (uv.due_at IS NULL OR uv.due_at <= ?)
               ORDER BY uv.due_at ASC NULLS FIRST
               LIMIT ?""",
            (user_id, now, limit)
        ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def review_card(self, body: dict) -> dict:
        """Process a flashcard review (dedicated flashcard mode)."""
        user_id    = int(body['user_id'])
        word_id    = int(body['word_id'])
        rating     = int(body['rating'])
        session_id = body.get('session_id')
        time_ms    = body.get('time_ms')

        self.ensure_user_vocab(user_id, word_id)

        row = self._conn.execute(
            "SELECT * FROM user_vocab WHERE user_id=? AND word_id=?",
            (user_id, word_id)
        ).fetchone()

        card = fsrs.Card.from_row(_row_to_dict(row))
        stability_before = card.stability
        updated, scheduled_secs = fsrs.review(card, rating)

        self._conn.execute(
            """UPDATE user_vocab SET
               stability=?, difficulty=?, elapsed_days=?, scheduled_days=?,
               reps=?, lapses=?, state=?, due_at=?, last_review=?
               WHERE user_id=? AND word_id=?""",
            (updated.stability, updated.difficulty, updated.elapsed_days,
             updated.scheduled_days, updated.reps, updated.lapses,
             updated.state, updated.due_at, updated.last_review,
             user_id, word_id)
        )

        self._conn.execute(
            """INSERT INTO reviews
               (session_id, user_id, word_id, timestamp, rating,
                stability_before, stability_after, scheduled_days, time_ms)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (session_id, user_id, word_id, _now_iso(), rating,
             stability_before, updated.stability, updated.scheduled_days, time_ms)
        )
        self._conn.commit()

        return {
            'word_id':        word_id,
            'state':          updated.state,
            'due_at':         updated.due_at,
            'scheduled_days': updated.scheduled_days,
            'reps':           updated.reps,
        }

    # ── sessions ────────────────────────────────────────────────────────────

    def log_session(self, body: dict) -> int:
        cur = self._conn.execute(
            """INSERT INTO sessions (user_id, timestamp, language, session_type, lesson_path, notes)
               VALUES (?,?,?,?,?,?)""",
            (
                int(body['user_id']),
                body.get('timestamp', _now_iso()),
                body['language'],
                body['session_type'],
                body.get('lesson_path'),
                body.get('notes'),
            )
        )
        self._conn.commit()
        return cur.lastrowid

    def get_sessions(self, user_id: int, limit: int = 100) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM sessions WHERE user_id=? ORDER BY timestamp DESC LIMIT ?",
            (user_id, limit)
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
