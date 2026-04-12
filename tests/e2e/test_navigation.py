"""
E2E tests — navigation and view routing.

Covers: user picker, nav tab switching, view isolation,
user chip, logo/switch-user, basic app shell structure.
"""

import pytest
from playwright.sync_api import Page, expect

from .helpers import pick_user, nav_to


# ── user picker ──────────────────────────────────────────────────────────────

def test_picker_renders_user_buttons(page: Page, base_url: str):
    page.goto(base_url)
    expect(page.locator('.picker-btn')).to_have_count(2)


def test_picker_shows_robie(page: Page, base_url: str):
    page.goto(base_url)
    expect(page.locator('.picker-btn', has_text='Robie')).to_be_visible()


def test_picker_shows_anna(page: Page, base_url: str):
    page.goto(base_url)
    expect(page.locator('.picker-btn', has_text='Anna')).to_be_visible()


def test_picker_visible_on_load(page: Page, base_url: str):
    page.goto(base_url)
    expect(page.locator('#view-picker')).to_be_visible()
    expect(page.locator('#view-app')).not_to_be_visible()


# ── user selection ───────────────────────────────────────────────────────────

def test_selecting_user_shows_app(page: Page, base_url: str):
    pick_user(page, base_url, 'Robie')
    expect(page.locator('#view-app')).to_be_visible()
    expect(page.locator('#view-picker')).not_to_be_visible()


def test_user_chip_shows_display_name(page: Page, base_url: str):
    pick_user(page, base_url, 'Robie')
    expect(page.locator('#user-chip')).to_have_text('Robie')


def test_logo_click_returns_to_picker(page: Page, base_url: str):
    pick_user(page, base_url, 'Robie')
    page.locator('.logo').click()
    expect(page.locator('#view-picker')).to_be_visible()


# ── nav tabs: Robie (Korean) ──────────────────────────────────────────────────

def test_robie_has_player_tab(page: Page, base_url: str):
    pick_user(page, base_url, 'Robie')
    expect(page.locator('.nav-btn[data-view="view-player"]')).to_be_visible()


def test_robie_has_all_expected_tabs(page: Page, base_url: str):
    pick_user(page, base_url, 'Robie')
    for view_id in ['view-player', 'view-lessons', 'view-tutor',
                    'view-flashcards', 'view-vocab', 'view-progress', 'view-admin']:
        expect(page.locator(f'.nav-btn[data-view="{view_id}"]')).to_be_visible()


def test_anna_has_no_player_tab(page: Page, base_url: str):
    """Anna (Spanish) has no Pimsleur player tab."""
    pick_user(page, base_url, 'Anna')
    expect(page.locator('.nav-btn[data-view="view-player"]')).to_have_count(0)


# ── view switching ────────────────────────────────────────────────────────────

def test_gear_opens_admin_view(page: Page, base_url: str):
    pick_user(page, base_url, 'Robie')
    nav_to(page, 'view-admin')
    expect(page.locator('#view-admin.active')).to_be_visible()


def test_switching_views_hides_others(page: Page, base_url: str):
    pick_user(page, base_url, 'Robie')
    nav_to(page, 'view-admin')
    expect(page.locator('#view-player.active')).to_have_count(0)
    expect(page.locator('#view-flashcards.active')).to_have_count(0)


def test_active_nav_btn_marked(page: Page, base_url: str):
    pick_user(page, base_url, 'Robie')
    nav_to(page, 'view-vocab')
    expect(page.locator('.nav-btn[data-view="view-vocab"].active')).to_be_visible()


def test_flashcards_tab_opens_flashcards(page: Page, base_url: str):
    pick_user(page, base_url, 'Robie')
    nav_to(page, 'view-flashcards')
    expect(page.locator('#view-flashcards.active')).to_be_visible()


def test_progress_tab_opens_progress(page: Page, base_url: str):
    pick_user(page, base_url, 'Robie')
    nav_to(page, 'view-progress')
    expect(page.locator('#view-progress.active')).to_be_visible()
