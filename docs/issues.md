# LangLab Issues

Drop problems and feature requests here. These are picked up in future work sessions.

---

## Open

<!-- format: - [ ] **Title** — description. _Added: YYYY-MM-DD_ -->

- [ ] **Progress view — streaks and achievements** — Current progress view shows session counts and vocab stats. Needs: study streak (consecutive days), achievements (e.g. "100 words reviewed", "7-day streak", "first lesson complete"). Design: `/api/progress/<user_id>` endpoint + new section in progress.js. _Added: 2026-04-12_

- [ ] **Bulk ingest timeout strategy** — 18 lessons × ~300 clips = ~5400 ffmpeg calls. Browser upload times out. Current workaround: use CLI for bulk ingest (`scripts/ingest_vtt.py`), web UI for one-offs. Longer-term options: SSE progress stream, or accept a server-side directory path instead of file upload. _Added: 2026-04-12_

- [ ] **Anna's Spanish content** — No Pimsleur equivalent yet (waiting on library CDs). Language Transfer Complete Spanish suggested as interim source. _Added: 2026-04-12_

- [ ] **Homelab deployment** — NixOS service module, disko, secrets all ready in nixos-config. Blocked on: (1) "LangLab env" 1Password item with GEMINI_API_KEY + CLAUDE_API_KEY, (2) langlab-env.age encryption, (3) flipper access to VLAN 20 for nixos-anywhere. See `DEPLOY_TODO.md`. _Added: 2026-04-12_

---

## Closed

<!-- format: - [x] **Title** — resolution. _Closed: YYYY-MM-DD_ -->

