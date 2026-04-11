#!/usr/bin/env python3
"""
Import an Anki deck (.apkg) into the LangLab vocabulary database.

.apkg files are ZIP archives containing a SQLite database (collection.anki2).
Cards are extracted assuming the first field is the target-language word
and the second field is the translation. HTML tags and sound refs are stripped.

Usage:
    python3 scripts/import_apkg.py <deck.apkg> [options]

Options:
    --user USER         LangLab username (default: robie)
    --language LANG     Target language (default: korean)
    --deck-name NAME    Deck name in LangLab (default: apkg filename)
    --dry-run           Preview without writing to DB
    --field-word N      Field index for target word (default: 0)
    --field-trans N     Field index for translation (default: 1)
"""

import argparse
import os
import re
import sqlite3
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from db import Database


# ── field helpers ─────────────────────────────────────────────────────────────

def split_fields(flds: str) -> list[str]:
    """Anki uses ASCII 0x1f (unit separator) to delimit fields."""
    return flds.split('\x1f')


def strip_markup(text: str) -> str:
    """Remove HTML tags and Anki sound/media references."""
    text = re.sub(r'\[sound:[^\]]+\]', '', text)   # [sound:file.mp3]
    text = re.sub(r'\{\{[^}]+\}\}', '', text)       # {{cloze}} deletions
    text = re.sub(r'<[^>]+>', '', text)              # HTML tags
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&') \
               .replace('&lt;', '<').replace('&gt;', '>')
    return text.strip()


# ── import ────────────────────────────────────────────────────────────────────

def import_apkg(
    apkg_path: str,
    db: Database,
    user_id: int,
    language: str,
    deck_name: str,
    dry_run: bool = False,
    field_word: int = 0,
    field_trans: int = 1,
) -> int:
    """Import cards from .apkg. Returns number of cards imported."""

    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(apkg_path, 'r') as z:
            z.extractall(tmpdir)

        # Anki 2.x uses collection.anki2; newer versions may use collection.anki21
        for fname in ('collection.anki21', 'collection.anki2'):
            db_path = os.path.join(tmpdir, fname)
            if os.path.exists(db_path):
                break
        else:
            raise FileNotFoundError(
                'No collection.anki2 or collection.anki21 found in the .apkg file.'
            )

        anki = sqlite3.connect(db_path)
        anki.row_factory = sqlite3.Row

        notes = anki.execute("SELECT flds FROM notes").fetchall()
        anki.close()

    if not notes:
        print('No notes found in deck.')
        return 0

    if dry_run:
        print(f'DRY RUN — would import up to {len(notes)} cards')
        print('First 5 cards:')
        for note in notes[:5]:
            fields = split_fields(note['flds'])
            word  = strip_markup(fields[field_word])  if len(fields) > field_word  else ''
            trans = strip_markup(fields[field_trans]) if len(fields) > field_trans else ''
            print(f'  {repr(word)!s:30s}  →  {repr(trans)}')
        return 0

    deck_id = db.ensure_deck(user_id, deck_name, 'imported')
    imported = 0
    skipped  = 0

    for note in notes:
        fields = split_fields(note['flds'])
        word  = strip_markup(fields[field_word])  if len(fields) > field_word  else ''
        trans = strip_markup(fields[field_trans]) if len(fields) > field_trans else ''

        if not word:
            skipped += 1
            continue

        word_id = db.upsert_word(
            language     = language,
            word         = word,
            translation  = trans or None,
            source       = 'imported',
            source_lesson = deck_name,
            audio_path   = None,
        )
        db.ensure_user_vocab(user_id, word_id)
        db.add_word_to_deck(deck_id, word_id)
        imported += 1

    if skipped:
        print(f'Skipped {skipped} empty cards.')

    return imported


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description='Import Anki deck into LangLab')
    p.add_argument('apkg',           help='Path to .apkg file')
    p.add_argument('--user',         default='robie',  help='LangLab username (default: robie)')
    p.add_argument('--language',     default='korean', help='Target language (default: korean)')
    p.add_argument('--deck-name',    help='Deck name in LangLab (default: apkg filename)')
    p.add_argument('--dry-run',      action='store_true', help='Preview without writing')
    p.add_argument('--field-word',   type=int, default=0, help='Field index for word (default: 0)')
    p.add_argument('--field-trans',  type=int, default=1, help='Field index for translation (default: 1)')
    args = p.parse_args()

    if not os.path.exists(args.apkg):
        print(f'Error: {args.apkg!r} not found', file=sys.stderr)
        sys.exit(1)

    deck_name = args.deck_name or Path(args.apkg).stem

    data_dir = Path(__file__).parent.parent / 'data'
    db = Database(str(data_dir / 'study.db'))

    users = db.get_users()
    user  = next((u for u in users if u['name'] == args.user), None)
    if not user:
        names = [u['name'] for u in users]
        print(f'Error: user {args.user!r} not found. Available: {names}', file=sys.stderr)
        sys.exit(1)

    print(f'Importing {Path(args.apkg).name!r} → deck "{deck_name}" '
          f'for {user["display_name"]} ({args.language})')

    try:
        n = import_apkg(
            apkg_path  = args.apkg,
            db         = db,
            user_id    = user['id'],
            language   = args.language,
            deck_name  = deck_name,
            dry_run    = args.dry_run,
            field_word = args.field_word,
            field_trans = args.field_trans,
        )
        if not args.dry_run:
            print(f'Done — {n} cards imported.')
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
