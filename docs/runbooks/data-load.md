# Runbook: Data Load

How to load Pimsleur lessons and Anki vocabulary decks into LangLab.

---

## Option A: Web UI (single lesson or small batches)

1. Start the server (`python3 server.py`)
2. Open `http://localhost:8080`, select a user, navigate to ⚙ (Admin/Library tab)
3. **Vocab section:** drop a `.apkg` file, set language and deck name, click **Import Vocab**
4. **Audio Library section:** drop VTT + MP3 files, set unit name, click **Ingest Lessons**

Web UI is suitable for one-off additions. For bulk loads (full units), use the CLI.

---

## Option B: CLI (bulk / full units)

### Pimsleur VTT + MP3 ingest

```bash
cd ~/proj/langlab

python3 scripts/ingest_vtt.py \
  --lang korean \
  --unit-dir ~/languages/korean/pimsleur/unit-1 \
  --db data/study.db \
  --user robie
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--lang` | `korean` | Language code |
| `--unit-dir` | required | Directory containing VTT + MP3 files |
| `--db` | required | Path to `study.db` |
| `--user` | `robie` | Username to associate vocab with |
| `--dry-run` | off | Parse and report without writing |
| `--qc-log` | `<unit-dir>/ingest-qc.json` | Path for QC log |

**What it does:**
1. Parses each `lesson-*.vtt` in `--unit-dir`
2. Extracts word audio clips via ffmpeg into `<unit-dir>/clips/korean/pimsleur/<unit>/`
3. Upserts lessons and words into the DB
4. Creates a deck per lesson and associates vocab with the user

**ffmpeg note:** Not on PATH in the Nix dev environment. The script detects and
uses the Nix store ffmpeg automatically. Audio clips will be silently skipped
if ffmpeg is not found.

**QC log:** Ambiguous Korean/English pairings (no clear translation found) are
written to `ingest-qc.json`. Roughly 50% of utterances in Pimsleur VTTs are
ambiguous — this is expected.

---

### Anki `.apkg` vocab import

```bash
cd ~/proj/langlab

python3 scripts/import_apkg.py \
  ~/languages/flashcard-archive/TTMIKs_First_500_Korean_Words_by_Retro_picturesaudio.apkg \
  --user robie \
  --language korean \
  --deck-name "TTMIK First 500 Korean Words"
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--user` | required | Username |
| `--language` | required | Language code |
| `--deck-name` | required | Name for the deck in LangLab |
| `--db` | `data/study.db` | Path to DB |
| `--field-word` | `0` | Field index for the word |
| `--field-trans` | `1` | Field index for the translation |
| `--dry-run` | off | Report without writing |

---

## Current data state (as of 2026-04-12)

| Content | Status |
|---------|--------|
| Pimsleur Unit 1 (18 lessons) | Loaded — robie/korean |
| TTMIK First 500 Korean Words | Loaded — robie/korean |
| Anna's Spanish | Not loaded (library CDs pending) |

---

## Audio file symlinks (dev machine only)

The CLI ingest script writes audio clips into the source tree
(`~/languages/korean/pimsleur/unit-1/clips/`), not into the LangLab data dir.
Two symlinks bridge them:

```bash
# Already created — documented here for reference
ln -s ~/languages/korean/pimsleur/unit-1/clips \
      ~/proj/langlab/data/languages/korean/clips

ln -s ~/languages/korean/pimsleur \
      ~/proj/langlab/data/languages/korean/pimsleur
```

These are dev-machine-specific. The homelab deployment uses `LANGLAB_DATA_DIR`
pointing to a proper data volume where everything lives in the right place.
