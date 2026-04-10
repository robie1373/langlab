"""
Unit tests for the database layer (db.py).

All tests use an in-memory SQLite database so they are
isolated, fast, and leave no files on disk.
"""

import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db import Database
from fsrs import NEW, LEARNING, REVIEW, AGAIN, GOOD, EASY


def make_db() -> Database:
    return Database(':memory:')


class TestSeed(unittest.TestCase):
    def test_default_users_created(self):
        db = make_db()
        users = db.get_users()
        names = {u['name'] for u in users}
        self.assertIn('robie', names)
        self.assertIn('anna', names)

    def test_user_default_langs(self):
        db = make_db()
        users = {u['name']: u for u in db.get_users()}
        self.assertEqual(users['robie']['default_lang'], 'korean')
        self.assertEqual(users['anna']['default_lang'],  'spanish')

    def test_seed_idempotent(self):
        db = make_db()
        # Second init on same connection should not error or duplicate
        db._seed()
        self.assertEqual(len(db.get_users()), 2)


class TestGetUser(unittest.TestCase):
    def test_get_existing_user(self):
        db = make_db()
        robie = db.get_users()[0]
        fetched = db.get_user(robie['id'])
        self.assertEqual(fetched['name'], robie['name'])

    def test_get_missing_user_returns_none(self):
        db = make_db()
        self.assertIsNone(db.get_user(9999))


class TestLessons(unittest.TestCase):
    ENTRIES = [
        {'start': 9.38, 'end': 9.78, 'lines': ['안녕하세요.'], 'korean': ['안녕하세요.']}
    ]

    def _insert(self, db):
        return db.upsert_lesson('korean', 'pimsleur/unit-1/lesson-01',
                                'Lesson 01', 'korean/.../lesson-01.mp3', self.ENTRIES)

    def test_upsert_and_list(self):
        db = make_db()
        self._insert(db)
        lessons = db.get_lesson_list('korean')
        self.assertEqual(len(lessons), 1)
        self.assertEqual(lessons[0]['title'], 'Lesson 01')

    def test_get_lesson_data_returns_entries(self):
        db = make_db()
        self._insert(db)
        data = db.get_lesson_data('korean', 'pimsleur/unit-1/lesson-01')
        self.assertIsNotNone(data)
        self.assertIsInstance(data['entries'], list)
        self.assertEqual(data['entries'][0]['korean'], ['안녕하세요.'])

    def test_get_missing_lesson_returns_none(self):
        db = make_db()
        self.assertIsNone(db.get_lesson_data('korean', 'no/such/lesson'))

    def test_upsert_is_idempotent(self):
        db = make_db()
        self._insert(db)
        self._insert(db)   # second upsert — should not raise or duplicate
        self.assertEqual(len(db.get_lesson_list('korean')), 1)

    def test_upsert_updates_entries(self):
        db = make_db()
        self._insert(db)
        new_entries = [{'start': 1.0, 'end': 2.0, 'lines': ['새'], 'korean': ['새']}]
        db.upsert_lesson('korean', 'pimsleur/unit-1/lesson-01',
                         'Lesson 01', None, new_entries)
        data = db.get_lesson_data('korean', 'pimsleur/unit-1/lesson-01')
        self.assertEqual(data['entries'][0]['korean'], ['새'])

    def test_empty_list_for_unknown_language(self):
        db = make_db()
        self.assertEqual(db.get_lesson_list('klingon'), [])


class TestWords(unittest.TestCase):
    def test_upsert_word_returns_id(self):
        db = make_db()
        wid = db.upsert_word('korean', '안녕', 'hello', 'pimsleur', None, None)
        self.assertIsInstance(wid, int)
        self.assertGreater(wid, 0)

    def test_upsert_word_idempotent(self):
        db = make_db()
        id1 = db.upsert_word('korean', '안녕', 'hello', 'pimsleur', None, None)
        id2 = db.upsert_word('korean', '안녕', 'hello', 'pimsleur', None, None)
        self.assertEqual(id1, id2)

    def test_same_word_different_language(self):
        db = make_db()
        id1 = db.upsert_word('korean',  '안녕', 'hello', 'pimsleur', None, None)
        id2 = db.upsert_word('spanish', '안녕', 'hello', 'manual',   None, None)
        self.assertNotEqual(id1, id2)

    def test_translation_not_overwritten_by_none(self):
        db = make_db()
        db.upsert_word('korean', '안녕', 'hello', 'pimsleur', None, None)
        db.upsert_word('korean', '안녕', None,    'pimsleur', None, None)
        vocab = db.get_user_vocab(db.get_users()[0]['id'])
        # word table still has translation (not overwritten) — verify via raw query
        row = db._conn.execute(
            "SELECT translation FROM words WHERE word='안녕' AND language='korean'"
        ).fetchone()
        self.assertEqual(row['translation'], 'hello')


class TestUserVocab(unittest.TestCase):
    def setUp(self):
        self.db = make_db()
        self.user_id = self.db.get_users()[0]['id']  # robie
        self.word_id = self.db.upsert_word('korean', '감사합니다', 'thank you',
                                           'pimsleur', None, None)

    def test_ensure_user_vocab_creates_entry(self):
        self.db.ensure_user_vocab(self.user_id, self.word_id)
        vocab = self.db.get_user_vocab(self.user_id)
        words = [v['word'] for v in vocab]
        self.assertIn('감사합니다', words)

    def test_ensure_user_vocab_idempotent(self):
        self.db.ensure_user_vocab(self.user_id, self.word_id)
        self.db.ensure_user_vocab(self.user_id, self.word_id)
        vocab = self.db.get_user_vocab(self.user_id)
        matches = [v for v in vocab if v['word'] == '감사합니다']
        self.assertEqual(len(matches), 1)

    def test_vocab_isolated_per_user(self):
        anna_id = next(u['id'] for u in self.db.get_users() if u['name'] == 'anna')
        self.db.ensure_user_vocab(self.user_id, self.word_id)
        # anna has no vocab yet
        self.assertEqual(self.db.get_user_vocab(anna_id), [])


class TestRateWord(unittest.TestCase):
    def setUp(self):
        self.db = make_db()
        self.user_id = self.db.get_users()[0]['id']
        self.word_id = self.db.upsert_word('korean', '네', 'yes', 'pimsleur', None, None)

    def test_rate_by_word_id(self):
        result = self.db.rate_word({
            'user_id': self.user_id,
            'word_id': self.word_id,
            'rating':  GOOD,
        })
        self.assertEqual(result['word_id'], self.word_id)
        self.assertIn('state', result)

    def test_rate_by_word_string_creates_entry(self):
        result = self.db.rate_word({
            'user_id':  self.user_id,
            'word':     '아니요',
            'language': 'korean',
            'rating':   GOOD,
        })
        self.assertIn('word_id', result)
        # verify word was created
        row = self.db._conn.execute(
            "SELECT id FROM words WHERE word='아니요' AND language='korean'"
        ).fetchone()
        self.assertIsNotNone(row)

    def test_state_changes_after_good_then_easy(self):
        # Good from New → Learning
        r1 = self.db.rate_word({'user_id': self.user_id, 'word_id': self.word_id, 'rating': GOOD})
        self.assertEqual(r1['state'], LEARNING)

    def test_again_from_new_stays_learning(self):
        r = self.db.rate_word({'user_id': self.user_id, 'word_id': self.word_id, 'rating': AGAIN})
        self.assertEqual(r['state'], LEARNING)

    def test_easy_from_new_goes_review(self):
        r = self.db.rate_word({'user_id': self.user_id, 'word_id': self.word_id, 'rating': EASY})
        self.assertEqual(r['state'], REVIEW)

    def test_review_logged(self):
        self.db.rate_word({'user_id': self.user_id, 'word_id': self.word_id, 'rating': GOOD})
        count = self.db._conn.execute(
            "SELECT COUNT(*) FROM reviews WHERE user_id=? AND word_id=?",
            (self.user_id, self.word_id)
        ).fetchone()[0]
        self.assertEqual(count, 1)


class TestDecks(unittest.TestCase):
    def setUp(self):
        self.db = make_db()
        self.user_id = self.db.get_users()[0]['id']

    def test_ensure_deck_creates(self):
        did = self.db.ensure_deck(self.user_id, 'Lesson 1', 'lesson')
        self.assertIsInstance(did, int)

    def test_ensure_deck_idempotent(self):
        id1 = self.db.ensure_deck(self.user_id, 'Lesson 1', 'lesson')
        id2 = self.db.ensure_deck(self.user_id, 'Lesson 1', 'lesson')
        self.assertEqual(id1, id2)

    def test_add_word_to_deck(self):
        did = self.db.ensure_deck(self.user_id, 'Test Deck', 'manual')
        wid = self.db.upsert_word('korean', '하나', 'one', 'manual', None, None)
        self.db.add_word_to_deck(did, wid)
        count = self.db._conn.execute(
            "SELECT COUNT(*) FROM deck_words WHERE deck_id=? AND word_id=?", (did, wid)
        ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_add_word_to_deck_idempotent(self):
        did = self.db.ensure_deck(self.user_id, 'Test Deck', 'manual')
        wid = self.db.upsert_word('korean', '둘', 'two', 'manual', None, None)
        self.db.add_word_to_deck(did, wid)
        self.db.add_word_to_deck(did, wid)
        count = self.db._conn.execute(
            "SELECT COUNT(*) FROM deck_words WHERE deck_id=? AND word_id=?", (did, wid)
        ).fetchone()[0]
        self.assertEqual(count, 1)


class TestSessions(unittest.TestCase):
    def setUp(self):
        self.db = make_db()
        self.user_id = self.db.get_users()[0]['id']

    def test_log_session_returns_id(self):
        sid = self.db.log_session({
            'user_id':      self.user_id,
            'language':     'korean',
            'session_type': 'pimsleur',
            'lesson_path':  'pimsleur/unit-1/lesson-06',
        })
        self.assertIsInstance(sid, int)
        self.assertGreater(sid, 0)

    def test_get_sessions(self):
        self.db.log_session({'user_id': self.user_id, 'language': 'korean', 'session_type': 'pimsleur'})
        self.db.log_session({'user_id': self.user_id, 'language': 'korean', 'session_type': 'flashcard'})
        sessions = self.db.get_sessions(self.user_id)
        self.assertEqual(len(sessions), 2)

    def test_sessions_isolated_per_user(self):
        anna_id = next(u['id'] for u in self.db.get_users() if u['name'] == 'anna')
        self.db.log_session({'user_id': self.user_id, 'language': 'korean', 'session_type': 'pimsleur'})
        self.assertEqual(self.db.get_sessions(anna_id), [])


class TestFlashcardReview(unittest.TestCase):
    def setUp(self):
        self.db = make_db()
        self.user_id = self.db.get_users()[0]['id']
        self.word_id = self.db.upsert_word('korean', '물', 'water', 'pimsleur', None, None)
        self.db.ensure_user_vocab(self.user_id, self.word_id)

    def test_review_card_returns_state(self):
        result = self.db.review_card({
            'user_id': self.user_id,
            'word_id': self.word_id,
            'rating':  GOOD,
        })
        self.assertIn('state', result)
        self.assertIn('due_at', result)

    def test_due_cards_empty_when_future_due(self):
        # After a Good review, due_at is in the future — card should not appear
        self.db.review_card({'user_id': self.user_id, 'word_id': self.word_id, 'rating': GOOD})
        due = self.db.get_due_cards(self.user_id)
        # Card should NOT be due immediately after a review
        self.assertEqual(len(due), 0)

    def test_new_card_is_due(self):
        # A newly added vocab entry with no due_at is treated as due
        due = self.db.get_due_cards(self.user_id)
        self.assertEqual(len(due), 1)
        self.assertEqual(due[0]['word_id'], self.word_id)

    def test_review_logged_with_session(self):
        sid = self.db.log_session({'user_id': self.user_id, 'language': 'korean', 'session_type': 'flashcard'})
        self.db.review_card({'user_id': self.user_id, 'word_id': self.word_id,
                             'rating': EASY, 'session_id': sid})
        row = self.db._conn.execute(
            "SELECT session_id FROM reviews WHERE user_id=? AND word_id=?",
            (self.user_id, self.word_id)
        ).fetchone()
        self.assertEqual(row['session_id'], sid)

    def test_multi_card_review_cycle(self):
        """Simulate a short review session: new → learning → review."""
        # Add a second word
        w2 = self.db.upsert_word('korean', '불', 'fire', 'pimsleur', None, None)
        self.db.ensure_user_vocab(self.user_id, w2)

        # Rate both
        r1 = self.db.review_card({'user_id': self.user_id, 'word_id': self.word_id, 'rating': EASY})
        r2 = self.db.review_card({'user_id': self.user_id, 'word_id': w2, 'rating': AGAIN})

        self.assertEqual(r1['state'], REVIEW)
        self.assertEqual(r2['state'], LEARNING)


if __name__ == '__main__':
    unittest.main()
