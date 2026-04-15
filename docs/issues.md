# LangLab Issues

Drop problems and feature requests here. These are picked up in future work sessions.

---

## Open

<!-- format: - [ ] **Title** — description. _Added: YYYY-MM-DD_ -->

- [ ] **manual session logging** - The user needs a tool to log a session by hand if they did it while away from langlab. I'd like a drop down of session types plus other. Make as much of it optional with sensible defaults as possible. a manually logged session should have the same value as an automatically logged session WRT streaks, badges, statistics etc... _Added: 2026-04-12_

- [x] **Flashcard end session** - "End" button + Escape key during review; shows partial results if any cards rated, returns to queue screen otherwise. _Closed: 2026-04-12_

- [x] **Flashcards appear to be presented in order** - Due cards sorted by due_at ASC (most overdue first); new cards (due_at IS NULL) randomised via SQLite RANDOM(). _Closed: 2026-04-12_

- [ ] **Flashcard deck management + session configuration — major rethink** — The current queue screen is too naive. Needs full redesign: deck list with per-deck status (new/learning/review counts, word count, source), ability to enable/disable individual decks for a session, session configuration (new cards per session cap, review-only mode), and possibly study modes (e.g. cram, due-only, new-only). Visual design should match the review screen quality. The review screen itself is good — this is pre-session configuration only. _Added: 2026-04-15_

- [x] **Progress view — streaks and achievements** — Full Progress & Rewards suite: streaks (current/best/lifetime, New Game+ framing), 52-week heat map, 27-badge achievement system (7 groups), XP system (per review/mastery/session/daily goal), card rarity (Fundamental/Essential/Interesting/Niche from frequency data), daily goal ring on flashcard queue, jackpot system (pity-guaranteed ~1 in 3 sessions), real-time toast notifications for badges/XP/mastery. _Closed: 2026-04-12_

- [ ] **Bulk ingest timeout strategy** — 18 lessons × ~300 clips = ~5400 ffmpeg calls. Browser upload times out. Current workaround: use CLI for bulk ingest (`scripts/ingest_vtt.py`), web UI for one-offs. Longer-term options: SSE progress stream, or accept a server-side directory path instead of file upload. _Added: 2026-04-12_

- [ ] **Anna's Spanish content** — No Pimsleur equivalent yet (waiting on library CDs). Language Transfer Complete Spanish suggested as interim source. _Added: 2026-04-12_

- [ ] **Lesson persistence and history** — Generated AI lessons should persist across sessions and accumulate (not be discarded when a new lesson is generated). UI should show a list of past lessons that grows over time; user can select any to review. Needs a `lessons_generated` table (or similar) to store the Gemini JSON per user. Deletion should be explicit (per-lesson trash/delete button). _Added: 2026-04-15_

- [x] **Homelab deployment** — Deployed 2026-04-14 to VMID 111 (192.168.20.11) via nixos-anywhere. Serving at https://langlab.vimba-stairs.ts.net. _Closed: 2026-04-14_

---

## Closed

<!-- format: - [x] **Title** — resolution. _Closed: YYYY-MM-DD_ -->

