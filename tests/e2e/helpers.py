"""Shared page interaction helpers for E2E tests."""

from playwright.sync_api import Page


def pick_user(page: Page, base_url: str, name: str = 'Robie'):
    """Load the app and select a user by display name."""
    page.goto(base_url)
    page.locator(f'.picker-btn:has-text("{name}")').click()
    page.wait_for_selector('.nav-btn[data-view]', state='attached')


def nav_to(page: Page, view_id: str):
    """Click a desktop nav button and wait for the view to become active."""
    page.locator(f'.nav-btn[data-view="{view_id}"]').click()
    page.wait_for_selector(f'#{view_id}.active')
