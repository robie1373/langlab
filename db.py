"""
LangLab database layer.
SQLite via the stdlib sqlite3 module — no external dependencies.
"""

import json
import sqlite3
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import fsrs
from achievements import BADGE_BY_KEY, XP_REVIEW, XP_MASTERED_BASE, XP_MASTERED_RARITY, XP_SESSION, XP_STREAK_BONUS


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

-- ── PandR tables ───────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS achievements (
    id         INTEGER PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    badge_key  TEXT    NOT NULL,
    earned_at  TEXT    NOT NULL,
    UNIQUE(user_id, badge_key)
);

CREATE TABLE IF NOT EXISTS xp_events (
    id        INTEGER PRIMARY KEY,
    user_id   INTEGER NOT NULL REFERENCES users(id),
    points    INTEGER NOT NULL,
    source    TEXT    NOT NULL,  -- 'flashcard_review','card_mastered','session','daily_goal','streak_bonus'
    meta      TEXT,              -- JSON: e.g. {"rating":3} or {"rarity":"legendary","word":"안녕"}
    timestamp TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS streak_chapters (
    id         INTEGER PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    start_date TEXT    NOT NULL,
    end_date   TEXT    NOT NULL,
    length     INTEGER NOT NULL,
    was_best   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS user_goals (
    user_id         INTEGER PRIMARY KEY REFERENCES users(id),
    daily_cards     INTEGER NOT NULL DEFAULT 20,
    show_leaderboard INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS jackpot_state (
    user_id               INTEGER PRIMARY KEY REFERENCES users(id),
    sessions_since_jackpot INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS cefr_designations (
    id         INTEGER PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    language   TEXT    NOT NULL,
    level      TEXT    NOT NULL,
    score      INTEGER,
    earned_at  TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_user_vocab_user   ON user_vocab(user_id);
CREATE INDEX IF NOT EXISTS idx_user_vocab_due    ON user_vocab(user_id, due_at);
CREATE INDEX IF NOT EXISTS idx_reviews_user      ON reviews(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user     ON sessions(user_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_lessons_lang      ON lessons(language);
CREATE INDEX IF NOT EXISTS idx_achievements_user ON achievements(user_id);
CREATE INDEX IF NOT EXISTS idx_xp_user           ON xp_events(user_id, timestamp);
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
        self._migrate()
        self._seed()

    def _migrate(self):
        """Idempotent schema migrations for columns that can't use IF NOT EXISTS."""
        existing = {r[1] for r in self._conn.execute("PRAGMA table_info(words)").fetchall()}
        if 'rarity' not in existing:
            self._conn.execute("ALTER TABLE words ADD COLUMN rarity TEXT DEFAULT 'niche'")
        if 'frequency_rank' not in existing:
            self._conn.execute("ALTER TABLE words ADD COLUMN frequency_rank INTEGER")
        self._conn.commit()

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
               ORDER BY CASE WHEN uv.due_at IS NULL THEN 1 ELSE 0 END,
                        CASE WHEN uv.due_at IS NULL THEN RANDOM() ELSE uv.due_at END
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
        prev_state       = card.state
        prev_stability   = card.stability
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

        # XP for this review
        xp = XP_REVIEW.get(rating, 100)
        self.log_xp(user_id, xp, 'flashcard_review', {'rating': rating})

        # Bonus XP if this review pushed the card to "mastered" state
        just_mastered = (
            updated.state == 2 and updated.stability >= 21 and updated.reps >= 3
            and not (prev_state == 2 and prev_stability >= 21)
        )
        if just_mastered:
            rarity_row = self._conn.execute(
                "SELECT rarity FROM words WHERE id=?", (word_id,)
            ).fetchone()
            rarity = rarity_row['rarity'] if rarity_row else 'niche'
            bonus  = XP_MASTERED_RARITY.get(rarity, XP_MASTERED_BASE)
            self.log_xp(user_id, XP_MASTERED_BASE + bonus, 'card_mastered',
                        {'rarity': rarity, 'word_id': word_id})

        result = {
            'word_id':        word_id,
            'state':          updated.state,
            'due_at':         updated.due_at,
            'scheduled_days': updated.scheduled_days,
            'reps':           updated.reps,
        }
        if just_mastered:
            result['just_mastered'] = True
            result['rarity']        = rarity
        return result

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
        session_id = cur.lastrowid

        # XP for completing a session
        session_type = body['session_type']
        xp = XP_SESSION.get(session_type, 100)
        self.log_xp(int(body['user_id']), xp, 'session', {'session_type': session_type})

        return session_id

    def get_library_stats(self) -> dict:
        rows = self._conn.execute(
            "SELECT language, COUNT(*) as n FROM lessons GROUP BY language"
        ).fetchall()
        lessons = {r['language']: r['n'] for r in rows}
        vocab = {}
        for user in self.get_users():
            n = self._conn.execute(
                "SELECT COUNT(*) as n FROM user_vocab WHERE user_id=?",
                (user['id'],)
            ).fetchone()['n']
            vocab[str(user['id'])] = {
                'name': user['display_name'],
                'language': user['default_lang'],
                'count': n,
            }
        return {'lessons': lessons, 'vocab': vocab}

    def get_sessions(self, user_id: int, limit: int = 100) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM sessions WHERE user_id=? ORDER BY timestamp DESC LIMIT ?",
            (user_id, limit)
        ).fetchall()
        return [_row_to_dict(r) for r in rows]

    # ── PandR: progress ──────────────────────────────────────────────────────

    def get_progress(self, user_id: int) -> dict:
        """Streak, total days, heat map for the progress view."""
        rows = self._conn.execute(
            """SELECT DISTINCT date(timestamp) as day
               FROM sessions WHERE user_id=?
               ORDER BY day DESC""",
            (user_id,)
        ).fetchall()

        day_strs  = [r['day'] for r in rows]
        total_days = len(day_strs)

        if not day_strs:
            heatmap = {}
            streak = best_streak = 0
        else:
            today     = date.today()
            day_dates = [date.fromisoformat(d) for d in day_strs]
            day_set   = set(day_dates)

            # Current streak — counts back from today or yesterday
            streak  = 0
            check   = today
            if check not in day_set:
                check = today - timedelta(days=1)
            while check in day_set:
                streak += 1
                check  -= timedelta(days=1)

            # Best streak — full scan
            best_streak = run = 0
            prev = None
            for d in sorted(day_dates):
                if prev is None or (d - prev).days == 1:
                    run += 1
                else:
                    best_streak = max(best_streak, run)
                    run = 1
                prev = d
            best_streak = max(best_streak, run)

            # Heat map: last 365 days — {YYYY-MM-DD: session_count}
            hm_rows = self._conn.execute(
                """SELECT date(timestamp) as day, COUNT(*) as n
                   FROM sessions
                   WHERE user_id=? AND date(timestamp) >= date('now', '-365 days')
                   GROUP BY day""",
                (user_id,)
            ).fetchall()
            heatmap = {r['day']: r['n'] for r in hm_rows}

        # XP total
        xp_row = self._conn.execute(
            "SELECT COALESCE(SUM(points),0) as total FROM xp_events WHERE user_id=?",
            (user_id,)
        ).fetchone()

        return {
            'streak':      streak,
            'best_streak': best_streak,
            'total_days':  total_days,
            'heatmap':     heatmap,
            'xp_total':    xp_row['total'],
        }

    # ── PandR: XP ────────────────────────────────────────────────────────────

    def log_xp(self, user_id: int, points: int, source: str, meta: dict = None) -> None:
        self._conn.execute(
            "INSERT INTO xp_events (user_id, points, source, meta, timestamp) VALUES (?,?,?,?,?)",
            (user_id, points, source, json.dumps(meta) if meta else None, _now_iso())
        )
        self._conn.commit()

    # ── PandR: achievements ──────────────────────────────────────────────────

    def get_achievements(self, user_id: int) -> list[dict]:
        rows = self._conn.execute(
            "SELECT badge_key, earned_at FROM achievements WHERE user_id=? ORDER BY earned_at",
            (user_id,)
        ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def _award(self, user_id: int, key: str) -> bool:
        """Insert an achievement row; return True if newly awarded."""
        try:
            self._conn.execute(
                "INSERT INTO achievements (user_id, badge_key, earned_at) VALUES (?,?,?)",
                (user_id, key, _now_iso())
            )
            self._conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False  # already earned

    def check_and_award(self, user_id: int) -> list[dict]:
        """
        Check all achievement conditions and award any newly earned badges.
        Returns list of badge dicts for badges awarded this call (for real-time toasts).
        """
        newly_earned = []

        def award(key: str):
            if self._award(user_id, key) and key in BADGE_BY_KEY:
                newly_earned.append(BADGE_BY_KEY[key])

        # ── gather stats ────────────────────────────────────────────────────
        progress = self.get_progress(user_id)
        streak      = progress['streak']
        best_streak = progress['best_streak']
        total_days  = progress['total_days']

        review_count = self._conn.execute(
            "SELECT COUNT(*) as n FROM reviews WHERE user_id=?", (user_id,)
        ).fetchone()['n']

        mastered_count = self._conn.execute(
            """SELECT COUNT(*) as n FROM user_vocab
               WHERE user_id=? AND state=2 AND stability>=21 AND reps>=3""",
            (user_id,)
        ).fetchone()['n']

        session_types_this_week = {
            r['session_type'] for r in self._conn.execute(
                """SELECT DISTINCT session_type FROM sessions
                   WHERE user_id=? AND date(timestamp) >= date('now', '-7 days')""",
                (user_id,)
            ).fetchall()
        }

        first_session = self._conn.execute(
            "SELECT session_type FROM sessions WHERE user_id=? ORDER BY timestamp LIMIT 1",
            (user_id,)
        ).fetchone()

        # Days since last session before the most recent one (for comeback)
        gap_row = self._conn.execute(
            """SELECT julianday(s1.timestamp) - julianday(s2.timestamp) as gap
               FROM sessions s1
               JOIN sessions s2 ON s2.id = (
                   SELECT id FROM sessions
                   WHERE user_id=? AND id < s1.id
                   ORDER BY id DESC LIMIT 1
               )
               WHERE s1.user_id=?
               ORDER BY s1.timestamp DESC LIMIT 1""",
            (user_id, user_id)
        ).fetchone()
        gap_days = gap_row['gap'] if gap_row else 0

        # ── first steps ────────────────────────────────────────────────────
        if review_count >= 1:
            award('first_review')

        if first_session:
            st = first_session['session_type']
            if st in ('pimsleur', 'ai_lesson', 'free'):
                award('first_lesson')
            elif st == 'tutor':
                award('first_tutor')
            elif st == 'ai_lesson':
                award('first_ai')

        # Check each session type independently
        for row in self._conn.execute(
            "SELECT DISTINCT session_type FROM sessions WHERE user_id=?", (user_id,)
        ).fetchall():
            st = row['session_type']
            if st in ('pimsleur', 'free'):
                award('first_lesson')
            elif st == 'tutor':
                award('first_tutor')
            elif st == 'ai_lesson':
                award('first_ai')

        if review_count >= 1:
            award('first_review')

        # ── streak milestones ──────────────────────────────────────────────
        for threshold, key in [(3,'streak_3'),(7,'streak_7'),(14,'streak_14'),
                               (30,'streak_30'),(60,'streak_60'),(100,'streak_100')]:
            if streak >= threshold:
                award(key)

        # ── new game+ / chapters ───────────────────────────────────────────
        chapter_count = self._conn.execute(
            "SELECT COUNT(*) as n FROM streak_chapters WHERE user_id=?", (user_id,)
        ).fetchone()['n']
        if chapter_count >= 1:
            award('new_chapter')

        # surpassed_best: current streak > all completed chapters
        if best_streak > 0 and streak > best_streak:
            award('surpassed_best')

        # comeback: returned after 7+ day gap
        if gap_days >= 7:
            award('comeback')

        # ── lifetime days ──────────────────────────────────────────────────
        for threshold, key in [(7,'days_7'),(30,'days_30'),(100,'days_100'),(365,'days_365')]:
            if total_days >= threshold:
                award(key)

        # ── review volume ──────────────────────────────────────────────────
        for threshold, key in [(10,'reviews_10'),(50,'reviews_50'),(100,'reviews_100'),
                               (500,'reviews_500'),(1000,'reviews_1000')]:
            if review_count >= threshold:
                award(key)

        # ── mastery ────────────────────────────────────────────────────────
        for threshold, key in [(10,'mastered_10'),(50,'mastered_50'),
                               (100,'mastered_100'),(500,'mastered_500')]:
            if mastered_count >= threshold:
                award(key)

        # ── multi-modal ────────────────────────────────────────────────────
        all_types = {'pimsleur', 'flashcard', 'ai_lesson', 'tutor', 'free'}
        if all_types.issubset(session_types_this_week):
            award('multimodal')

        # ── streak XP bonuses ──────────────────────────────────────────────
        for threshold, xp in XP_STREAK_BONUS.items():
            if streak == threshold:  # exactly on milestone day — award once
                if not self._conn.execute(
                    "SELECT 1 FROM xp_events WHERE user_id=? AND source=? AND meta LIKE ?",
                    (user_id, 'streak_bonus', f'%"streak":{threshold}%')
                ).fetchone():
                    self.log_xp(user_id, xp, 'streak_bonus', {'streak': threshold})

        return newly_earned

    def close_streak_chapter(self, user_id: int) -> None:
        """
        Called when a streak is broken (detected at session-log time).
        Records the completed streak chapter for the Streak Chronicle.
        """
        progress = self.get_progress(user_id)
        # The streak before today — look at yesterday's count
        rows = self._conn.execute(
            """SELECT DISTINCT date(timestamp) as day
               FROM sessions WHERE user_id=?
               ORDER BY day DESC""",
            (user_id,)
        ).fetchall()
        if len(rows) < 2:
            return

        day_dates = [date.fromisoformat(r['day']) for r in rows]
        # Find the most recent run that ended before today
        today = date.today()
        run_end = None
        run_len = 0
        prev = None
        for d in sorted(day_dates, reverse=True):
            if d >= today:
                continue
            if prev is None:
                run_end = d
                run_len = 1
            elif (prev - d).days == 1:
                run_len += 1
            else:
                break
            prev = d

        if run_len < 1 or run_end is None:
            return

        run_start = run_end - timedelta(days=run_len - 1)
        best_before = self._conn.execute(
            "SELECT COALESCE(MAX(length),0) as best FROM streak_chapters WHERE user_id=?",
            (user_id,)
        ).fetchone()['best']

        self._conn.execute(
            """INSERT OR IGNORE INTO streak_chapters
               (user_id, start_date, end_date, length, was_best)
               VALUES (?,?,?,?,?)""",
            (user_id, run_start.isoformat(), run_end.isoformat(),
             run_len, 1 if run_len > best_before else 0)
        )
        self._conn.commit()

    def get_streak_chapters(self, user_id: int) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM streak_chapters WHERE user_id=? ORDER BY start_date DESC",
            (user_id,)
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
