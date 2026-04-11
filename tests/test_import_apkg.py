"""
Tests for scripts/import_apkg.py.

Builds synthetic .apkg files (zip + SQLite) in memory/tmpdir to exercise
the full import pipeline without needing real Anki decks.
"""

import json
import os
import sqlite3
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from db import Database
import import_apkg as imp


# ── helpers ───────────────────────────────────────────────────────────────────

_apkg_counter = 0

def make_anki_db(tmpdir: str, notes: list[list[str]], filename: str = 'collection.anki2') -> str:
    """Create a minimal Anki collection.anki2 SQLite file.

    Args:
        notes:    list of field lists, e.g. [['한국어', 'English'], ...]
        filename: name for the SQLite file inside tmpdir

    Returns path to the created .db file.
    """
    db_path = os.path.join(tmpdir, filename)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE notes (id INTEGER PRIMARY KEY, flds TEXT NOT NULL)"
    )
    for fields in notes:
        conn.execute("INSERT INTO notes (flds) VALUES (?)", ('\x1f'.join(fields),))
    conn.commit()
    conn.close()
    return db_path


def make_apkg(tmpdir: str, notes: list[list[str]], db_name: str = 'collection.anki2') -> str:
    """Wrap a synthetic Anki DB in a .apkg zip file. Returns .apkg path.

    Each call generates a unique filename to avoid collisions when called
    multiple times within the same tmpdir.
    """
    global _apkg_counter
    _apkg_counter += 1
    unique_db = f'collection_{_apkg_counter}.anki2'
    db_path   = make_anki_db(tmpdir, notes, filename=unique_db)
    apkg_path = os.path.join(tmpdir, f'test_{_apkg_counter}.apkg')
    with zipfile.ZipFile(apkg_path, 'w') as z:
        z.write(db_path, db_name)
    return apkg_path


# ── unit tests: field helpers ─────────────────────────────────────────────────

class TestSplitFields(unittest.TestCase):
    def test_single_field(self):
        self.assertEqual(imp.split_fields('hello'), ['hello'])

    def test_two_fields(self):
        self.assertEqual(imp.split_fields('안녕\x1fhello'), ['안녕', 'hello'])

    def test_three_fields(self):
        parts = imp.split_fields('word\x1ftrans\x1fexample')
        self.assertEqual(parts, ['word', 'trans', 'example'])

    def test_empty_string(self):
        self.assertEqual(imp.split_fields(''), [''])

    def test_trailing_separator(self):
        parts = imp.split_fields('a\x1fb\x1f')
        self.assertEqual(parts, ['a', 'b', ''])


class TestStripMarkup(unittest.TestCase):
    def test_plain_text_unchanged(self):
        self.assertEqual(imp.strip_markup('안녕하세요'), '안녕하세요')

    def test_html_tags_removed(self):
        self.assertEqual(imp.strip_markup('<b>hello</b>'), 'hello')

    def test_nested_html_removed(self):
        self.assertEqual(imp.strip_markup('<div class="x"><span>word</span></div>'), 'word')

    def test_sound_ref_removed(self):
        self.assertEqual(imp.strip_markup('[sound:hello.mp3]'), '')

    def test_sound_ref_with_surrounding_text(self):
        result = imp.strip_markup('안녕[sound:hello.mp3]')
        self.assertEqual(result, '안녕')

    def test_cloze_deletion_removed(self):
        self.assertEqual(imp.strip_markup('{{c1::word}}'), '')

    def test_nbsp_replaced(self):
        self.assertEqual(imp.strip_markup('a&nbsp;b'), 'a b')

    def test_html_entities(self):
        self.assertEqual(imp.strip_markup('&amp;&lt;&gt;'), '&<>')

    def test_whitespace_stripped(self):
        self.assertEqual(imp.strip_markup('  hello  '), 'hello')

    def test_combined(self):
        result = imp.strip_markup('<b>안녕</b>[sound:hi.mp3]<i>하세요</i>')
        self.assertEqual(result, '안녕하세요')


# ── integration tests: full import pipeline ───────────────────────────────────

class TestImportApkg(unittest.TestCase):
    def setUp(self):
        self.tmpdir  = tempfile.mkdtemp()
        self.db      = Database(':memory:')
        self.user_id = next(u['id'] for u in self.db.get_users() if u['name'] == 'robie')

    def _import(self, notes, **kwargs):
        apkg = make_apkg(self.tmpdir, notes)
        return imp.import_apkg(
            apkg_path  = apkg,
            db         = self.db,
            user_id    = self.user_id,
            language   = 'korean',
            deck_name  = 'Test Deck',
            **kwargs
        )

    # ── happy path ─────────────────────────────────────────────────────────

    def test_simple_import_returns_count(self):
        n = self._import([['안녕', 'hello'], ['감사합니다', 'thank you']])
        self.assertEqual(n, 2)

    def test_words_appear_in_db(self):
        self._import([['물', 'water'], ['불', 'fire']])
        vocab = self.db.get_user_vocab(self.user_id)
        words = {v['word'] for v in vocab}
        self.assertIn('물', words)
        self.assertIn('불', words)

    def test_translations_stored(self):
        self._import([['안녕', 'hello']])
        row = self.db._conn.execute(
            "SELECT translation FROM words WHERE word='안녕' AND language='korean'"
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row['translation'], 'hello')

    def test_deck_created(self):
        self._import([['하나', 'one']])
        row = self.db._conn.execute(
            "SELECT id FROM decks WHERE user_id=? AND name='Test Deck'", (self.user_id,)
        ).fetchone()
        self.assertIsNotNone(row)

    def test_words_added_to_deck(self):
        self._import([['둘', 'two'], ['셋', 'three']])
        deck = self.db._conn.execute(
            "SELECT id FROM decks WHERE user_id=? AND name='Test Deck'", (self.user_id,)
        ).fetchone()
        count = self.db._conn.execute(
            "SELECT COUNT(*) FROM deck_words WHERE deck_id=?", (deck['id'],)
        ).fetchone()[0]
        self.assertEqual(count, 2)

    def test_user_vocab_entries_created(self):
        self._import([['넷', 'four'], ['다섯', 'five']])
        vocab = self.db.get_user_vocab(self.user_id)
        self.assertGreaterEqual(len(vocab), 2)

    def test_html_stripped_from_fields(self):
        self._import([['<b>여섯</b>', '<i>six</i>']])
        row = self.db._conn.execute(
            "SELECT translation FROM words WHERE word='여섯'"
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row['translation'], 'six')

    def test_sound_refs_stripped(self):
        self._import([['일곱[sound:7.mp3]', 'seven']])
        row = self.db._conn.execute(
            "SELECT id FROM words WHERE word='일곱'"
        ).fetchone()
        self.assertIsNotNone(row)

    def test_idempotent_second_import(self):
        """Re-importing the same deck should not duplicate words or vocab entries."""
        notes = [['여덟', 'eight'], ['아홉', 'nine']]
        n1 = self._import(notes)
        n2 = self._import(notes)
        self.assertEqual(n1, 2)
        self.assertEqual(n2, 2)
        vocab = self.db.get_user_vocab(self.user_id)
        words = [v['word'] for v in vocab]
        self.assertEqual(words.count('여덟'), 1)

    # ── field index options ────────────────────────────────────────────────

    def test_custom_field_indices(self):
        """Field order reversed: translation first, word second."""
        self._import([['ten', '열']], field_word=1, field_trans=0)
        row = self.db._conn.execute(
            "SELECT translation FROM words WHERE word='열'"
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row['translation'], 'ten')

    def test_three_field_note_uses_first_two(self):
        self._import([['열하나', 'eleven', 'extra_field']])
        row = self.db._conn.execute(
            "SELECT translation FROM words WHERE word='열하나'"
        ).fetchone()
        self.assertEqual(row['translation'], 'eleven')

    # ── edge cases ─────────────────────────────────────────────────────────

    def test_empty_word_skipped(self):
        n = self._import([['', 'empty'], ['진짜', 'real']])
        self.assertEqual(n, 1)

    def test_single_field_note_no_translation(self):
        n = self._import([['단어']])
        self.assertEqual(n, 1)
        row = self.db._conn.execute(
            "SELECT translation FROM words WHERE word='단어'"
        ).fetchone()
        self.assertIsNone(row['translation'])

    def test_empty_deck(self):
        n = self._import([])
        self.assertEqual(n, 0)

    def test_dry_run_returns_zero(self):
        n = self._import([['안녕', 'hello']], dry_run=True)
        self.assertEqual(n, 0)

    def test_dry_run_does_not_write(self):
        self._import([['테스트', 'test']], dry_run=True)
        vocab = self.db.get_user_vocab(self.user_id)
        words = {v['word'] for v in vocab}
        self.assertNotIn('테스트', words)

    # ── file format ────────────────────────────────────────────────────────

    def test_anki21_format_accepted(self):
        """Some Anki versions use collection.anki21 instead of collection.anki2."""
        notes = [['hello', 'world']]
        apkg = os.path.join(self.tmpdir, 'new_format.apkg')

        db_path = make_anki_db(self.tmpdir, notes)
        with zipfile.ZipFile(apkg, 'w') as z:
            z.write(db_path, 'collection.anki21')

        n = imp.import_apkg(apkg, self.db, self.user_id, 'korean', 'fmt_test')
        self.assertEqual(n, 1)

    def test_missing_db_raises(self):
        apkg = os.path.join(self.tmpdir, 'bad.apkg')
        with zipfile.ZipFile(apkg, 'w') as z:
            z.writestr('media', '{}')   # no collection file

        with self.assertRaises(FileNotFoundError):
            imp.import_apkg(apkg, self.db, self.user_id, 'korean', 'bad')

    def test_nonexistent_apkg_raises(self):
        with self.assertRaises(Exception):
            imp.import_apkg('/nonexistent.apkg', self.db, self.user_id, 'korean', 'x')

    # ── multi-user isolation ───────────────────────────────────────────────

    def test_import_isolated_per_user(self):
        anna_id = next(u['id'] for u in self.db.get_users() if u['name'] == 'anna')
        self._import([['안녕', 'hello']])

        anna_vocab = self.db.get_user_vocab(anna_id)
        self.assertEqual(anna_vocab, [])

    def test_same_word_different_users(self):
        anna_id = next(u['id'] for u in self.db.get_users() if u['name'] == 'anna')
        apkg = make_apkg(self.tmpdir, [['hola', 'hello']])

        imp.import_apkg(apkg, self.db, self.user_id, 'spanish', 'Deck A')
        imp.import_apkg(apkg, self.db, anna_id,     'spanish', 'Deck A')

        robie_vocab = {v['word'] for v in self.db.get_user_vocab(self.user_id)}
        anna_vocab  = {v['word'] for v in self.db.get_user_vocab(anna_id)}
        self.assertIn('hola', robie_vocab)
        self.assertIn('hola', anna_vocab)


# ── server: /api/config (not previously covered) ─────────────────────────────

class TestConfigEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import threading
        from http.server import HTTPServer
        from server import LangLabHandler

        db = Database(':memory:')
        LangLabHandler.db = db

        cls.server = HTTPServer(('127.0.0.1', 0), LangLabHandler)
        port = cls.server.server_address[1]
        t = threading.Thread(target=cls.server.serve_forever, daemon=True)
        t.start()
        cls.base = f'http://127.0.0.1:{port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def _get(self, path):
        import urllib.request
        import urllib.error
        try:
            with urllib.request.urlopen(f'{self.base}{path}') as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            try:   return e.code, json.loads(e.read())
            except: return e.code, None

    def test_config_200(self):
        status, _ = self._get('/api/config')
        self.assertEqual(status, 200)

    def test_config_has_gemini_key_field(self):
        _, data = self._get('/api/config')
        self.assertIn('gemini_api_key', data)

    def test_config_has_claude_key_field(self):
        _, data = self._get('/api/config')
        self.assertIn('claude_api_key', data)


# ── server: new session_types ─────────────────────────────────────────────────

class TestAISessionTypes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import threading
        import urllib.request
        import urllib.error
        from http.server import HTTPServer
        from server import LangLabHandler

        db = Database(':memory:')
        LangLabHandler.db = db

        cls.server = HTTPServer(('127.0.0.1', 0), LangLabHandler)
        port = cls.server.server_address[1]
        t = threading.Thread(target=cls.server.serve_forever, daemon=True)
        t.start()
        cls.base    = f'http://127.0.0.1:{port}'
        cls.user_id = next(u['id'] for u in db.get_users() if u['name'] == 'robie')

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def _post(self, path, body):
        import urllib.request, urllib.error
        data = json.dumps(body).encode()
        req  = urllib.request.Request(
            f'{self.base}{path}', data=data,
            headers={'Content-Type': 'application/json'}, method='POST'
        )
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            try:   return e.code, json.loads(e.read())
            except: return e.code, None

    def _check_session_type(self, session_type):
        status, data = self._post('/api/sessions', {
            'user_id':      self.user_id,
            'language':     'korean',
            'session_type': session_type,
        })
        self.assertEqual(status, 200, msg=f'session_type={session_type!r} returned {status}')
        self.assertIn('id', data)
        self.assertIsInstance(data['id'], int)

    def test_ai_lesson_session(self):
        self._check_session_type('ai_lesson')

    def test_tutor_session(self):
        self._check_session_type('tutor')

    def test_flashcard_session(self):
        self._check_session_type('flashcard')

    def test_free_session(self):
        self._check_session_type('free')

    def test_ai_lesson_appears_in_history(self):
        self._post('/api/sessions', {
            'user_id': self.user_id, 'language': 'spanish', 'session_type': 'ai_lesson',
        })
        import urllib.request
        with urllib.request.urlopen(f'{self.base}/api/sessions/{self.user_id}') as r:
            sessions = json.loads(r.read())
        types = {s['session_type'] for s in sessions}
        self.assertIn('ai_lesson', types)


if __name__ == '__main__':
    unittest.main()
