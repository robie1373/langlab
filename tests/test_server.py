"""
Integration tests for the HTTP server (server.py).

Spins up a real HTTPServer on a random port with an in-memory DB,
makes actual HTTP requests, and checks responses.
"""

import json
import sys
import threading
import unittest
import urllib.request
import urllib.error
from http.server import HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from db import Database
from server import LangLabHandler


def _start_server() -> tuple[HTTPServer, str]:
    """Start a test server on a random port. Returns (server, base_url)."""
    db = Database(':memory:')
    LangLabHandler.db = db

    server = HTTPServer(('127.0.0.1', 0), LangLabHandler)
    port   = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f'http://127.0.0.1:{port}'


def _get(url: str) -> tuple[int, dict | list | None]:
    try:
        with urllib.request.urlopen(url) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, None


def _post(url: str, body: dict) -> tuple[int, dict | None]:
    data = json.dumps(body).encode()
    req  = urllib.request.Request(
        url, data=data,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, None


class TestUsersEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server, cls.base = _start_server()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_get_users_200(self):
        status, data = _get(f'{self.base}/api/users')
        self.assertEqual(status, 200)

    def test_users_contains_robie(self):
        _, data = _get(f'{self.base}/api/users')
        names = [u['name'] for u in data]
        self.assertIn('robie', names)

    def test_users_contains_anna(self):
        _, data = _get(f'{self.base}/api/users')
        names = [u['name'] for u in data]
        self.assertIn('anna', names)


class TestLessonsEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server, cls.base = _start_server()
        # Seed a lesson
        cls.server.RequestHandlerClass.db.upsert_lesson(
            'korean', 'pimsleur/unit-1/lesson-01', 'Lesson 01',
            'korean/.../lesson-01.mp3',
            [{'start': 9.38, 'end': 9.78, 'lines': ['안녕하세요.'], 'korean': ['안녕하세요.']}]
        )

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_list_lessons_200(self):
        status, data = _get(f'{self.base}/api/lessons/korean')
        self.assertEqual(status, 200)
        self.assertIsInstance(data, list)

    def test_list_lessons_has_seeded_lesson(self):
        _, data = _get(f'{self.base}/api/lessons/korean')
        titles = [l['title'] for l in data]
        self.assertIn('Lesson 01', titles)

    def test_get_lesson_data_200(self):
        status, data = _get(f'{self.base}/api/lessons/korean/pimsleur/unit-1/lesson-01')
        self.assertEqual(status, 200)
        self.assertIn('entries', data)

    def test_get_lesson_entries_structure(self):
        _, data = _get(f'{self.base}/api/lessons/korean/pimsleur/unit-1/lesson-01')
        entry = data['entries'][0]
        self.assertIn('start',  entry)
        self.assertIn('end',    entry)
        self.assertIn('lines',  entry)
        self.assertIn('korean', entry)

    def test_missing_lesson_404(self):
        status, _ = _get(f'{self.base}/api/lessons/korean/no/such/lesson')
        self.assertEqual(status, 404)

    def test_empty_language_returns_empty_list(self):
        status, data = _get(f'{self.base}/api/lessons/klingon')
        self.assertEqual(status, 200)
        self.assertEqual(data, [])


class TestSessionsEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server, cls.base = _start_server()
        users = cls.server.RequestHandlerClass.db.get_users()
        cls.user_id = next(u['id'] for u in users if u['name'] == 'robie')

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_post_session_200(self):
        status, data = _post(f'{self.base}/api/sessions', {
            'user_id':      self.user_id,
            'language':     'korean',
            'session_type': 'pimsleur',
            'lesson_path':  'pimsleur/unit-1/lesson-06',
        })
        self.assertEqual(status, 200)
        self.assertIn('id', data)

    def test_post_session_returns_int_id(self):
        _, data = _post(f'{self.base}/api/sessions', {
            'user_id': self.user_id, 'language': 'korean', 'session_type': 'pimsleur',
        })
        self.assertIsInstance(data['id'], int)

    def test_get_sessions_200(self):
        status, data = _get(f'{self.base}/api/sessions/{self.user_id}')
        self.assertEqual(status, 200)
        self.assertIsInstance(data, list)


class TestVocabEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server, cls.base = _start_server()
        db   = cls.server.RequestHandlerClass.db
        users = db.get_users()
        cls.user_id = next(u['id'] for u in users if u['name'] == 'robie')
        cls.word_id = db.upsert_word('korean', '안녕', 'hello', 'pimsleur', None, None)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_get_vocab_200(self):
        status, _ = _get(f'{self.base}/api/vocab/{self.user_id}')
        self.assertEqual(status, 200)

    def test_rate_by_word_id_200(self):
        status, data = _post(f'{self.base}/api/vocab/rate', {
            'user_id': self.user_id,
            'word_id': self.word_id,
            'rating':  3,
        })
        self.assertEqual(status, 200)
        self.assertIn('state', data)

    def test_rate_by_word_string_200(self):
        status, data = _post(f'{self.base}/api/vocab/rate', {
            'user_id':  self.user_id,
            'word':     '감사합니다',
            'language': 'korean',
            'rating':   3,
        })
        self.assertEqual(status, 200)
        self.assertIn('word_id', data)

    def test_rate_creates_vocab_entry(self):
        _post(f'{self.base}/api/vocab/rate', {
            'user_id': self.user_id, 'word_id': self.word_id, 'rating': 4,
        })
        _, vocab = _get(f'{self.base}/api/vocab/{self.user_id}')
        words = [v['word'] for v in vocab]
        self.assertIn('안녕', words)


class TestFlashcardsEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server, cls.base = _start_server()
        db    = cls.server.RequestHandlerClass.db
        users = db.get_users()
        cls.user_id = next(u['id'] for u in users if u['name'] == 'robie')
        cls.word_id = db.upsert_word('korean', '물', 'water', 'pimsleur', None, None)
        db.ensure_user_vocab(cls.user_id, cls.word_id)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_get_due_200(self):
        status, data = _get(f'{self.base}/api/flashcards/due/{self.user_id}')
        self.assertEqual(status, 200)
        self.assertIsInstance(data, list)

    def test_new_card_appears_in_due(self):
        # Use a fresh word so test order doesn't matter
        db = self.server.RequestHandlerClass.db
        fresh_id = db.upsert_word('korean', '새', 'new/bird', 'pimsleur', None, None)
        db.ensure_user_vocab(self.user_id, fresh_id)
        _, due = _get(f'{self.base}/api/flashcards/due/{self.user_id}')
        word_ids = [c['word_id'] for c in due]
        self.assertIn(fresh_id, word_ids)

    def test_post_review_200(self):
        status, data = _post(f'{self.base}/api/flashcards/review', {
            'user_id': self.user_id,
            'word_id': self.word_id,
            'rating':  3,
        })
        self.assertEqual(status, 200)
        self.assertIn('state', data)

    def test_card_not_due_after_easy_review(self):
        _post(f'{self.base}/api/flashcards/review', {
            'user_id': self.user_id, 'word_id': self.word_id, 'rating': 4,
        })
        _, due = _get(f'{self.base}/api/flashcards/due/{self.user_id}')
        word_ids = [c['word_id'] for c in due]
        self.assertNotIn(self.word_id, word_ids)


class TestUnknownEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server, cls.base = _start_server()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_unknown_api_get_404(self):
        status, _ = _get(f'{self.base}/api/nonexistent')
        self.assertEqual(status, 404)

    def test_unknown_api_post_404(self):
        status, _ = _post(f'{self.base}/api/nonexistent', {})
        self.assertEqual(status, 404)


class TestAdminLibraryEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server, cls.base = _start_server()
        db = cls.server.RequestHandlerClass.db
        db.upsert_lesson('korean',  'pimsleur/unit-1/lesson-01', 'Lesson 01', None, [])
        db.upsert_lesson('korean',  'pimsleur/unit-1/lesson-02', 'Lesson 02', None, [])
        db.upsert_lesson('spanish', 'lt/lesson-01', 'S01', None, [])

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_library_200(self):
        status, _ = _get(f'{self.base}/api/admin/library')
        self.assertEqual(status, 200)

    def test_library_has_lessons_key(self):
        _, data = _get(f'{self.base}/api/admin/library')
        self.assertIn('lessons', data)

    def test_library_has_vocab_key(self):
        _, data = _get(f'{self.base}/api/admin/library')
        self.assertIn('vocab', data)

    def test_library_lesson_counts_correct(self):
        _, data = _get(f'{self.base}/api/admin/library')
        self.assertEqual(data['lessons']['korean'],  2)
        self.assertEqual(data['lessons']['spanish'], 1)

    def test_library_vocab_entry_per_user(self):
        _, data = _get(f'{self.base}/api/admin/library')
        self.assertEqual(len(data['vocab']), 2)

    def test_library_vocab_has_required_fields(self):
        _, data = _get(f'{self.base}/api/admin/library')
        for entry in data['vocab'].values():
            self.assertIn('name',     entry)
            self.assertIn('count',    entry)
            self.assertIn('language', entry)

    def test_library_unknown_admin_post_404(self):
        status, _ = _post(f'{self.base}/api/admin/nonexistent', {})
        self.assertEqual(status, 404)


class TestPandREndpoints(unittest.TestCase):
    """Tests for the Progress & Rewards API endpoints.
    Each test gets a fresh server/DB to avoid state bleed."""

    def setUp(self):
        self.server, self.base = _start_server()

    def tearDown(self):
        self.server.shutdown()

    def _uid(self):
        _, users = _get(f'{self.base}/api/users')
        return users[0]['id']

    def test_progress_200(self):
        status, _ = _get(f'{self.base}/api/progress/{self._uid()}')
        self.assertEqual(status, 200)

    def test_progress_fields(self):
        _, data = _get(f'{self.base}/api/progress/{self._uid()}')
        for field in ('streak', 'best_streak', 'total_days', 'heatmap', 'xp_total'):
            self.assertIn(field, data)

    def test_progress_initial_zeros(self):
        _, data = _get(f'{self.base}/api/progress/{self._uid()}')
        self.assertEqual(data['streak'],     0)
        self.assertEqual(data['total_days'], 0)
        self.assertEqual(data['xp_total'],   0)

    def test_achievements_200(self):
        status, _ = _get(f'{self.base}/api/achievements/{self._uid()}')
        self.assertEqual(status, 200)

    def test_achievements_has_badge_defs(self):
        _, data = _get(f'{self.base}/api/achievements/{self._uid()}')
        self.assertIn('badge_defs', data)
        self.assertGreater(len(data['badge_defs']), 20)

    def test_achievements_has_groups(self):
        _, data = _get(f'{self.base}/api/achievements/{self._uid()}')
        self.assertIn('badge_groups', data)
        self.assertIn('group_labels', data)

    def test_achievements_earned_empty_initially(self):
        _, data = _get(f'{self.base}/api/achievements/{self._uid()}')
        self.assertEqual(data['earned'], [])

    def test_achievements_check_post_200(self):
        status, data = _post(f'{self.base}/api/achievements/check/{self._uid()}', {})
        self.assertEqual(status, 200)
        self.assertIn('awarded', data)

    def test_achievements_check_idempotent(self):
        uid = self._uid()
        # Log a session so first_lesson is awardable
        _post(f'{self.base}/api/sessions', {
            'user_id': uid, 'language': 'korean', 'session_type': 'pimsleur'
        })
        _, d1 = _post(f'{self.base}/api/achievements/check/{uid}', {})
        _, d2 = _post(f'{self.base}/api/achievements/check/{uid}', {})
        # Second call should award nothing new
        self.assertEqual(d2['awarded'], [])


if __name__ == '__main__':
    unittest.main()
