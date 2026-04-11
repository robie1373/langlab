#!/usr/bin/env python3
"""LangLab — language learning suite server."""

import json
import mimetypes
import os
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

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


class LangLabHandler(BaseHTTPRequestHandler):
    db: Database = None  # injected at startup

    def log_message(self, fmt, *args):
        pass  # suppress default Apache-style access log

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

        else:
            self._err(404, 'Unknown endpoint')

    # ── POST API ────────────────────────────────────────────────────────────

    def _api_post(self, path: str):
        body = self._read_body()

        if path == '/api/sessions':
            session_id = self.db.log_session(body)
            self._json({'id': session_id})

        elif path == '/api/vocab/rate':
            self._json(self.db.rate_word(body))

        elif path == '/api/flashcards/review':
            self._json(self.db.review_card(body))

        else:
            self._err(404, 'Unknown endpoint')

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

    db = Database(db_path)
    LangLabHandler.db = db

    server = HTTPServer(('0.0.0.0', port), LangLabHandler)
    print(f'LangLab running on http://0.0.0.0:{port}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
