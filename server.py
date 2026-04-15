#!/usr/bin/env python3
"""LangLab — language learning suite server."""

import email
import json
import logging
import mimetypes
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

logging.basicConfig(
    level=getattr(logging, os.environ.get('LOG_LEVEL', 'INFO').upper(), logging.INFO),
    format='%(levelname)s %(name)s: %(message)s',
)
log = logging.getLogger('langlab')

from db import Database

BASE_DIR     = Path(__file__).parent
FRONTEND_DIR = BASE_DIR / 'frontend'
DATA_DIR     = Path(os.environ.get('LANGLAB_DATA_DIR', str(BASE_DIR / 'data')))

# Security headers added to every response
SECURITY_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options':        'SAMEORIGIN',
    'Referrer-Policy':        'strict-origin-when-cross-origin',
}


# ── VTT parsing utilities (for admin ingest endpoint) ────────────────────────

_KOREAN_RE   = re.compile(r'[\uAC00-\uD7AF\u1100-\u11FF\u3130-\u318F]')
_TIMECODE_RE = re.compile(
    r'(\d{1,2}):(\d{2}):(\d{2})\.(\d+)\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})\.(\d+)'
    r'|(\d{1,2}):(\d{2})\.(\d+)\s*-->\s*(\d{1,2}):(\d{2})\.(\d+)'
)


def _tc_to_secs(parts: tuple) -> float:
    if len(parts) == 4:
        h, m, s, ms = parts
        return int(h)*3600 + int(m)*60 + int(s) + int(ms)/(10**len(ms))
    m, s, ms = parts
    return int(m)*60 + int(s) + int(ms)/(10**len(ms))


def _find_ffmpeg() -> str | None:
    found = shutil.which('ffmpeg')
    if found:
        return found
    import glob
    candidates = glob.glob('/nix/store/*ffmpeg*/bin/ffmpeg')
    return sorted(candidates)[-1] if candidates else None


def _parse_vtt_text(text: str) -> list:
    entries = []
    for block in re.split(r'\n{2,}', text.strip()):
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        tc_idx = next((i for i, l in enumerate(lines) if _TIMECODE_RE.match(l)), None)
        if tc_idx is None:
            continue
        m = _TIMECODE_RE.match(lines[tc_idx])
        if m.group(1) is not None:
            start = _tc_to_secs((m.group(1), m.group(2), m.group(3), m.group(4)))
            end   = _tc_to_secs((m.group(5), m.group(6), m.group(7), m.group(8)))
        else:
            start = _tc_to_secs((m.group(9),  m.group(10), m.group(11)))
            end   = _tc_to_secs((m.group(12), m.group(13), m.group(14)))
        text_lines = lines[tc_idx + 1:]
        if text_lines:
            entries.append({
                'start':  start, 'end': end,
                'lines':  text_lines,
                'korean': [l for l in text_lines if _KOREAN_RE.search(l)],
            })
    return entries


def _pair_korean(entries: list, lesson_path: str) -> list:
    """Pair each Korean utterance with the nearest preceding English line."""
    cards = []
    for i, entry in enumerate(entries):
        for ko_line in entry.get('korean', []):
            trans = None
            for j in range(i - 1, max(i - 4, -1), -1):
                eng = [l for l in entries[j]['lines']
                       if not _KOREAN_RE.search(l) and len(l.split()) >= 3]
                if eng:
                    trans = eng[0]
                    break
            cards.append({'word': ko_line, 'translation': trans,
                          'start': entry['start'], 'end': entry['end']})
    return cards


class LangLabHandler(BaseHTTPRequestHandler):
    db: Database = None  # injected at startup

    def log_message(self, fmt, *args):
        log.debug('%s - - %s', self.address_string(), fmt % args)

    # ── response helpers ────────────────────────────────────────────────────

    def _send_headers(self, status: int, content_type: str, extra: dict = None):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        for k, v in SECURITY_HEADERS.items():
            self.send_header(k, v)
        if extra:
            for k, v in extra.items():
                self.send_header(k, v)
        self.end_headers()

    def _json(self, data, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self._send_headers(status, 'application/json',
                           {'Content-Length': str(len(body))})
        self.wfile.write(body)

    def _err(self, status: int, message: str):
        log.warning('%s %s → %s %s', self.command, self.path, status, message)
        self._json({'error': message}, status)

    def _read_body(self) -> dict:
        length = int(self.headers.get('Content-Length', 0))
        if not length:
            return {}
        return json.loads(self.rfile.read(length))

    # ── routing ─────────────────────────────────────────────────────────────

    def do_GET(self):
        p = urlparse(self.path).path
        if p.startswith('/api/'):
            self._api_get(p)
        elif p.startswith('/audio/'):
            self._serve_audio(p)
        else:
            self._serve_static(p)

    def do_POST(self):
        p = urlparse(self.path).path
        if p.startswith('/api/'):
            self._api_post(p)
        else:
            self._err(404, 'Not found')

    # ── GET API ─────────────────────────────────────────────────────────────

    def _api_get(self, path: str):
        if path == '/api/users':
            self._json(self.db.get_users())

        elif path == '/api/config':
            self._json({
                'gemini_api_key': os.environ.get('GEMINI_API_KEY', ''),
                'claude_api_key': os.environ.get('CLAUDE_API_KEY', ''),
            })

        elif m := re.match(r'^/api/lessons/([^/]+)/(.+)$', path):
            lang, lesson_path = m.groups()
            data = self.db.get_lesson_data(lang, lesson_path)
            if data is None:
                self._err(404, 'Lesson not found')
            else:
                self._json(data)

        elif m := re.match(r'^/api/lessons/([^/]+)$', path):
            self._json(self.db.get_lesson_list(m.group(1)))

        elif m := re.match(r'^/api/vocab/(\d+)$', path):
            self._json(self.db.get_user_vocab(int(m.group(1))))

        elif m := re.match(r'^/api/sessions/(\d+)$', path):
            self._json(self.db.get_sessions(int(m.group(1))))

        elif m := re.match(r'^/api/flashcards/due/(\d+)$', path):
            self._json(self.db.get_due_cards(int(m.group(1))))

        elif path == '/api/admin/library':
            self._json(self.db.get_library_stats())

        elif m := re.match(r'^/api/progress/(\d+)$', path):
            self._json(self.db.get_progress(int(m.group(1))))

        elif m := re.match(r'^/api/achievements/(\d+)$', path):
            from achievements import BADGE_DEFS, BADGE_BY_KEY, BADGE_GROUPS, GROUP_LABELS
            earned = {r['badge_key'] for r in self.db.get_achievements(int(m.group(1)))}
            self._json({
                'earned':       list(earned),
                'badge_defs':   BADGE_DEFS,
                'badge_groups': BADGE_GROUPS,
                'group_labels': GROUP_LABELS,
            })

        elif m := re.match(r'^/api/goals/(\d+)$', path):
            self._json(self.db.get_goal(int(m.group(1))))

        else:
            self._err(404, 'Unknown endpoint')

    # ── POST API ────────────────────────────────────────────────────────────

    def _api_post(self, path: str):
        # Admin endpoints use multipart — don't pre-read the body as JSON
        if path.startswith('/api/admin/'):
            if path == '/api/admin/import-apkg':
                self._handle_import_apkg()
            elif path == '/api/admin/ingest-vtt':
                self._handle_ingest_vtt()
            else:
                self._err(404, 'Unknown endpoint')
            return

        body = self._read_body()

        if path == '/api/sessions':
            result = self.db.log_session(body)
            self._json(result)

        elif path == '/api/vocab/rate':
            self._json(self.db.rate_word(body))

        elif path == '/api/flashcards/review':
            self._json(self.db.review_card(body))

        elif m := re.match(r'^/api/achievements/check/(\d+)$', path):
            newly_earned = self.db.check_and_award(int(m.group(1)))
            self._json({'awarded': newly_earned})

        elif m := re.match(r'^/api/goals/(\d+)$', path):
            self._json(self.db.set_goal(
                int(m.group(1)),
                int(body.get('daily_cards', 20)),
                body.get('show_leaderboard'),
            ))

        elif m := re.match(r'^/api/admin/backfill-rarity/([^/]+)$', path):
            count = self.db.backfill_rarity(m.group(1))
            self._json({'updated': count})

        else:
            self._err(404, 'Unknown endpoint')

    # ── admin: multipart helpers ─────────────────────────────────────────────

    def _parse_multipart(self) -> dict:
        ct     = self.headers.get('Content-Type', '')
        length = int(self.headers.get('Content-Length', 0))
        body   = self.rfile.read(length)
        raw    = ('Content-Type: ' + ct + '\r\nMIME-Version: 1.0\r\n\r\n').encode() + body
        msg    = email.message_from_bytes(raw)
        result: dict = {}
        for part in msg.walk():
            if part.get_content_maintype() == 'multipart':
                continue
            name     = part.get_param('name',     header='content-disposition')
            filename = part.get_param('filename', header='content-disposition')
            if not name:
                continue
            data  = part.get_payload(decode=True) or b''
            entry = {'filename': filename, 'data': data} if filename \
                    else data.decode('utf-8', errors='replace')
            if name in result:
                if not isinstance(result[name], list):
                    result[name] = [result[name]]
                result[name].append(entry)
            else:
                result[name] = entry
        return result

    def _handle_import_apkg(self):
        try:
            parts     = self._parse_multipart()
            user_id   = int(parts.get('user_id', 0))
            language  = parts.get('language', 'korean')
            dn_field  = parts.get('deck_name', '')
            file_part = parts.get('file')
            if not file_part or not user_id:
                return self._err(400, 'Missing user_id or file')
            deck_name = (dn_field.strip() if isinstance(dn_field, str) else '') \
                        or Path(file_part['filename']).stem
            with tempfile.NamedTemporaryFile(suffix='.apkg', delete=False) as f:
                f.write(file_part['data'])
                tmp = f.name
            try:
                result = self._run_apkg_import(tmp, user_id, language, deck_name)
            finally:
                os.unlink(tmp)
            self._json(result)
        except Exception as e:
            self._err(500, str(e))

    def _run_apkg_import(self, apkg_path: str, user_id: int,
                         language: str, deck_name: str) -> dict:
        import sqlite3 as _sq
        with tempfile.TemporaryDirectory() as tmpdir:
            with zipfile.ZipFile(apkg_path) as z:
                z.extractall(tmpdir)
            db_file = next(
                (os.path.join(tmpdir, n)
                 for n in ('collection.anki21', 'collection.anki2')
                 if os.path.exists(os.path.join(tmpdir, n))),
                None,
            )
            if not db_file:
                raise ValueError('No Anki collection found in .apkg')
            anki  = _sq.connect(db_file)
            anki.row_factory = _sq.Row
            notes = anki.execute('SELECT flds FROM notes').fetchall()
            anki.close()

        def _clean(t: str) -> str:
            t = re.sub(r'\[sound:[^\]]+\]', '', t)
            t = re.sub(r'<[^>]+>', '', t)
            return t.replace('&nbsp;', ' ').strip()

        deck_id  = self.db.ensure_deck(user_id, deck_name, 'imported')
        imported = skipped = 0
        for note in notes:
            fields = note['flds'].split('\x1f')
            word  = _clean(fields[0]) if fields else ''
            trans = _clean(fields[1]) if len(fields) > 1 else ''
            if not word:
                skipped += 1
                continue
            wid = self.db.upsert_word(language, word, trans or None,
                                      'imported', deck_name, None)
            self.db.ensure_user_vocab(user_id, wid)
            self.db.add_word_to_deck(deck_id, wid)
            imported += 1
        return {'imported': imported, 'skipped': skipped, 'deck': deck_name}

    def _handle_ingest_vtt(self):
        try:
            parts     = self._parse_multipart()
            language  = parts.get('language', 'korean')
            user_id   = int(parts.get('user_id', 0))
            unit_name = (parts.get('unit_name') or 'unit-1').strip() or 'unit-1'

            files = parts.get('files', [])
            if isinstance(files, dict):
                files = [files]
            if not isinstance(files, list):
                files = []

            vtts = {Path(f['filename']).stem: f
                    for f in files if f['filename'].lower().endswith('.vtt')}
            mp3s = {Path(f['filename']).stem: f
                    for f in files if f['filename'].lower().endswith('.mp3')}

            if not vtts:
                return self._err(400, 'No VTT files provided')

            ffmpeg_bin    = _find_ffmpeg()
            have_ffmpeg   = ffmpeg_bin is not None
            lessons_added = words_added = clips_made = 0

            for stem, vtt_file in sorted(vtts.items()):
                lesson_path = f'pimsleur/{unit_name}/{stem}'
                text        = vtt_file['data'].decode('utf-8', errors='replace')
                entries     = _parse_vtt_text(text)

                # Save MP3 to canonical location
                mp3_rel      = None
                mp3_full     = None
                if stem in mp3s:
                    mp3_dir  = DATA_DIR / 'languages' / language / 'pimsleur' / unit_name
                    mp3_dir.mkdir(parents=True, exist_ok=True)
                    mp3_full = mp3_dir / f'{stem}.mp3'
                    mp3_full.write_bytes(mp3s[stem]['data'])
                    mp3_rel  = f'{language}/pimsleur/{unit_name}/{stem}.mp3'

                self.db.upsert_lesson(language, lesson_path, stem, mp3_rel, entries)
                lessons_added += 1

                if user_id:
                    cards    = _pair_korean(entries, lesson_path)
                    unit_lbl = unit_name.replace('-', ' ').title()
                    stem_lbl = stem.replace('-', ' ').title()
                    deck_id  = self.db.ensure_deck(
                        user_id, f'Pimsleur {unit_lbl} {stem_lbl}', 'lesson'
                    )

                    for card in cards:
                        audio_rel = None
                        if mp3_full and mp3_full.exists() and have_ffmpeg \
                                and card['end'] > card['start']:
                            clip_name = (f"{stem}_"
                                         f"{card['word'].encode('utf-8').hex()[:32]}.mp3")
                            clip_dir  = (DATA_DIR / 'languages' / language
                                         / 'clips' / language / 'pimsleur' / unit_name)
                            clip_dir.mkdir(parents=True, exist_ok=True)
                            r = subprocess.run(
                                [ffmpeg_bin, '-y', '-loglevel', 'error',
                                 '-i', str(mp3_full),
                                 '-ss', str(card['start']),
                                 '-t',  str(card['end'] - card['start'] + 0.1),
                                 '-c', 'copy', str(clip_dir / clip_name)],
                                capture_output=True,
                            )
                            if r.returncode == 0:
                                audio_rel = (f'{language}/clips/{language}'
                                             f'/pimsleur/{unit_name}/{clip_name}')
                                clips_made += 1

                        wid = self.db.upsert_word(
                            language, card['word'], card['translation'],
                            'pimsleur', lesson_path, audio_rel,
                        )
                        self.db.ensure_user_vocab(user_id, wid)
                        self.db.add_word_to_deck(deck_id, wid)
                        words_added += 1

            self._json({
                'lessons': lessons_added,
                'words':   words_added,
                'clips':   clips_made,
                'ffmpeg':  have_ffmpeg,
            })
        except Exception as e:
            self._err(500, str(e))

    # ── audio serving (with range request support for seeking) ──────────────

    def _serve_audio(self, url_path: str):
        rel = url_path[len('/audio/'):]
        file_path = DATA_DIR / 'languages' / rel
        if not file_path.exists() or not file_path.is_file():
            self._err(404, 'Audio not found')
            return
        self._serve_file(file_path)

    # ── static file serving ─────────────────────────────────────────────────

    def _serve_static(self, url_path: str):
        if url_path == '/':
            url_path = '/index.html'
        file_path = FRONTEND_DIR / url_path.lstrip('/')
        # SPA fallback — unknown paths serve index.html
        if not file_path.exists() or not file_path.is_file():
            file_path = FRONTEND_DIR / 'index.html'
        self._serve_file(file_path)

    def _serve_file(self, file_path: Path):
        size = file_path.stat().st_size
        mime, _ = mimetypes.guess_type(str(file_path))
        mime = mime or 'application/octet-stream'

        range_header = self.headers.get('Range', '')
        if range_header:
            m = re.match(r'bytes=(\d*)-(\d*)', range_header)
            start = int(m.group(1)) if m.group(1) else 0
            end   = int(m.group(2)) if m.group(2) else size - 1
            end   = min(end, size - 1)
            length = end - start + 1
            self._send_headers(206, mime, {
                'Content-Length':  str(length),
                'Content-Range':   f'bytes {start}-{end}/{size}',
                'Accept-Ranges':   'bytes',
            })
            with open(file_path, 'rb') as f:
                f.seek(start)
                self.wfile.write(f.read(length))
        else:
            self._send_headers(200, mime, {
                'Content-Length': str(size),
                'Accept-Ranges':  'bytes',
            })
            with open(file_path, 'rb') as f:
                self.wfile.write(f.read())


if __name__ == '__main__':
    port    = int(os.environ.get('PORT', 8080))
    db_path = str(DATA_DIR / 'study.db')

    log.info('Starting LangLab')
    log.info('  BASE_DIR     = %s', BASE_DIR)
    log.info('  FRONTEND_DIR = %s', FRONTEND_DIR)
    log.info('  DATA_DIR     = %s', DATA_DIR)
    log.info('  db_path      = %s', db_path)
    log.info('  port         = %s', port)

    db = Database(db_path)
    LangLabHandler.db = db

    server = HTTPServer(('0.0.0.0', port), LangLabHandler)
    log.info('LangLab running on http://0.0.0.0:%s', port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
