"""
LangLab PandR — badge definitions and XP constants.
No imports from db.py; safe to import anywhere.
"""

# ── Badge definitions ─────────────────────────────────────────────────────────
# key:   stable identifier used in achievements table
# group: used to organise the badge grid in the UI

BADGE_DEFS = [
    # First steps
    {'key': 'first_review',   'name': 'First Step',         'desc': 'Completed your first flashcard review',             'icon': '👣', 'group': 'first_steps'},
    {'key': 'first_lesson',   'name': 'First Lesson',       'desc': 'Completed your first lesson',                       'icon': '🎧', 'group': 'first_steps'},
    {'key': 'first_tutor',    'name': 'First Conversation', 'desc': 'Had your first tutor session',                      'icon': '💬', 'group': 'first_steps'},
    {'key': 'first_ai',       'name': 'First AI Lesson',    'desc': 'Completed your first AI-generated lesson',          'icon': '🤖', 'group': 'first_steps'},

    # Streak milestones
    {'key': 'streak_3',   'name': '3-Day Streak',  'desc': 'Studied 3 days in a row',    'icon': '🔥', 'group': 'streaks'},
    {'key': 'streak_7',   'name': 'Week Warrior',  'desc': 'Studied 7 days in a row',    'icon': '🔥', 'group': 'streaks'},
    {'key': 'streak_14',  'name': 'Fortnight',     'desc': 'Studied 14 days in a row',   'icon': '🔥', 'group': 'streaks'},
    {'key': 'streak_30',  'name': 'Month Strong',  'desc': 'Studied 30 days in a row',   'icon': '🔥', 'group': 'streaks'},
    {'key': 'streak_60',  'name': 'Two Months',    'desc': 'Studied 60 days in a row',   'icon': '⭐', 'group': 'streaks'},
    {'key': 'streak_100', 'name': 'Century',       'desc': 'Studied 100 days in a row',  'icon': '💯', 'group': 'streaks'},

    # New Game+ — streak chapters
    {'key': 'new_chapter',    'name': 'New Chapter',   'desc': 'Started a new streak after a break — every chapter counts', 'icon': '📖', 'group': 'chapters'},
    {'key': 'surpassed_best', 'name': 'New Best',      'desc': 'Current streak surpassed your previous personal best',      'icon': '🏅', 'group': 'chapters'},
    {'key': 'comeback',       'name': 'Welcome Back',  'desc': 'Returned after 7+ days away — starting fresh',              'icon': '🌱', 'group': 'chapters'},

    # Lifetime days (never resets)
    {'key': 'days_7',   'name': '7 Days',   'desc': '7 total days of study',   'icon': '📅', 'group': 'lifetime'},
    {'key': 'days_30',  'name': '30 Days',  'desc': '30 total days of study',  'icon': '📅', 'group': 'lifetime'},
    {'key': 'days_100', 'name': '100 Days', 'desc': '100 total days of study', 'icon': '📅', 'group': 'lifetime'},
    {'key': 'days_365', 'name': 'Year',     'desc': '365 total days of study', 'icon': '🎓', 'group': 'lifetime'},

    # Review volume
    {'key': 'reviews_10',   'name': 'First Ten',        'desc': '10 flashcard reviews',   'icon': '📇', 'group': 'volume'},
    {'key': 'reviews_50',   'name': 'Fifty',            'desc': '50 flashcard reviews',   'icon': '📇', 'group': 'volume'},
    {'key': 'reviews_100',  'name': 'Century of Cards', 'desc': '100 flashcard reviews',  'icon': '📇', 'group': 'volume'},
    {'key': 'reviews_500',  'name': 'Five Hundred',     'desc': '500 flashcard reviews',  'icon': '📇', 'group': 'volume'},
    {'key': 'reviews_1000', 'name': 'Thousand',         'desc': '1000 flashcard reviews', 'icon': '🏆', 'group': 'volume'},

    # Mastery — "known cold": state=2, stability≥21 days, reps≥3
    {'key': 'mastered_10',  'name': '10 Known Cold',  'desc': '10 words truly mastered',   'icon': '✨', 'group': 'mastery'},
    {'key': 'mastered_50',  'name': '50 Known Cold',  'desc': '50 words truly mastered',   'icon': '✨', 'group': 'mastery'},
    {'key': 'mastered_100', 'name': '100 Known Cold', 'desc': '100 words truly mastered',  'icon': '✨', 'group': 'mastery'},
    {'key': 'mastered_500', 'name': '500 Known Cold', 'desc': '500 words truly mastered',  'icon': '💎', 'group': 'mastery'},

    # Multi-modal
    {'key': 'multimodal', 'name': 'Polymath', 'desc': 'Used all 5 study types in one week', 'icon': '🎭', 'group': 'exploration'},
]

BADGE_BY_KEY = {b['key']: b for b in BADGE_DEFS}

# Badge groups for display ordering
BADGE_GROUPS = ['first_steps', 'streaks', 'chapters', 'lifetime', 'volume', 'mastery', 'exploration']
GROUP_LABELS  = {
    'first_steps': 'First Steps',
    'streaks':     'Streaks',
    'chapters':    'Streak Chapters',
    'lifetime':    'Total Days',
    'volume':      'Reviews',
    'mastery':     'Mastery',
    'exploration': 'Exploration',
}

# ── XP constants ─────────────────────────────────────────────────────────────

XP_REVIEW = {1: 50, 2: 75, 3: 100, 4: 150}  # keyed by FSRS rating (Again/Hard/Good/Easy)

XP_MASTERED_BASE = 200
XP_MASTERED_RARITY = {'niche': 200, 'interesting': 500, 'essential': 1000, 'fundamental': 2500}

XP_SESSION = {
    'pimsleur':   500,
    'flashcard':  100,
    'ai_lesson':  750,
    'tutor':      1000,
    'free':       300,
}

XP_DAILY_GOAL     = 500
XP_STREAK_BONUS   = {7: 2500, 30: 5000, 100: 10000}
