"""
Unit tests for the database layer (db.py).

All tests use an in-memory SQLite database so they are
isolated, fast, and leave no files on disk.
"""

import sys, unittest, json
from pathlib import Path
from datetime import date
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


class TestLibraryStats(unittest.TestCase):
    def test_empty_db_has_no_lessons(self):
        db = make_db()
        stats = db.get_library_stats()
        self.assertEqual(stats['lessons'], {})

    def test_lesson_counted_by_language(self):
        db = make_db()
        db.upsert_lesson('korean', 'pimsleur/unit-1/lesson-01', 'Lesson 01', None, [])
        stats = db.get_library_stats()
        self.assertEqual(stats['lessons']['korean'], 1)

    def test_multi_lesson_multi_language_counts(self):
        db = make_db()
        db.upsert_lesson('korean',  'pimsleur/unit-1/lesson-01', 'L01', None, [])
        db.upsert_lesson('korean',  'pimsleur/unit-1/lesson-02', 'L02', None, [])
        db.upsert_lesson('spanish', 'lt/lesson-01',              'S01', None, [])
        stats = db.get_library_stats()
        self.assertEqual(stats['lessons']['korean'],  2)
        self.assertEqual(stats['lessons']['spanish'], 1)

    def test_upsert_does_not_double_count(self):
        db = make_db()
        db.upsert_lesson('korean', 'pimsleur/unit-1/lesson-01', 'L01', None, [])
        db.upsert_lesson('korean', 'pimsleur/unit-1/lesson-01', 'L01', None, [])  # re-upsert
        stats = db.get_library_stats()
        self.assertEqual(stats['lessons']['korean'], 1)

    def test_vocab_key_present_for_all_users(self):
        db = make_db()
        stats = db.get_library_stats()
        for user in db.get_users():
            self.assertIn(str(user['id']), stats['vocab'])

    def test_vocab_count_zero_for_new_user(self):
        db = make_db()
        stats = db.get_library_stats()
        for entry in stats['vocab'].values():
            self.assertEqual(entry['count'], 0)

    def test_vocab_count_increments(self):
        db = make_db()
        user_id = db.get_users()[0]['id']
        wid = db.upsert_word('korean', '안녕', 'hello', 'pimsleur', None, None)
        db.ensure_user_vocab(user_id, wid)
        stats = db.get_library_stats()
        self.assertEqual(stats['vocab'][str(user_id)]['count'], 1)

    def test_vocab_structure_has_required_fields(self):
        db = make_db()
        stats = db.get_library_stats()
        for entry in stats['vocab'].values():
            self.assertIn('name',     entry)
            self.assertIn('count',    entry)
            self.assertIn('language', entry)

    def test_vocab_isolated_per_user(self):
        db = make_db()
        users = db.get_users()
        robie_id = next(u['id'] for u in users if u['name'] == 'robie')
        anna_id  = next(u['id'] for u in users if u['name'] == 'anna')
        wid = db.upsert_word('korean', '안녕', 'hello', 'pimsleur', None, None)
        db.ensure_user_vocab(robie_id, wid)
        stats = db.get_library_stats()
        self.assertEqual(stats['vocab'][str(robie_id)]['count'], 1)
        self.assertEqual(stats['vocab'][str(anna_id)]['count'],  0)


class TestPandR(unittest.TestCase):
    def setUp(self):
        self.db = make_db()
        self.user_id = self.db.get_users()[0]['id']  # robie
        self.word_id = self.db.upsert_word('korean', '환영', 'welcome', 'pimsleur', None, None)
        self.db.ensure_user_vocab(self.user_id, self.word_id)

    def test_get_progress_new_user_zero_streak_and_days(self):
        """New user with no sessions shows zero streak and zero total_days."""
        progress = self.db.get_progress(self.user_id)
        self.assertEqual(progress['streak'], 0)
        self.assertEqual(progress['best_streak'], 0)
        self.assertEqual(progress['total_days'], 0)
        self.assertEqual(progress['heatmap'], {})
        self.assertEqual(progress['xp_total'], 0)

    def test_get_progress_after_one_session_shows_streak_and_day(self):
        """After logging one session, streak=1 and total_days=1."""
        self.db.log_session({
            'user_id': self.user_id,
            'language': 'korean',
            'session_type': 'pimsleur',
        })
        progress = self.db.get_progress(self.user_id)
        self.assertEqual(progress['streak'], 1)
        self.assertEqual(progress['total_days'], 1)
        self.assertIsInstance(progress['heatmap'], dict)

    def test_get_progress_xp_total_appears_in_response(self):
        """get_progress() response includes xp_total key."""
        self.db.log_xp(self.user_id, 250, 'test_source', {'test': True})
        progress = self.db.get_progress(self.user_id)
        self.assertIn('xp_total', progress)
        self.assertEqual(progress['xp_total'], 250)

    def test_get_achievements_empty_for_new_user(self):
        """New user has no achievements."""
        achievements = self.db.get_achievements(self.user_id)
        self.assertEqual(achievements, [])

    def test_check_and_award_returns_newly_earned_badges(self):
        """check_and_award() returns list of badge dicts for newly earned badges."""
        # Log a review to earn 'first_review' badge
        self.db.review_card({
            'user_id': self.user_id,
            'word_id': self.word_id,
            'rating': GOOD,
        })
        newly_earned = self.db.check_and_award(self.user_id)
        self.assertIsInstance(newly_earned, list)
        self.assertGreater(len(newly_earned), 0)
        # Should include 'first_review' badge
        badge_keys = [b['key'] for b in newly_earned]
        self.assertIn('first_review', badge_keys)

    def test_check_and_award_idempotent(self):
        """Calling check_and_award() twice does not re-award badges."""
        # Log a review to earn 'first_review'
        self.db.review_card({
            'user_id': self.user_id,
            'word_id': self.word_id,
            'rating': GOOD,
        })
        newly_earned_1 = self.db.check_and_award(self.user_id)
        newly_earned_2 = self.db.check_and_award(self.user_id)
        # First call should award badges; second should not
        self.assertGreater(len(newly_earned_1), 0)
        self.assertEqual(len(newly_earned_2), 0)

    def test_check_and_award_first_review_badge(self):
        """After first review, 'first_review' badge should be awarded."""
        self.db.review_card({
            'user_id': self.user_id,
            'word_id': self.word_id,
            'rating': GOOD,
        })
        newly_earned = self.db.check_and_award(self.user_id)
        badge_keys = [b['key'] for b in newly_earned]
        self.assertIn('first_review', badge_keys)
        # Verify it's also in the achievements table
        achievements = self.db.get_achievements(self.user_id)
        earned_keys = [a['badge_key'] for a in achievements]
        self.assertIn('first_review', earned_keys)

    def test_log_xp_adds_points(self):
        """log_xp() logs XP events to the database."""
        self.db.log_xp(self.user_id, 100, 'test_source', {'test': 'data'})
        self.db.log_xp(self.user_id, 50, 'another_source', None)
        # Verify via xp_events table
        rows = self.db._conn.execute(
            "SELECT SUM(points) as total FROM xp_events WHERE user_id=?",
            (self.user_id,)
        ).fetchone()
        self.assertEqual(rows['total'], 150)

    def test_log_xp_appears_in_get_progress(self):
        """XP logged via log_xp() appears in get_progress() xp_total."""
        self.db.log_xp(self.user_id, 300, 'session', {})
        self.db.log_xp(self.user_id, 200, 'review', {})
        progress = self.db.get_progress(self.user_id)
        self.assertEqual(progress['xp_total'], 500)

    def test_log_xp_with_meta_stores_json(self):
        """log_xp() stores meta dict as JSON string."""
        meta = {'rarity': 'legendary', 'word_id': 123}
        self.db.log_xp(self.user_id, 500, 'card_mastered', meta)
        row = self.db._conn.execute(
            "SELECT meta FROM xp_events WHERE user_id=? AND source=?",
            (self.user_id, 'card_mastered')
        ).fetchone()
        self.assertIsNotNone(row['meta'])
        # Verify it's valid JSON
        stored_meta = json.loads(row['meta'])
        self.assertEqual(stored_meta['rarity'], 'legendary')
        self.assertEqual(stored_meta['word_id'], 123)

    def test_get_progress_heatmap_includes_session_dates(self):
        """get_progress() heatmap includes session dates within 365 days."""
        self.db.log_session({
            'user_id': self.user_id,
            'language': 'korean',
            'session_type': 'pimsleur',
        })
        progress = self.db.get_progress(self.user_id)
        today = date.today().isoformat()
        self.assertIn(today, progress['heatmap'])
        self.assertGreaterEqual(progress['heatmap'][today], 1)

    def test_check_and_award_first_lesson_badge(self):
        """After logging a lesson session, 'first_lesson' badge should be awarded."""
        self.db.log_session({
            'user_id': self.user_id,
            'language': 'korean',
            'session_type': 'pimsleur',
        })
        newly_earned = self.db.check_and_award(self.user_id)
        badge_keys = [b['key'] for b in newly_earned]
        self.assertIn('first_lesson', badge_keys)


class TestRarity(unittest.TestCase):
    """Test word rarity assignment via frequency data lookup."""

    def setUp(self):
        self.db = make_db()

    def test_upsert_word_default_rarity_is_niche(self):
        # No frequency data for 'test' language → default niche
        wid = self.db.upsert_word('test', '테스트', 'test', 'manual', None, None)
        row = self.db._conn.execute("SELECT rarity FROM words WHERE id=?", (wid,)).fetchone()
        self.assertEqual(row['rarity'], 'niche')

    def test_due_cards_include_rarity(self):
        db = make_db()
        uid = db.get_users()[0]['id']
        wid = db.upsert_word('korean', '안녕', 'hello', 'manual', None, None)
        db.ensure_user_vocab(uid, wid)
        due = db.get_due_cards(uid)
        self.assertEqual(len(due), 1)
        self.assertIn('rarity', due[0])

    def test_assign_rarity_uses_frequency_data(self):
        import db as db_module
        # Inject fake frequency data
        db_module._FREQ_CACHE['fakelang'] = {'hello': 1, 'world': 600, 'obscure': 3000, 'rare_word': 10000}
        try:
            r1, rank1 = db_module._assign_rarity('hello',     'fakelang')
            r2, rank2 = db_module._assign_rarity('world',     'fakelang')
            r3, rank3 = db_module._assign_rarity('obscure',   'fakelang')
            r4, rank4 = db_module._assign_rarity('rare_word', 'fakelang')
            r5, rank5 = db_module._assign_rarity('unknown',   'fakelang')
            self.assertEqual(r1, 'fundamental')
            self.assertEqual(r2, 'essential')
            self.assertEqual(r3, 'interesting')
            self.assertEqual(r4, 'niche')
            self.assertEqual(r5, 'niche')
            self.assertEqual(rank1, 1)
            self.assertIsNone(rank5)
        finally:
            del db_module._FREQ_CACHE['fakelang']

    def test_backfill_rarity_runs_without_error(self):
        self.db.upsert_word('korean', '안녕', 'hello', 'manual', None, None)
        count = self.db.backfill_rarity('korean')
        self.assertGreaterEqual(count, 1)


if __name__ == '__main__':
    unittest.main()
