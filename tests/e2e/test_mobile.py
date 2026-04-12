"""
E2E tests — mobile viewport and hamburger menu.

At ≤640px: #app-nav is hidden, .hamburger-btn is visible.
Hamburger click adds .open to #mobile-menu.
Mobile menu buttons mirror the desktop nav tabs.
"""

import pytest
from playwright.sync_api import Page, expect

from .helpers import pick_user

MOBILE_VIEWPORT = {'width': 390, 'height': 844}   # iPhone 14 Pro
DESKTOP_VIEWPORT = {'width': 1280, 'height': 800}


def _open_app_mobile(page: Page, base_url: str):
    page.set_viewport_size(MOBILE_VIEWPORT)
    pick_user(page, base_url, 'Robie')


# ── layout at mobile width ────────────────────────────────────────────────────

def test_hamburger_visible_at_mobile_width(page: Page, base_url: str):
    _open_app_mobile(page, base_url)
    expect(page.locator('#hamburger-btn')).to_be_visible()


def test_desktop_nav_hidden_at_mobile_width(page: Page, base_url: str):
    _open_app_mobile(page, base_url)
    expect(page.locator('#app-nav')).to_be_hidden()


def test_hamburger_hidden_at_desktop_width(page: Page, base_url: str):
    page.set_viewport_size(DESKTOP_VIEWPORT)
    pick_user(page, base_url, 'Robie')
    expect(page.locator('#hamburger-btn')).to_be_hidden()


def test_desktop_nav_visible_at_desktop_width(page: Page, base_url: str):
    page.set_viewport_size(DESKTOP_VIEWPORT)
    pick_user(page, base_url, 'Robie')
    expect(page.locator('#app-nav')).to_be_visible()


# ── hamburger interaction ─────────────────────────────────────────────────────

def test_mobile_menu_closed_on_load(page: Page, base_url: str):
    _open_app_mobile(page, base_url)
    expect(page.locator('#mobile-menu.open')).to_have_count(0)


def test_hamburger_click_opens_menu(page: Page, base_url: str):
    _open_app_mobile(page, base_url)
    page.locator('#hamburger-btn').click()
    expect(page.locator('#mobile-menu.open')).to_be_visible()


def test_hamburger_icon_changes_to_x_when_open(page: Page, base_url: str):
    _open_app_mobile(page, base_url)
    page.locator('#hamburger-btn').click()
    expect(page.locator('#hamburger-btn')).to_have_text('✕')


def test_hamburger_icon_reverts_on_second_click(page: Page, base_url: str):
    _open_app_mobile(page, base_url)
    page.locator('#hamburger-btn').click()
    page.locator('#hamburger-btn').click()
    expect(page.locator('#hamburger-btn')).to_have_text('☰')
    expect(page.locator('#mobile-menu.open')).to_have_count(0)


# ── mobile menu content ───────────────────────────────────────────────────────

def test_mobile_menu_has_nav_buttons(page: Page, base_url: str):
    _open_app_mobile(page, base_url)
    page.locator('#hamburger-btn').click()
    count = page.locator('.mobile-menu-btn').count()
    assert count >= 6, f'Expected ≥6 mobile menu buttons, got {count}'


def test_mobile_menu_nav_mirrors_desktop(page: Page, base_url: str):
    """Mobile menu should have the same view targets as the desktop nav."""
    _open_app_mobile(page, base_url)
    page.locator('#hamburger-btn').click()
    mobile_views = set(
        page.locator('.mobile-menu-btn').nth(i).get_attribute('data-view')
        for i in range(page.locator('.mobile-menu-btn').count())
    )
    expected = {'view-player', 'view-lessons', 'view-tutor',
                'view-flashcards', 'view-vocab', 'view-progress', 'view-admin'}
    assert mobile_views == expected, f'Mobile menu views mismatch: {mobile_views}'


def test_mobile_menu_nav_switches_view(page: Page, base_url: str):
    _open_app_mobile(page, base_url)
    page.locator('#hamburger-btn').click()
    page.locator('.mobile-menu-btn[data-view="view-vocab"]').click()
    page.wait_for_selector('#view-vocab.active')
    expect(page.locator('#view-vocab.active')).to_be_visible()


def test_mobile_menu_closes_after_nav(page: Page, base_url: str):
    _open_app_mobile(page, base_url)
    page.locator('#hamburger-btn').click()
    page.locator('.mobile-menu-btn[data-view="view-vocab"]').click()
    expect(page.locator('#mobile-menu.open')).to_have_count(0)
