"""
E2E tests — Admin / Library view.

Covers: section structure, stats loading, user selector sync,
drop zones present, import/ingest buttons.
"""

import pytest
from playwright.sync_api import Page, expect

from .helpers import pick_user, nav_to


def _open_admin(page: Page, base_url: str):
    pick_user(page, base_url, 'Robie')
    nav_to(page, 'view-admin')


# ── structure ─────────────────────────────────────────────────────────────────

def test_admin_view_renders(page: Page, base_url: str):
    _open_admin(page, base_url)
    expect(page.locator('#view-admin.active')).to_be_visible()


def test_vocab_section_heading_present(page: Page, base_url: str):
    _open_admin(page, base_url)
    expect(page.locator('.admin-section h2:has-text("Vocab")')).to_be_visible()


def test_library_section_heading_present(page: Page, base_url: str):
    _open_admin(page, base_url)
    expect(page.locator('.admin-section h2:has-text("Audio Library")')).to_be_visible()


def test_log_section_present(page: Page, base_url: str):
    _open_admin(page, base_url)
    expect(page.locator('#admin-log')).to_be_visible()


# ── controls ──────────────────────────────────────────────────────────────────

def test_vocab_user_selector_present(page: Page, base_url: str):
    _open_admin(page, base_url)
    expect(page.locator('#admin-vocab-user')).to_be_visible()


def test_lesson_user_selector_present(page: Page, base_url: str):
    _open_admin(page, base_url)
    expect(page.locator('#admin-lesson-user')).to_be_visible()


def test_import_button_present(page: Page, base_url: str):
    _open_admin(page, base_url)
    expect(page.locator('#admin-import-btn')).to_be_visible()


def test_ingest_button_present(page: Page, base_url: str):
    _open_admin(page, base_url)
    expect(page.locator('#admin-ingest-btn')).to_be_visible()


def test_apkg_drop_zone_present(page: Page, base_url: str):
    _open_admin(page, base_url)
    expect(page.locator('#admin-apkg-zone')).to_be_visible()


def test_vtt_drop_zone_present(page: Page, base_url: str):
    _open_admin(page, base_url)
    expect(page.locator('#admin-vtt-zone')).to_be_visible()


# ── live stats ────────────────────────────────────────────────────────────────

def test_vocab_stat_loads(page: Page, base_url: str):
    """Stats should not stay as the placeholder dash."""
    _open_admin(page, base_url)
    page.wait_for_function(
        "document.getElementById('admin-vocab-stat').textContent.trim() !== '—'",
        timeout=5000,
    )
    stat = page.locator('#admin-vocab-stat').text_content()
    assert stat.strip() != '—', f'Vocab stat never loaded: {stat!r}'


def test_lesson_stat_loads(page: Page, base_url: str):
    _open_admin(page, base_url)
    page.wait_for_function(
        "document.getElementById('admin-lesson-stat').textContent.trim() !== '—'",
        timeout=5000,
    )
    stat = page.locator('#admin-lesson-stat').text_content()
    assert stat.strip() != '—', f'Lesson stat never loaded: {stat!r}'


def test_vocab_stat_shows_word_count(page: Page, base_url: str):
    """Stat line should mention a number of words."""
    _open_admin(page, base_url)
    page.wait_for_function(
        "document.getElementById('admin-vocab-stat').textContent.includes('words')",
        timeout=5000,
    )
    stat = page.locator('#admin-vocab-stat').text_content()
    assert 'words' in stat, f'Expected "words" in stat, got: {stat!r}'
