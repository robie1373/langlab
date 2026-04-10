#!/usr/bin/env python3
"""
Ingest Pimsleur VTT + MP3 files into the LangLab database.

For each lesson:
  1. Parse the VTT into timestamped entries (Korean lines, English lines)
  2. Extract an audio clip per Korean utterance via ffmpeg
  3. Upsert words into the DB, create a lesson-deck
  4. Populate the lessons table for the player

Ambiguous Korean/English pairings are written to a QC log for phase-2 review.

Usage:
  python3 scripts/ingest_vtt.py \\
    --lang korean \\
    --unit-dir /home/robie/languages/korean/pimsleur/unit-1 \\
    --db /home/robie/proj/langlab/data/study.db \\
    --user robie

  # Dry run (no DB writes, no ffmpeg):
  python3 scripts/ingest_vtt.py --dry-run ...
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Add project root to path for db import
sys.path.insert(0, str(Path(__file__).parent.parent))
from db import Database

# ── VTT parsing ───────────────────────────────────────────────────────────────

KOREAN_RE = re.compile(r'[\uAC00-\uD7AF\u1100-\u11FF\u3130-\u318F]')
TIMECODE_RE = re.compile(
    r'(\d{1,2}):(\d{2}):(\d{2})\.(\d+)\s*-->\s*'
    r'(\d{1,2}):(\d{2}):(\d{2})\.(\d+)'
    r'|'
    r'(\d{1,2}):(\d{2})\.(\d+)\s*-->\s*'
    r'(\d{1,2}):(\d{2})\.(\d+)'
)


@dataclass
class Entry:
    start:  float
    end:    float
    lines:  list[str] = field(default_factory=list)
    korean: list[str] = field(default_factory=list)


def _tc_to_secs(parts: tuple) -> float:
    """Convert (h, m, s, ms_str) or (m, s, ms_str) to float seconds."""
    if len(parts) == 4:
        h, m, s, ms = parts
        return int(h)*3600 + int(m)*60 + int(s) + int(ms) / (10 ** len(ms))
    else:
        m, s, ms = parts
        return int(m)*60 + int(s) + int(ms) / (10 ** len(ms))


def parse_vtt(path: Path) -> list[Entry]:
    text    = path.read_text(encoding='utf-8')
    entries = []
    blocks  = re.split(r'\n{2,}', text.strip())

    for block in blocks:
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if not lines:
            continue
        # Find the timecode line
        tc_idx = next((i for i, l in enumerate(lines) if TIMECODE_RE.match(l)), None)
        if tc_idx is None:
            continue

        m = TIMECODE_RE.match(lines[tc_idx])
        if m.group(1) is not None:
            # HH:MM:SS.mmm format
            start = _tc_to_secs((m.group(1), m.group(2), m.group(3), m.group(4)))
            end   = _tc_to_secs((m.group(5), m.group(6), m.group(7), m.group(8)))
        else:
            # MM:SS.mmm format
            start = _tc_to_secs((m.group(9),  m.group(10), m.group(11)))
            end   = _tc_to_secs((m.group(12), m.group(13), m.group(14)))

        text_lines = lines[tc_idx + 1:]
        if not text_lines:
            continue

        entry        = Entry(start=start, end=end)
        entry.lines  = text_lines
        entry.korean = [l for l in text_lines if KOREAN_RE.search(l)]
        entries.append(entry)

    return entries


# ── Korean/English pairing ────────────────────────────────────────────────────

@dataclass
class WordCard:
    korean:       str
    translation:  Optional[str]
    start:        float
    end:          float
    source_lesson: str
    ambiguous:    bool = False
    ambiguity_reason: str = ''


def pair_entries(entries: list[Entry], lesson_id: str) -> list[WordCard]:
    """
    For each Korean utterance, find the nearest preceding English-only line
    as its translation candidate.

    Heuristics:
      - Look back up to 3 entries for a pure-English line
      - If none found → ambiguous (no translation)
      - If multiple candidates found → use the closest, flag as ambiguous
      - Very short English lines (< 3 words, likely filler) → skip
    """
    cards = []
    for i, entry in enumerate(entries):
        if not entry.korean:
            continue

        for ko_line in entry.korean:
            # Search backwards for English context
            candidates = []
            for j in range(i - 1, max(i - 4, -1), -1):
                prev = entries[j]
                eng_lines = [l for l in prev.lines if not KOREAN_RE.search(l)]
                for eng in eng_lines:
                    words = eng.split()
                    if len(words) < 3:
                        continue  # skip short filler
                    candidates.append((j, eng))

            if not candidates:
                cards.append(WordCard(
                    korean=ko_line, translation=None,
                    start=entry.start, end=entry.end,
                    source_lesson=lesson_id,
                    ambiguous=True,
                    ambiguity_reason='no_english_context',
                ))
            elif len(candidates) == 1:
                cards.append(WordCard(
                    korean=ko_line, translation=candidates[0][1],
                    start=entry.start, end=entry.end,
                    source_lesson=lesson_id,
                ))
            else:
                # Multiple candidates — use closest, flag it
                closest = candidates[0]  # already sorted nearest-first
                cards.append(WordCard(
                    korean=ko_line, translation=closest[1],
                    start=entry.start, end=entry.end,
                    source_lesson=lesson_id,
                    ambiguous=True,
                    ambiguity_reason=f'multiple_candidates ({len(candidates)})',
                ))

    return cards


# ── audio clip extraction ──────────────────────────────────────────────────────

def extract_clip(mp3_path: Path, start: float, end: float,
                 out_path: Path, dry_run: bool = False) -> bool:
    """Extract [start, end] seconds from mp3_path to out_path using ffmpeg."""
    if dry_run:
        print(f'  [dry-run] ffmpeg clip {start:.2f}–{end:.2f} → {out_path.name}')
        return True

    out_path.parent.mkdir(parents=True, exist_ok=True)
    duration = end - start + 0.1  # small buffer
    result = subprocess.run(
        ['ffmpeg', '-y', '-loglevel', 'error',
         '-i', str(mp3_path),
         '-ss', str(start),
         '-t',  str(duration),
         '-c', 'copy',
         str(out_path)],
        capture_output=True
    )
    if result.returncode != 0:
        print(f'  [warn] ffmpeg failed for {out_path.name}: {result.stderr.decode()[:120]}')
        return False
    return True


# ── main ingestion ─────────────────────────────────────────────────────────────

def slug(text: str) -> str:
    """Make a safe filename fragment from Korean text."""
    # Use hex encoding of UTF-8 bytes for a stable, safe filename
    return text.encode('utf-8').hex()[:32]


def ingest_unit(
    lang:     str,
    unit_dir: Path,
    db:       Database,
    user:     str,
    dry_run:  bool,
    qc_log:   Path,
) -> None:
    clips_base = unit_dir / 'clips'
    qc_entries = []

    # Find all VTT files
    vtt_files = sorted(unit_dir.glob('lesson-*.vtt'))
    if not vtt_files:
        print(f'No VTT files found in {unit_dir}')
        return

    # Resolve user_id (skipped in dry-run)
    user_id = None
    if db is not None:
        users    = db.get_users()
        user_row = next((u for u in users if u['name'] == user), None)
        if not user_row:
            print(f'User "{user}" not found in DB. Available: {[u["name"] for u in users]}')
            sys.exit(1)
        user_id = user_row['id']

    for vtt_path in vtt_files:
        lesson_num = vtt_path.stem  # e.g. 'lesson-01'
        mp3_path   = unit_dir / f'{lesson_num}.mp3'
        unit_name  = unit_dir.name  # e.g. 'unit-1'

        lesson_path  = f'pimsleur/{unit_name}/{lesson_num}'
        lesson_title = lesson_num.replace('-', ' ').title()

        print(f'\n── {lesson_num} ──')

        if not mp3_path.exists():
            print(f'  [warn] No MP3 found: {mp3_path.name}, skipping audio extraction')

        # Parse VTT
        entries = parse_vtt(vtt_path)
        print(f'  {len(entries)} VTT entries')

        # Build lesson entries for the player (same format as the original SPA)
        player_entries = [
            {'start': e.start, 'end': e.end, 'lines': e.lines, 'korean': e.korean}
            for e in entries
        ]

        # Upsert lesson
        mp3_rel = f'{lang}/pimsleur/{unit_name}/{lesson_num}.mp3' if mp3_path.exists() else None
        if not dry_run:
            db.upsert_lesson(lang, lesson_path, lesson_title, mp3_rel, player_entries)

        # Pair Korean utterances with English translations
        cards = pair_entries(entries, lesson_path)
        print(f'  {len(cards)} Korean utterances, '
              f'{sum(1 for c in cards if c.ambiguous)} ambiguous')

        # Create deck for this lesson
        deck_id = None
        if not dry_run:
            deck_name = f'Pimsleur {unit_name.replace("-"," ").title()} {lesson_title}'
            deck_id   = db.ensure_deck(user_id, deck_name, 'lesson')

        # Process each card
        for card in cards:
            # Extract audio clip
            audio_path_rel = None
            if mp3_path.exists() and card.start < card.end:
                clip_name = f'{lesson_num}_{slug(card.korean)}.mp3'
                clip_path = clips_base / lang / 'pimsleur' / unit_name / clip_name
                audio_path_rel = f'{lang}/clips/{lang}/pimsleur/{unit_name}/{clip_name}'
                extract_clip(mp3_path, card.start, card.end, clip_path, dry_run)

            # Upsert word
            if not dry_run:
                word_id = db.upsert_word(
                    language      = lang,
                    word          = card.korean,
                    translation   = card.translation,
                    source        = 'pimsleur',
                    source_lesson = card.source_lesson,
                    audio_path    = audio_path_rel,
                )
                db.ensure_user_vocab(user_id, word_id)
                if deck_id:
                    db.add_word_to_deck(deck_id, word_id)

            # Collect QC entries
            if card.ambiguous:
                qc_entries.append({
                    'lesson':   lesson_path,
                    'korean':   card.korean,
                    'translation': card.translation,
                    'reason':   card.ambiguity_reason,
                    'start':    card.start,
                    'end':      card.end,
                })

    # Write QC log
    if qc_entries:
        print(f'\n── QC log: {len(qc_entries)} entries → {qc_log}')
        if not dry_run:
            qc_log.parent.mkdir(parents=True, exist_ok=True)
            qc_log.write_text(
                json.dumps(qc_entries, ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
    else:
        print('\n── No ambiguous pairings — clean ingest')


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description='Ingest Pimsleur VTT+MP3 into LangLab DB')
    p.add_argument('--lang',     default='korean', help='Language code (default: korean)')
    p.add_argument('--unit-dir', required=True,    help='Path to unit directory (contains VTTs + MP3s)')
    p.add_argument('--db',       required=True,    help='Path to study.db')
    p.add_argument('--user',     default='robie',  help='Username to associate vocab with (default: robie)')
    p.add_argument('--dry-run',  action='store_true', help='Parse and report without writing to DB or disk')
    p.add_argument('--qc-log',   default=None,     help='Path for QC log JSON (default: <unit-dir>/ingest-qc.json)')
    args = p.parse_args()

    unit_dir = Path(args.unit_dir).expanduser().resolve()
    if not unit_dir.exists():
        print(f'Unit directory not found: {unit_dir}')
        sys.exit(1)

    if not shutil.which('ffmpeg') and not args.dry_run:
        print('ffmpeg not found in PATH — audio clips will be skipped')

    db_path = Path(args.db).expanduser().resolve()
    qc_log  = Path(args.qc_log).expanduser() if args.qc_log else unit_dir / 'ingest-qc.json'

    db = Database(str(db_path)) if not args.dry_run else None

    print(f'Ingesting {args.lang} from {unit_dir}')
    print(f'DB: {db_path}{"  [dry-run, no writes]" if args.dry_run else ""}')

    ingest_unit(
        lang     = args.lang,
        unit_dir = unit_dir,
        db       = db,
        user     = args.user,
        dry_run  = args.dry_run,
        qc_log   = qc_log,
    )

    print('\nDone.')


if __name__ == '__main__':
    main()
