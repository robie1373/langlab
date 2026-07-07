# Spec 05 — Progress Polish: Streak Chronicle, CEFR Estimate, Leaderboard, Login Visual

_Fable 5, 2026-07-06. Four small independent items — commit each separately, in
this order. Items 1–2 are for both users; item 3 renders for Anna only; item 4
is cosmetic and last._

## 1. Streak Chronicle ("trophy shelf")

The DB already stores completed streak runs (`streak_chapters`,
`db.get_streak_chapters` — exists, currently unrouted).

- **Route:** `GET /api/streak-chapters/<user_id>` → list, newest first:
  `{start_date, end_date, length, was_best}`.
- **UI (progress view):** a horizontal shelf row under the heatmap titled
  **Chapters**. Each chapter is a small card: `length`-day count large, date
  range small, 🏅 corner mark when `was_best`. The **current** streak renders as
  the first card, visually distinct (live/glowing), labeled "Current".
- **Framing (hard rule):** New Game+ language only. A finished chapter is a
  completed run, never a "broken" or "lost" streak. Copy: "Chapter N — X days".
  The words "broke", "lost", "failed" must not appear.
- Empty state: hide the shelf entirely (no nag copy).

## 2. CEFR estimate — Phase A only

Aspirational estimated level from real counts. **Phase B (Gemini-simulated
mastery test earning a permanent `cefr_designations` badge) is explicitly out of
scope — do not build it now.** The table exists; leave it untouched.

- **Definitions:** `mastered` = the standing mastery rule (state 2, stability
  ≥ 21, reps ≥ 3); `sessions` = lifetime session count.
- **Thresholds (working toward the *next* level):**

| Estimate shown | Requires |
|---|---|
| "Working toward A1" | below A1 line |
| "Estimated A1 — working toward A2" | ≥150 mastered AND ≥10 sessions |
| "Estimated A2 — working toward B1" | ≥500 mastered AND ≥40 sessions |
| "Estimated B1 — working toward B2" | ≥1500 mastered AND ≥120 sessions |
| "Estimated B2" | ≥3000 mastered AND ≥250 sessions |

- **Route:** `GET /api/cefr/<user_id>` →
  `{"estimate": "A1", "next": "A2", "mastered": N, "sessions": M,
    "next_needs": {"mastered": 500, "sessions": 40}}`
  (`estimate: null` below the A1 line).
- **UI (progress view):** a chip near the streak numbers: the estimate string
  plus a thin progress bar toward the next level (fraction = min of the two
  ratios). Always aspirational framing; never "you are only".

## 3. Leaderboard — Anna's UI only

Weekly XP, Anna vs. Robie. Opt-in via the existing `user_goals.show_leaderboard`.

- **Route:** `GET /api/leaderboard` → both users' XP summed over the current
  ISO week (`xp_events` where `date(timestamp,'localtime')` within Mon–Sun of
  the current local week): `[{user_id, display_name, xp}]` sorted desc.
- **UI:** in the progress view, render a two-row weekly XP panel **only when the
  current user's `show_leaderboard == 1`** (comes back in `GET /api/goals`).
  Robie's flag stays 0 — **his UI must never show it**; there is no toggle in the
  UI for him. Enable for Anna by a one-time manual
  `POST /api/goals/2 {"show_leaderboard": 1}` (note this in the ship report;
  don't seed it in code).
- No notifications, no taunts — just the two numbers and a 👑 on the leader.

## 4. Login page visual — floating user clouds

Cosmetic redesign of the user picker (`view-picker`, `showPicker` in `main.js`).

- Each user tile becomes a soft floating "cloud" card: Robie = forest green,
  Anna = royal blue (define as CSS variables; respect dark mode).
- Slow idle float animation (CSS keyframes, translate ±6px, ~8s ease-in-out
  loop, offset phases).
- Background: a sparse parallax drift of PandR glyphs (badge emoji, `+XP`
  numerals) — pure CSS animation on absolutely-positioned spans, ~10 elements,
  very low opacity. Two drift speeds for cheap parallax depth.
- **`@media (prefers-reduced-motion: reduce)`: all animation off.**
- No JS beyond emitting the static elements at render; no layout shift of the
  actual buttons; click behavior unchanged.

## Tests

Unit: streak-chapters route shape; CEFR thresholds (exact boundary cases: 149/150
mastered, 9/10 sessions); leaderboard week windowing (an xp_event last Sunday
23:59 local vs. this Monday 00:01) and sort order.

E2E: chapters shelf renders with seeded chapters; CEFR chip renders; leaderboard
absent for Robie (flag 0) and present when a test user's flag is 1; picker still
navigates (reduced-motion not testable — skip).

## Acceptance criteria

- [ ] Chronicle shows seeded chapters + live current chapter; zero negative copy.
- [ ] CEFR chip matches the threshold table exactly at boundaries.
- [ ] Leaderboard invisible at `show_leaderboard=0` (default; Robie), visible at 1.
- [ ] Picker animates, respects reduced-motion, behavior unchanged.
- [ ] Four separate commits; suite green; docs updated.
