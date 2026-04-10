"""
FSRS v5 spaced repetition algorithm.
Based on the open-spaced-repetition/fsrs4anki specification.
Weights are the community-trained defaults targeting 90% retention.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

# FSRS v5 default weights (19 parameters)
W = [
    0.4072, 1.1829, 3.1262, 15.4722,  # w[0-3]: initial stability per rating
    7.2102, 0.5316, 1.0651, 0.0589,   # w[4-7]: difficulty
    1.5330, 0.1544, 1.0070,            # w[8-10]: recall stability multipliers
    1.9395, 0.1100, 0.2900, 2.2700,   # w[11-14]: forget stability
    0.0000, 2.9898,                    # w[15-16]: hard/easy penalty/bonus
    0.5100, 0.4300,                    # w[17-18]: short-term stability
]

DECAY = -0.5
FACTOR = 0.9 ** (1.0 / DECAY) - 1.0
DESIRED_RETENTION = 0.90

# Card states
NEW        = 0
LEARNING   = 1
REVIEW     = 2
RELEARNING = 3

# Ratings
AGAIN = 1
HARD  = 2
GOOD  = 3
EASY  = 4

# Learning steps (seconds): 1 minute, then 10 minutes
LEARNING_STEPS = [60, 600]
# Relearning steps (seconds): 10 minutes
RELEARNING_STEPS = [600]


@dataclass
class Card:
    stability:      float = 0.0
    difficulty:     float = 0.0
    elapsed_days:   float = 0.0
    scheduled_days: float = 0.0
    reps:           int   = 0
    lapses:         int   = 0
    state:          int   = NEW
    due_at:         Optional[int] = None   # unix timestamp
    last_review:    float = 0.0            # unix timestamp float

    @classmethod
    def from_row(cls, row: dict) -> 'Card':
        return cls(
            stability      = row.get('stability', 0.0),
            difficulty     = row.get('difficulty', 0.0),
            elapsed_days   = row.get('elapsed_days', 0.0),
            scheduled_days = row.get('scheduled_days', 0.0),
            reps           = row.get('reps', 0),
            lapses         = row.get('lapses', 0),
            state          = row.get('state', NEW),
            due_at         = row.get('due_at'),
            last_review    = row.get('last_review', 0.0),
        )


def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


def _init_stability(rating: int) -> float:
    return W[rating - 1]


def _init_difficulty(rating: int) -> float:
    d = W[4] - math.exp(W[5] * (rating - 1)) + 1
    return _clamp(d, 1.0, 10.0)


def _retrievability(elapsed_days: float, stability: float) -> float:
    if stability <= 0:
        return 0.0
    return (1 + FACTOR * elapsed_days / stability) ** DECAY


def _next_interval(stability: float) -> int:
    interval = stability * math.log(DESIRED_RETENTION) / math.log(0.9)
    return max(1, round(interval))


def _next_difficulty(difficulty: float, rating: int) -> float:
    d = difficulty - W[6] * (rating - 3)
    # Mean-reversion toward initial difficulty for rating=4
    d = W[7] * _init_difficulty(EASY) + (1 - W[7]) * d
    return _clamp(d, 1.0, 10.0)


def _recall_stability(d: float, s: float, r: float, rating: int) -> float:
    hard_penalty = W[15] if rating == HARD else 1.0
    easy_bonus   = W[16] if rating == EASY else 1.0
    return s * math.exp(W[8]) * (11 - d) * (s ** -W[9]) * (math.exp(W[10] * (1 - r)) - 1) * hard_penalty * easy_bonus


def _forget_stability(d: float, s: float, r: float) -> float:
    return W[11] * (d ** -W[12]) * ((s + 1) ** W[13] - 1) * math.exp(W[14] * (1 - r))


def _short_term_stability(s: float, rating: int) -> float:
    return s * math.exp(W[17] * (rating - 3 + W[18]))


def review(card: Card, rating: int, now: Optional[float] = None) -> tuple[Card, int]:
    """
    Apply a review rating to a card. Returns (updated_card, scheduled_seconds).
    scheduled_seconds is seconds until next review (use for due_at calculation).
    """
    if now is None:
        now = datetime.now(timezone.utc).timestamp()

    c = Card(
        stability      = card.stability,
        difficulty     = card.difficulty,
        elapsed_days   = card.elapsed_days,
        scheduled_days = card.scheduled_days,
        reps           = card.reps,
        lapses         = card.lapses,
        state          = card.state,
        due_at         = card.due_at,
        last_review    = now,
    )

    elapsed = (now - card.last_review) / 86400.0 if card.last_review else 0.0
    c.elapsed_days = elapsed

    if card.state == NEW:
        c.stability   = _init_stability(rating)
        c.difficulty  = _init_difficulty(rating)
        c.reps        = 1

        if rating == AGAIN:
            c.state = LEARNING
            scheduled_secs = LEARNING_STEPS[0]
        elif rating == HARD:
            c.state = LEARNING
            scheduled_secs = LEARNING_STEPS[0]
        elif rating == GOOD:
            c.state = LEARNING
            scheduled_secs = LEARNING_STEPS[-1]
        else:  # EASY
            c.state = REVIEW
            interval = _next_interval(c.stability)
            c.scheduled_days = interval
            scheduled_secs = interval * 86400

    elif card.state == LEARNING or card.state == RELEARNING:
        steps = LEARNING_STEPS if card.state == LEARNING else RELEARNING_STEPS
        c.reps += 1

        if rating == AGAIN:
            c.state = card.state
            c.stability = _short_term_stability(card.stability, rating)
            scheduled_secs = steps[0]
        elif rating == EASY:
            c.state = REVIEW
            c.stability = _short_term_stability(card.stability, rating)
            interval = _next_interval(c.stability)
            c.scheduled_days = interval
            scheduled_secs = interval * 86400
        else:  # HARD or GOOD
            c.stability = _short_term_stability(card.stability, rating)
            # Graduate if we've been through all steps
            if c.reps >= len(steps):
                c.state = REVIEW
                interval = _next_interval(c.stability)
                c.scheduled_days = interval
                scheduled_secs = interval * 86400
            else:
                scheduled_secs = steps[min(c.reps, len(steps) - 1)]

    else:  # REVIEW
        r = _retrievability(elapsed, card.stability)
        c.reps += 1

        if rating == AGAIN:
            c.lapses += 1
            c.state = RELEARNING
            c.stability = _forget_stability(card.difficulty, card.stability, r)
            c.difficulty = _next_difficulty(card.difficulty, rating)
            scheduled_secs = RELEARNING_STEPS[0]
        else:
            c.state = REVIEW
            c.stability = _recall_stability(card.difficulty, card.stability, r, rating)
            c.difficulty = _next_difficulty(card.difficulty, rating)
            interval = _next_interval(c.stability)
            c.scheduled_days = interval
            scheduled_secs = interval * 86400

    c.due_at = int(now + scheduled_secs)
    return c, scheduled_secs
