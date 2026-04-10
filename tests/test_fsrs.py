"""
Unit tests for the FSRS v5 algorithm (fsrs.py).

Checks state transitions, stability/difficulty bounds,
due-date scheduling, and known algorithm invariants.
"""

import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fsrs import (
    Card, review,
    NEW, LEARNING, REVIEW, RELEARNING,
    AGAIN, HARD, GOOD, EASY,
    DESIRED_RETENTION,
)


class TestNewCard(unittest.TestCase):
    """New card (state=0) behaviour for each rating."""

    def _review(self, rating):
        return review(Card(), rating)

    def test_again_stays_learning(self):
        card, _ = self._review(AGAIN)
        self.assertEqual(card.state, LEARNING)

    def test_hard_goes_learning(self):
        card, _ = self._review(HARD)
        self.assertEqual(card.state, LEARNING)

    def test_good_goes_learning(self):
        card, _ = self._review(GOOD)
        self.assertEqual(card.state, LEARNING)

    def test_easy_graduates_to_review(self):
        card, _ = self._review(EASY)
        self.assertEqual(card.state, REVIEW)

    def test_easy_scheduled_days_positive(self):
        card, _ = self._review(EASY)
        self.assertGreater(card.scheduled_days, 0)

    def test_stability_positive_after_new(self):
        for rating in (AGAIN, HARD, GOOD, EASY):
            with self.subTest(rating=rating):
                card, _ = self._review(rating)
                self.assertGreater(card.stability, 0)

    def test_difficulty_in_range(self):
        for rating in (AGAIN, HARD, GOOD, EASY):
            with self.subTest(rating=rating):
                card, _ = self._review(rating)
                self.assertGreaterEqual(card.difficulty, 1.0)
                self.assertLessEqual(card.difficulty, 10.0)

    def test_reps_increments(self):
        card, _ = self._review(GOOD)
        self.assertEqual(card.reps, 1)

    def test_due_at_set(self):
        card, _ = self._review(GOOD)
        self.assertIsNotNone(card.due_at)
        self.assertGreater(card.due_at, 0)

    def test_again_shorter_interval_than_good(self):
        _, secs_again = self._review(AGAIN)
        _, secs_good  = self._review(GOOD)
        self.assertLessEqual(secs_again, secs_good)

    def test_good_shorter_interval_than_easy(self):
        _, secs_good = self._review(GOOD)
        _, secs_easy = self._review(EASY)
        self.assertLessEqual(secs_good, secs_easy)


class TestLearningCard(unittest.TestCase):
    """Learning card state transitions."""

    def _learning_card(self):
        card, _ = review(Card(), GOOD)   # New → Learning
        return card

    def test_again_stays_learning(self):
        c = self._learning_card()
        updated, _ = review(c, AGAIN)
        self.assertEqual(updated.state, LEARNING)

    def test_easy_graduates_to_review(self):
        c = self._learning_card()
        updated, _ = review(c, EASY)
        self.assertEqual(updated.state, REVIEW)

    def test_good_eventually_graduates(self):
        c = self._learning_card()
        # After enough Good ratings through learning steps, state becomes Review
        for _ in range(5):
            c, _ = review(c, GOOD)
            if c.state == REVIEW:
                break
        self.assertEqual(c.state, REVIEW)

    def test_lapses_unchanged_in_learning(self):
        c = self._learning_card()
        updated, _ = review(c, AGAIN)
        self.assertEqual(updated.lapses, 0)


class TestReviewCard(unittest.TestCase):
    """Review card behaviour."""

    def _review_card(self):
        c = Card()
        c, _ = review(c, EASY)    # New → Review
        return c

    def test_again_goes_relearning(self):
        c = self._review_card()
        updated, _ = review(c, AGAIN)
        self.assertEqual(updated.state, RELEARNING)

    def test_again_increments_lapses(self):
        c = self._review_card()
        updated, _ = review(c, AGAIN)
        self.assertEqual(updated.lapses, 1)

    def test_good_stays_review(self):
        c = self._review_card()
        updated, _ = review(c, GOOD)
        self.assertEqual(updated.state, REVIEW)

    def test_easy_stays_review(self):
        c = self._review_card()
        updated, _ = review(c, EASY)
        self.assertEqual(updated.state, REVIEW)

    def test_good_longer_interval_than_hard(self):
        c = self._review_card()
        _, secs_hard = review(c, HARD)
        _, secs_good = review(c, GOOD)
        self.assertLessEqual(secs_hard, secs_good)

    def test_easy_longest_interval(self):
        c = self._review_card()
        _, secs_good = review(c, GOOD)
        _, secs_easy = review(c, EASY)
        self.assertLessEqual(secs_good, secs_easy)

    def test_stability_grows_on_good(self):
        import time
        c = self._review_card()
        s_before = c.stability
        # Simulate 10 days elapsed; reviewing at t=0 gives R≈1 and ~zero growth
        c.last_review = time.time() - 10 * 86400
        updated, _ = review(c, GOOD)
        self.assertGreater(updated.stability, s_before)

    def test_stability_drops_on_again(self):
        c = self._review_card()
        s_before = c.stability
        updated, _ = review(c, AGAIN)
        self.assertLess(updated.stability, s_before)

    def test_difficulty_decreases_on_easy(self):
        """Easy rating should make a hard card easier over time."""
        c = Card()
        c, _ = review(c, AGAIN)  # start with hard card
        c, _ = review(c, AGAIN)
        # Graduate it
        c, _ = review(c, EASY)
        d_before = c.difficulty
        updated, _ = review(c, EASY)
        self.assertLessEqual(updated.difficulty, d_before + 0.01)  # allow float noise

    def test_difficulty_bounds_maintained(self):
        c = self._review_card()
        for rating in (AGAIN, AGAIN, AGAIN, EASY, EASY, EASY):
            c, _ = review(c, rating)
            if c.state == RELEARNING:
                c, _ = review(c, EASY)  # re-graduate
            self.assertGreaterEqual(c.difficulty, 1.0)
            self.assertLessEqual(c.difficulty, 10.0)


class TestReLearningCard(unittest.TestCase):
    """Relearning (lapsed review) card behaviour."""

    def _relearning_card(self):
        c = Card()
        c, _ = review(c, EASY)    # New → Review
        c, _ = review(c, AGAIN)   # Review → Relearning
        return c

    def test_state_is_relearning(self):
        c = self._relearning_card()
        self.assertEqual(c.state, RELEARNING)

    def test_easy_re_graduates_to_review(self):
        c = self._relearning_card()
        updated, _ = review(c, EASY)
        self.assertEqual(updated.state, REVIEW)

    def test_again_stays_relearning(self):
        c = self._relearning_card()
        updated, _ = review(c, AGAIN)
        self.assertEqual(updated.state, RELEARNING)

    def test_lapse_count_preserved(self):
        c = self._relearning_card()
        self.assertEqual(c.lapses, 1)
        updated, _ = review(c, AGAIN)
        self.assertEqual(updated.lapses, 1)  # lapses only inc on Review→Relearning


class TestCardFromRow(unittest.TestCase):
    """Card.from_row handles missing / extra fields gracefully."""

    def test_empty_row(self):
        c = Card.from_row({})
        self.assertEqual(c.state, NEW)
        self.assertEqual(c.reps, 0)

    def test_partial_row(self):
        c = Card.from_row({'state': REVIEW, 'stability': 12.5})
        self.assertEqual(c.state, REVIEW)
        self.assertAlmostEqual(c.stability, 12.5)


class TestSchedulingMonotonicity(unittest.TestCase):
    """Higher ratings always produce longer or equal intervals."""

    def test_new_card_interval_order(self):
        intervals = []
        for r in (AGAIN, HARD, GOOD, EASY):
            _, secs = review(Card(), r)
            intervals.append(secs)
        for i in range(len(intervals) - 1):
            self.assertLessEqual(intervals[i], intervals[i + 1],
                                 msg=f'Rating {i+1} interval > rating {i+2} interval')


if __name__ == '__main__':
    unittest.main()
