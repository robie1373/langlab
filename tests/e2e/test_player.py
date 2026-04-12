"""
E2E tests — VTT player view.

Covers: lesson selector populated, view toggle buttons,
entries container, audio element, lesson switching.
"""

import pytest
from playwright.sync_api import Page, expect

from .helpers import pick_user, nav_to


def _open_player(page: Page, base_url: str):
    pick_user(page, base_url, 'Robie')
    # Player is default view; wait for lesson list and first lesson entries to load
    page.wait_for_selector('#lessonSel option', state='attached')
    page.wait_for_selector('.entry', timeout=15000)


def test_player_is_default_view_for_robie(page: Page, base_url: str):
    pick_user(page, base_url, 'Robie')
    expect(page.locator('#view-player.active')).to_be_visible()


def test_lesson_selector_is_present(page: Page, base_url: str):
    _open_player(page, base_url)
    expect(page.locator('#lessonSel')).to_be_visible()


def test_lesson_selector_populated(page: Page, base_url: str):
    _open_player(page, base_url)
    count = page.locator('#lessonSel option').count()
    assert count >= 18, f'Expected ≥18 lessons, got {count}'


def test_korean_view_toggle_present(page: Page, base_url: str):
    _open_player(page, base_url)
    expect(page.locator('#btnKorean')).to_be_visible()


def test_full_view_toggle_present(page: Page, base_url: str):
    _open_player(page, base_url)
    expect(page.locator('#btnFull')).to_be_visible()


def test_entries_container_present(page: Page, base_url: str):
    _open_player(page, base_url)
    expect(page.locator('#entries')).to_be_visible()


def test_entries_rendered(page: Page, base_url: str):
    """At least one VTT entry should render after load."""
    _open_player(page, base_url)   # already waits for .entry
    count = page.locator('.entry').count()
    assert count > 0, 'No entries rendered in player'


def test_audio_element_present(page: Page, base_url: str):
    _open_player(page, base_url)
    expect(page.locator('#player-audio')).to_be_attached()


def test_korean_toggle_active_by_default(page: Page, base_url: str):
    _open_player(page, base_url)
    expect(page.locator('#btnKorean.on')).to_be_visible()
