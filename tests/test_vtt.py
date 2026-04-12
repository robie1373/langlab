"""
Tests for VTT parsing utilities.

Covers both:
- server.py module-level functions: _tc_to_secs, _parse_vtt_text, _pair_korean
- scripts/ingest_vtt.py functions: parse_vtt (via temp file), pair_entries
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from server import _tc_to_secs, _parse_vtt_text, _pair_korean
import ingest_vtt as ivtt


# ── fixtures ──────────────────────────────────────────────────────────────────

VTT_MIXED = """\
WEBVTT

00:09.380 --> 00:09.780
안녕하세요.

00:10.000 --> 00:11.000
Hello, how are you today?

00:12.000 --> 00:13.000
감사합니다.

00:14.000 --> 00:15.000
Thank you very much indeed.
"""

VTT_HH_FORMAT = """\
WEBVTT

00:00:09.380 --> 00:00:09.780
안녕하세요.

00:01:30.000 --> 00:01:31.000
Hello, how are you today?
"""

VTT_EMPTY = "WEBVTT\n\n"

VTT_NO_TEXT_BLOCK = """\
WEBVTT

00:00:01.000 --> 00:00:02.000
"""

VTT_WITH_CUES = """\
WEBVTT

1
00:09.380 --> 00:09.780
안녕하세요.

2
00:10.000 --> 00:11.000
Hello, how are you today?
"""


# ── _tc_to_secs ───────────────────────────────────────────────────────────────

class TestTcToSecs(unittest.TestCase):

    def test_hms_zero(self):
        self.assertAlmostEqual(_tc_to_secs(('0', '0', '0', '0')), 0.0)

    def test_hms_seconds(self):
        self.assertAlmostEqual(_tc_to_secs(('0', '0', '9', '38')), 9.38, places=5)

    def test_hms_full_hours(self):
        self.assertAlmostEqual(_tc_to_secs(('1', '0', '0', '0')), 3600.0)

    def test_hms_minutes(self):
        self.assertAlmostEqual(_tc_to_secs(('0', '1', '30', '0')), 90.0)

    def test_ms_format(self):
        self.assertAlmostEqual(_tc_to_secs(('0', '9', '38')), 9.38, places=5)

    def test_ms_format_minutes(self):
        self.assertAlmostEqual(_tc_to_secs(('1', '30', '0')), 90.0)

    def test_ms_precision_two_digits(self):
        # '38' → 38/100 = 0.38
        self.assertAlmostEqual(_tc_to_secs(('0', '0', '38')), 0.38, places=5)

    def test_ms_precision_three_digits(self):
        # '380' → 380/1000 = 0.38
        self.assertAlmostEqual(_tc_to_secs(('0', '0', '380')), 0.38, places=5)


# ── _parse_vtt_text ───────────────────────────────────────────────────────────

class TestParseVttText(unittest.TestCase):

    def test_entry_count(self):
        entries = _parse_vtt_text(VTT_MIXED)
        self.assertEqual(len(entries), 4)

    def test_entry_has_required_keys(self):
        entries = _parse_vtt_text(VTT_MIXED)
        for e in entries:
            self.assertIn('start',  e)
            self.assertIn('end',    e)
            self.assertIn('lines',  e)
            self.assertIn('korean', e)

    def test_korean_line_detected(self):
        entries = _parse_vtt_text(VTT_MIXED)
        self.assertEqual(entries[0]['korean'], ['안녕하세요.'])

    def test_english_line_has_empty_korean(self):
        entries = _parse_vtt_text(VTT_MIXED)
        self.assertEqual(entries[1]['korean'], [])

    def test_start_end_mm_format(self):
        entries = _parse_vtt_text(VTT_MIXED)
        self.assertAlmostEqual(entries[0]['start'], 9.38, places=2)
        self.assertAlmostEqual(entries[0]['end'],   9.78, places=2)

    def test_start_end_hh_format(self):
        entries = _parse_vtt_text(VTT_HH_FORMAT)
        self.assertAlmostEqual(entries[0]['start'], 9.38, places=2)
        self.assertAlmostEqual(entries[1]['start'], 90.0, places=2)

    def test_empty_vtt_returns_empty(self):
        self.assertEqual(_parse_vtt_text(VTT_EMPTY), [])

    def test_block_without_text_skipped(self):
        self.assertEqual(_parse_vtt_text(VTT_NO_TEXT_BLOCK), [])

    def test_webvtt_header_not_in_lines(self):
        entries = _parse_vtt_text(VTT_MIXED)
        for e in entries:
            self.assertNotIn('WEBVTT', e['lines'])

    def test_numeric_cue_ids_not_in_lines(self):
        entries = _parse_vtt_text(VTT_WITH_CUES)
        for e in entries:
            for line in e['lines']:
                self.assertFalse(line.strip().isdigit(),
                                 msg=f'Cue ID leaked into lines: {line!r}')

    def test_multi_korean_lines_in_one_entry(self):
        vtt = "WEBVTT\n\n00:01.000 --> 00:02.000\n안녕.\n감사.\n"
        entries = _parse_vtt_text(vtt)
        self.assertEqual(len(entries[0]['korean']), 2)

    def test_lines_contains_all_text(self):
        entries = _parse_vtt_text(VTT_MIXED)
        self.assertIn('안녕하세요.', entries[0]['lines'])


# ── _pair_korean ──────────────────────────────────────────────────────────────

def _make_entries(specs):
    """Build entry dicts from a list of line-lists."""
    entries = []
    for i, lines in enumerate(specs):
        entries.append({
            'start': float(i),
            'end':   float(i) + 0.5,
            'lines': lines,
            'korean': [l for l in lines
                       if any('\uAC00' <= c <= '\uD7AF' for c in l)],
        })
    return entries


class TestPairKorean(unittest.TestCase):

    def test_english_before_korean_is_paired(self):
        entries = _make_entries([
            ['Hello, how are you today?'],
            ['안녕하세요.'],
        ])
        cards = _pair_korean(entries, 'pimsleur/unit-1/lesson-01')
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]['translation'], 'Hello, how are you today?')

    def test_no_english_context_gives_none(self):
        entries = _make_entries([['안녕하세요.']])
        cards = _pair_korean(entries, 'test')
        self.assertIsNone(cards[0]['translation'])

    def test_short_english_skipped(self):
        # < 3 words
        entries = _make_entries([
            ['Yes.'],
            ['안녕하세요.'],
        ])
        cards = _pair_korean(entries, 'test')
        self.assertIsNone(cards[0]['translation'])

    def test_card_has_word_key(self):
        entries = _make_entries([['안녕하세요.']])
        cards = _pair_korean(entries, 'test')
        self.assertIn('word', cards[0])
        self.assertEqual(cards[0]['word'], '안녕하세요.')

    def test_card_has_start_end(self):
        entries = _make_entries([['안녕하세요.']])
        cards = _pair_korean(entries, 'test')
        self.assertIn('start', cards[0])
        self.assertIn('end',   cards[0])

    def test_no_korean_produces_no_cards(self):
        entries = _make_entries([
            ['Hello there today.'],
            ['How are you doing?'],
        ])
        self.assertEqual(_pair_korean(entries, 'test'), [])

    def test_lookback_does_not_exceed_3_entries(self):
        # English at i=0, Korean at i=4 — i=0 is 4 entries back (out of window)
        # Entries 1-3 are short placeholders
        entries = _make_entries([
            ['Good morning to you today'],  # i=0 — too far back
            ['Short'],                       # i=1 — < 3 words
            ['Short'],                       # i=2 — < 3 words
            ['Short'],                       # i=3 — < 3 words
            ['안녕하세요.'],                 # i=4 — lookback: [3, 2, 1]
        ])
        cards = _pair_korean(entries, 'test')
        self.assertIsNone(cards[0]['translation'])

    def test_nearest_english_wins(self):
        entries = _make_entries([
            ['Good morning how are you'],  # i=0 — farther
            ['Hello how are you doing'],   # i=1 — closer
            ['안녕하세요.'],               # i=2 — lookback: [1, 0]
        ])
        cards = _pair_korean(entries, 'test')
        self.assertEqual(cards[0]['translation'], 'Hello how are you doing')

    def test_multiple_korean_in_one_entry(self):
        entries = _make_entries([
            ['Hello, how are you today?'],
            ['안녕하세요. 감사합니다.'],  # two Korean in lines; but korean field has one entry
        ])
        # Each korean line in entry.korean gets a card
        cards = _pair_korean(entries, 'test')
        self.assertEqual(len(cards), 1)  # only one item in 'korean' field


# ── ingest_vtt.py parse_vtt (via temp file) ───────────────────────────────────

class TestIngestVttParseVtt(unittest.TestCase):
    """Tests for scripts/ingest_vtt.py parse_vtt(), exercised via temp VTT file."""

    def _parse(self, content: str):
        with tempfile.NamedTemporaryFile(suffix='.vtt', mode='w',
                                         encoding='utf-8', delete=False) as f:
            f.write(content)
            path = Path(f.name)
        try:
            return ivtt.parse_vtt(path)
        finally:
            path.unlink()

    def test_basic_parse(self):
        entries = self._parse(VTT_MIXED)
        self.assertEqual(len(entries), 4)

    def test_entry_is_entry_dataclass(self):
        entries = self._parse(VTT_MIXED)
        e = entries[0]
        self.assertTrue(hasattr(e, 'start'))
        self.assertTrue(hasattr(e, 'end'))
        self.assertTrue(hasattr(e, 'lines'))
        self.assertTrue(hasattr(e, 'korean'))

    def test_korean_lines_populated(self):
        entries = self._parse(VTT_MIXED)
        self.assertIn('안녕하세요.', entries[0].korean)

    def test_empty_vtt_returns_empty(self):
        self.assertEqual(self._parse(VTT_EMPTY), [])

    def test_hh_format_parsed(self):
        entries = self._parse(VTT_HH_FORMAT)
        self.assertAlmostEqual(entries[0].start, 9.38, places=2)


# ── ingest_vtt.py pair_entries ────────────────────────────────────────────────

class TestIngestVttPairEntries(unittest.TestCase):

    def _pair(self, specs, lesson_id='test/lesson'):
        entries = []
        for i, (lines, korean) in enumerate(specs):
            entries.append(ivtt.Entry(
                start=float(i), end=float(i)+0.5,
                lines=lines, korean=korean,
            ))
        return ivtt.pair_entries(entries, lesson_id)

    def test_english_before_korean_paired(self):
        cards = self._pair([
            (['Hello, how are you today?'], []),
            (['안녕하세요.'], ['안녕하세요.']),
        ])
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].translation, 'Hello, how are you today?')

    def test_no_context_marked_ambiguous(self):
        cards = self._pair([
            (['안녕하세요.'], ['안녕하세요.']),
        ])
        self.assertTrue(cards[0].ambiguous)
        self.assertEqual(cards[0].ambiguity_reason, 'no_english_context')

    def test_multiple_candidates_flagged(self):
        cards = self._pair([
            (['Good morning how are you'],      []),
            (['Hello how are you doing today'], []),
            (['안녕하세요.'], ['안녕하세요.']),
        ])
        self.assertTrue(cards[0].ambiguous)
        self.assertIn('multiple_candidates', cards[0].ambiguity_reason)

    def test_single_clear_match_not_ambiguous(self):
        cards = self._pair([
            (['Hello, how are you today?'], []),
            (['안녕하세요.'], ['안녕하세요.']),
        ])
        self.assertFalse(cards[0].ambiguous)

    def test_card_has_source_lesson(self):
        cards = self._pair([
            (['안녕하세요.'], ['안녕하세요.']),
        ], lesson_id='pimsleur/unit-1/lesson-01')
        self.assertEqual(cards[0].source_lesson, 'pimsleur/unit-1/lesson-01')

    def test_no_korean_entries_no_cards(self):
        cards = self._pair([
            (['Hello, how are you today?'], []),
            (['Fine thank you very much'],  []),
        ])
        self.assertEqual(cards, [])


if __name__ == '__main__':
    unittest.main()
