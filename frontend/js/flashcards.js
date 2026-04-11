/**
 * Flashcard review module.
 * FSRS-backed queue from /api/flashcards/due/:userId
 * Reviews posted to /api/flashcards/review
 */

import { showToast } from './ui.js';

let user        = null;
let queue       = [];
let current     = 0;
let sessionId   = null;
let results     = [];   // { rating }[]
let cardStart   = 0;
let audioEl     = null;

// ── public init ──────────────────────────────────────────────────────────────

export async function initFlashcards(currentUser) {
  user = currentUser;
  audioEl = document.getElementById('fc-audio');
  bindButtons();
  await refresh();
}

export async function refresh() {
  const res  = await fetch(`/api/flashcards/due/${user.id}`);
  queue      = await res.json();
  renderQueue();
}

// ── screen management ────────────────────────────────────────────────────────

function showScreen(name) {
  ['fc-queue', 'fc-review', 'fc-done'].forEach(id => {
    document.getElementById(id).classList.toggle('active', id === `fc-${name}`);
  });
}

// ── queue screen ──────────────────────────────────────────────────────────────

function renderQueue() {
  showScreen('queue');
  document.getElementById('fc-due-number').textContent = queue.length;

  const btn = document.getElementById('fc-start-btn');
  if (queue.length === 0) {
    document.getElementById('fc-queue-msg').textContent = 'All caught up — no cards due.';
    btn.disabled = true;
  } else {
    document.getElementById('fc-queue-msg').textContent =
      queue.length === 1 ? '1 card due for review' : `${queue.length} cards due for review`;
    btn.disabled = false;
  }
}

// ── review ────────────────────────────────────────────────────────────────────

async function startReview() {
  if (!queue.length) return;

  const res = await fetch('/api/sessions', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({
      user_id:      user.id,
      language:     user.default_lang,
      session_type: 'flashcard',
    }),
  });
  const data = await res.json();
  sessionId  = data.id;

  current = 0;
  results = [];
  showScreen('review');
  showCard(0);
}

function showCard(idx) {
  const card   = queue[idx];
  cardStart    = Date.now();

  // Progress
  const pct = queue.length > 1 ? (idx / queue.length) * 100 : 0;
  document.querySelector('.fc-progress-fill').style.width = `${pct}%`;
  document.querySelector('.fc-progress-text').textContent = `${idx} / ${queue.length}`;

  // Front face: Korean word
  document.querySelector('.fc-front .fc-word-display').textContent = card.word;

  // Back face: word + translation
  document.querySelector('.fc-back .fc-word-display').textContent  = card.word;
  document.querySelector('.fc-translation').textContent             = card.translation || '';

  // Reset flip
  document.getElementById('fc-card').classList.remove('flipped');
  document.getElementById('fc-show-wrap').classList.remove('hidden');
  document.getElementById('fc-rating-wrap').classList.add('hidden');

  // Audio
  const audioBtn = document.getElementById('fc-audio-btn');
  if (card.audio_path) {
    audioBtn.classList.remove('hidden');
    audioEl.src = `/audio/${card.audio_path}`;
    audioEl.play().catch(() => {});   // auto-play; ignore if blocked
  } else {
    audioBtn.classList.add('hidden');
    audioEl.src = '';
  }
}

function showAnswer() {
  document.getElementById('fc-card').classList.add('flipped');
  document.getElementById('fc-show-wrap').classList.add('hidden');
  document.getElementById('fc-rating-wrap').classList.remove('hidden');
}

async function rateCard(rating) {
  const card   = queue[current];
  const timeMs = Date.now() - cardStart;

  results.push({ rating });

  fetch('/api/flashcards/review', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({
      user_id:    user.id,
      word_id:    card.word_id,
      rating,
      session_id: sessionId,
      time_ms:    timeMs,
    }),
  });

  current++;
  if (current >= queue.length) {
    showDone();
  } else {
    showCard(current);
  }
}

// ── done screen ───────────────────────────────────────────────────────────────

function showDone() {
  showScreen('done');

  const counts = [1, 2, 3, 4].map(r => results.filter(x => x.rating === r).length);
  ['again','hard','good','easy'].forEach((cls, i) => {
    document.querySelector(`.fc-dist-item.${cls} .fc-dist-num`).textContent = counts[i];
  });
  document.querySelector('.fc-done-total').textContent =
    `${results.length} card${results.length !== 1 ? 's' : ''} reviewed`;
}

// ── keyboard + button bindings ────────────────────────────────────────────────

function bindButtons() {
  document.getElementById('fc-start-btn').addEventListener('click', startReview);

  document.getElementById('fc-audio-btn').addEventListener('click', e => {
    e.stopPropagation();
    if (audioEl.src) audioEl.play().catch(() => {});
  });

  // Card click = show answer (when front showing)
  document.getElementById('fc-card').addEventListener('click', () => {
    if (!document.getElementById('fc-card').classList.contains('flipped')) showAnswer();
  });

  document.getElementById('fc-show-btn').addEventListener('click', showAnswer);

  document.querySelectorAll('.fc-rate').forEach(btn => {
    btn.addEventListener('click', () => rateCard(+btn.dataset.r));
  });

  document.getElementById('fc-done-again').addEventListener('click', async () => {
    await refresh();
    if (queue.length) startReview();
    else renderQueue();
  });

  document.getElementById('fc-done-home').addEventListener('click', () => {
    refresh();   // reset queue count in bg
  });

  document.addEventListener('keydown', onKey);
}

function onKey(ev) {
  // Only active when flashcard view is visible
  const view = document.getElementById('view-flashcards');
  if (!view?.classList.contains('active')) return;

  const card    = document.getElementById('fc-card');
  const flipped = card?.classList.contains('flipped');
  const tag     = ev.target.tagName;
  if (['INPUT','TEXTAREA','SELECT'].includes(tag)) return;

  if (!flipped && ev.key === ' ') {
    ev.preventDefault();
    showAnswer();
    return;
  }

  if (flipped) {
    const map = { '1': 1, '2': 2, '3': 3, '4': 4 };
    if (map[ev.key]) {
      ev.preventDefault();
      rateCard(map[ev.key]);
    }
    // Space = Good shortcut
    if (ev.key === ' ') {
      ev.preventDefault();
      rateCard(3);
    }
  }
}
