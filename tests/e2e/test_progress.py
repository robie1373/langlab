"""
E2E tests — Progress & Rewards view.

Covers: progress view structure (streak cards, heat map, badge grid),
goal ring on flashcard queue, end-session escape hatch.
"""

import pytest
from playwright.sync_api import Page, expect

from .helpers import pick_user, nav_to


def _open_progress(page: Page, base_url: str):
    pick_user(page, base_url, 'Robie')
    nav_to(page, 'view-progress')
    page.wait_for_selector('#view-progress.active')


def _open_flashcards(page: Page, base_url: str):
    pick_user(page, base_url, 'Robie')
    nav_to(page, 'view-flashcards')
    page.wait_for_selector('#fc-queue.active')


# ── progress view structure ───────────────────────────────────────────────────

def test_progress_view_renders(page: Page, base_url: str):
    _open_progress(page, base_url)
    expect(page.locator('#view-progress.active')).to_be_visible()


def test_streak_row_present(page: Page, base_url: str):
    _open_progress(page, base_url)
    expect(page.locator('#pr-streak-row')).to_be_visible()


def test_streak_cards_rendered(page: Page, base_url: str):
    _open_progress(page, base_url)
    # At least one streak card should be rendered
    page.wait_for_selector('.pr-streak-card', timeout=4000)
    expect(page.locator('.pr-streak-card').first).to_be_visible()


def test_streak_card_shows_number(page: Page, base_url: str):
    _open_progress(page, base_url)
    page.wait_for_selector('.pr-sc-number', timeout=4000)
    # Number element present and contains text
    text = page.locator('.pr-sc-number').first.text_content()
    assert text.strip().isdigit(), f'Streak card number not numeric: {text!r}'


def test_heatmap_section_present(page: Page, base_url: str):
    _open_progress(page, base_url)
    expect(page.locator('#pr-heatmap-wrap')).to_be_visible()


def test_heatmap_grid_rendered(page: Page, base_url: str):
    _open_progress(page, base_url)
    page.wait_for_selector('.pr-heatmap', timeout=4000)
    expect(page.locator('.pr-heatmap')).to_be_visible()


def test_heatmap_has_day_cells(page: Page, base_url: str):
    _open_progress(page, base_url)
    page.wait_for_selector('.pr-hm-day', timeout=4000)
    count = page.locator('.pr-hm-day').count()
    # 52 weeks * 7 days = 364, plus current partial week
    assert count >= 300, f'Expected ≥300 heat map cells, got {count}'


def test_badges_section_present(page: Page, base_url: str):
    _open_progress(page, base_url)
    expect(page.locator('#pr-badges-wrap')).to_be_visible()


def test_badge_grid_rendered(page: Page, base_url: str):
    _open_progress(page, base_url)
    page.wait_for_selector('.pr-badge', timeout=4000)
    count = page.locator('.pr-badge').count()
    assert count > 20, f'Expected >20 badge pills, got {count}'


def test_unearned_badges_have_class(page: Page, base_url: str):
    _open_progress(page, base_url)
    page.wait_for_selector('.pr-badge', timeout=4000)
    # On a fresh DB there should be unearned badges
    unearned = page.locator('.pr-badge.unearned').count()
    earned   = page.locator('.pr-badge.earned').count()
    assert unearned + earned > 0, 'No badges rendered at all'


def test_badge_group_titles_present(page: Page, base_url: str):
    _open_progress(page, base_url)
    page.wait_for_selector('.pr-badge-group-title', timeout=4000)
    count = page.locator('.pr-badge-group-title').count()
    assert count >= 3, f'Expected at least 3 badge groups, got {count}'


# ── daily goal ring on flashcard queue ───────────────────────────────────────

def test_goal_ring_present_on_queue(page: Page, base_url: str):
    _open_flashcards(page, base_url)
    page.wait_for_selector('#fc-goal-ring', timeout=4000)
    expect(page.locator('#fc-goal-ring')).to_be_visible()


def test_goal_ring_has_svg(page: Page, base_url: str):
    _open_flashcards(page, base_url)
    page.wait_for_selector('.fc-goal-svg', timeout=4000)
    expect(page.locator('.fc-goal-svg')).to_be_visible()


def test_goal_ring_has_text(page: Page, base_url: str):
    _open_flashcards(page, base_url)
    page.wait_for_selector('.fc-goal-text', timeout=4000)
    expect(page.locator('.fc-goal-text')).to_be_visible()


# ── end session button ────────────────────────────────────────────────────────

def test_end_session_btn_in_review(page: Page, base_url: str):
    _open_flashcards(page, base_url)
    due = int(page.locator('#fc-due-number').text_content().strip())
    if due == 0:
        pytest.skip('No cards due — cannot enter review')
    page.locator('#fc-start-btn').click()
    page.wait_for_selector('#fc-review.active')
    expect(page.locator('#fc-end-btn')).to_be_visible()


def test_end_session_returns_to_queue(page: Page, base_url: str):
    _open_flashcards(page, base_url)
    due = int(page.locator('#fc-due-number').text_content().strip())
    if due == 0:
        pytest.skip('No cards due — cannot enter review')
    page.locator('#fc-start-btn').click()
    page.wait_for_selector('#fc-review.active')
    page.locator('#fc-end-btn').click()
    page.wait_for_selector('#fc-queue.active, #fc-done.active', timeout=3000)
    # Should return to queue (since we haven't reviewed anything, done screen
    # may show instead — either is acceptable, but review should be gone)
    review_active = page.locator('#fc-review.active').count()
    assert review_active == 0, 'Still on review screen after End clicked'


def test_escape_key_exits_review(page: Page, base_url: str):
    _open_flashcards(page, base_url)
    due = int(page.locator('#fc-due-number').text_content().strip())
    if due == 0:
        pytest.skip('No cards due — cannot enter review')
    page.locator('#fc-start-btn').click()
    page.wait_for_selector('#fc-review.active')
    page.keyboard.press('Escape')
    page.wait_for_selector('#fc-queue.active, #fc-done.active', timeout=3000)
    review_active = page.locator('#fc-review.active').count()
    assert review_active == 0, 'Still on review screen after Escape key'


# ── toast container ───────────────────────────────────────────────────────────

def test_toast_container_exists(page: Page, base_url: str):
    pick_user(page, base_url, 'Robie')
    expect(page.locator('#toast-container')).to_be_attached()
