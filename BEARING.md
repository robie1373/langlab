# Bearing Delegation — langlab
_The Bearing communicates with this project through this file._
_Last updated: 2026-04-11_

---

## Pending

- [ ] —

## In Progress

- [ ] NixOS deployment — mobile UI fixes and LANGLAB_DATA_DIR env var landed (2026-04-11). DEPLOY_TODO.md has the remaining steps.

## Completed

- [x] Phase 1 — server, SQLite + FSRS v5, VTT player SPA, Docker deploy (2026-04-10)
- [x] Phase 2 — flashcards, AI lessons (Gemini), conversational tutor with voice I/O, vocab browser, Anki .apkg import, progress view. 134/134 tests green. (2026-04-11)
- [x] Mobile UI fixes + LANGLAB_DATA_DIR env var (2026-04-11)

## Notes to The Bearing

---

## Context

**Relationship to ~/languages/:**
LangLab is on the path to replacing ~/languages/ functionality. The full meta migration (study logs, Pimsleur content, tooling) is deferred — ~/languages/ remains the source of truth for now. Specifically:
- `~/languages/study-robie.log` — still the authoritative Korean session log; The Bearing reads this for streak/stats
- `~/languages/korean/pimsleur/unit-1/` — Pimsleur VTT + MP3 source files; LangLab ingests from here
- Migration will happen incrementally as LangLab matures

**Users:** Robie (Korean) + Anna (Spanish)
**Stack:** Python stdlib HTTP server, SQLite, FSRS v5, vanilla JS SPA, Gemini API (AI lessons + tutor)
**Deploy target:** homeLab (NixOS service, LANGLAB_DATA_DIR points to persistent data volume)
