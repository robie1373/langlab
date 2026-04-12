"""
Pytest fixtures for LangLab E2E tests.

Requires the server to be running on localhost:8080, or set
LANGLAB_SERVER_URL to point at another instance. If no server is detected
this conftest will start one automatically (against the real data/study.db).

Run from the project root after entering the nix dev shell:
    pytest tests/e2e/ -v
"""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright, Page

BASE_URL     = os.environ.get('LANGLAB_SERVER_URL', 'http://localhost:8080')
PROJECT_ROOT = Path(__file__).parent.parent.parent


def _server_up() -> bool:
    try:
        s = socket.create_connection(('127.0.0.1', 8080), timeout=1)
        s.close()
        return True
    except OSError:
        return False


@pytest.fixture(scope='session')
def base_url():
    """Return base URL, starting the server if needed."""
    if _server_up():
        yield BASE_URL
        return

    server_py = PROJECT_ROOT / 'server.py'
    if not server_py.exists():
        pytest.exit(
            f'Server not running at {BASE_URL} and server.py not found. '
            'Start it first: python server.py'
        )

    proc = subprocess.Popen(
        [sys.executable, str(server_py)],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(30):
        if _server_up():
            break
        time.sleep(0.3)
    else:
        proc.kill()
        pytest.exit('Server failed to start on port 8080')

    yield BASE_URL
    proc.terminate()
    proc.wait(timeout=5)


@pytest.fixture(scope='session')
def _browser():
    """One browser instance for the whole session."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture
def page(_browser, base_url) -> Page:
    """Fresh browser context per test — isolated localStorage."""
    ctx = _browser.new_context()
    p   = ctx.new_page()
    yield p
    ctx.close()


