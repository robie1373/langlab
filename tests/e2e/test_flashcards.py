"""
E2E tests — flashcard review flow.

Covers: queue screen, due count, begin review, show answer,
rating buttons, progression to done screen.
"""

import pytest
from playwright.sync_api import Page, expect

from .helpers import pick_user, nav_to


def _open_flashcards(page: Page, base_url: str):
    pick_user(page, base_url, 'Robie')
    nav_to(page, 'view-flashcards')
    page.wait_for_selector('#fc-queue.active')


# ── queue screen ─────────────────────────────────────────────────────────────

def test_queue_screen_visible_on_enter(page: Page, base_url: str):
    _open_flashcards(page, base_url)
    expect(page.locator('#fc-queue.active')).to_be_visible()


def test_due_ring_visible(page: Page, base_url: str):
    _open_flashcards(page, base_url)
    expect(page.locator('.fc-due-ring')).to_be_visible()


def test_due_number_element_present(page: Page, base_url: str):
    _open_flashcards(page, base_url)
    expect(page.locator('#fc-due-number')).to_be_visible()


def test_begin_review_button_present(page: Page, base_url: str):
    _open_flashcards(page, base_url)
    expect(page.locator('#fc-start-btn')).to_be_visible()


def test_due_number_is_numeric(page: Page, base_url: str):
    _open_flashcards(page, base_url)
    text = page.locator('#fc-due-number').text_content()
    assert text.strip().isdigit(), f'Due number not numeric: {text!r}'


# ── review flow (requires cards due) ─────────────────────────────────────────

def test_begin_review_shows_review_screen(page: Page, base_url: str):
    _open_flashcards(page, base_url)
    due = int(page.locator('#fc-due-number').text_content().strip())
    if due == 0:
        pytest.skip('No cards due — skipping review flow test')
    page.locator('#fc-start-btn').click()
    page.wait_for_selector('#fc-review.active')
    expect(page.locator('#fc-review.active')).to_be_visible()
    expect(page.locator('#fc-queue.active')).to_have_count(0)


def test_show_answer_button_visible_in_review(page: Page, base_url: str):
    _open_flashcards(page, base_url)
    if int(page.locator('#fc-due-number').text_content().strip()) == 0:
        pytest.skip('No cards due')
    page.locator('#fc-start-btn').click()
    page.wait_for_selector('#fc-review.active')
    expect(page.locator('#fc-show-btn')).to_be_visible()


def test_show_answer_reveals_rating_buttons(page: Page, base_url: str):
    _open_flashcards(page, base_url)
    if int(page.locator('#fc-due-number').text_content().strip()) == 0:
        pytest.skip('No cards due')
    page.locator('#fc-start-btn').click()
    page.wait_for_selector('#fc-review.active')
    # Ratings hidden before show
    expect(page.locator('#fc-rating-wrap.hidden')).to_be_attached()
    page.locator('#fc-show-btn').click()
    # After show: rating wrap loses .hidden
    expect(page.locator('#fc-rating-wrap:not(.hidden)')).to_be_visible()


def test_all_four_rating_buttons_present(page: Page, base_url: str):
    _open_flashcards(page, base_url)
    if int(page.locator('#fc-due-number').text_content().strip()) == 0:
        pytest.skip('No cards due')
    page.locator('#fc-start-btn').click()
    page.wait_for_selector('#fc-review.active')
    page.locator('#fc-show-btn').click()
    for label in ['Again', 'Hard', 'Good', 'Easy']:
        expect(page.locator(f'.fc-rate:has-text("{label}")')).to_be_visible()


def test_rating_advances_to_next_card_or_done(page: Page, base_url: str):
    _open_flashcards(page, base_url)
    if int(page.locator('#fc-due-number').text_content().strip()) == 0:
        pytest.skip('No cards due')
    page.locator('#fc-start-btn').click()
    page.wait_for_selector('#fc-review.active')
    page.locator('#fc-show-btn').click()
    page.locator('.fc-rate.good').click()
    # After rating: either still in review (next card) or on done screen
    page.wait_for_selector('#fc-review.active, #fc-done.active', timeout=3000)
    in_review = page.locator('#fc-review.active').count()
    in_done   = page.locator('#fc-done.active').count()
    assert in_review + in_done > 0, 'Neither review nor done screen active after rating'
