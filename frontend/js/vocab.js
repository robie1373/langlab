/**
 * Vocabulary browser — view and filter all words.
 * Fetch from /api/vocab/:userId and display grouped by FSRS state.
 */

import { showToast } from './ui.js';

let _user     = null;
let _vocab    = [];
let _filter   = '';   // '' = all, '0'=New, '1'=Learning, '2'=Review

const STATE_LABELS = ['New', 'Learning', 'Review', 'Relearning'];
const STATE_CLASSES = ['state-new', 'state-learning', 'state-review', 'state-relearning'];

export async function initVocab(user) {
  _user = user;
  bindFilters();
  await refresh();
}

export async function refresh() {
  try {
    const res = await fetch(`/api/vocab/${_user.id}`);
    _vocab = await res.json();
    renderVocab();
  } catch (err) {
    document.getElementById('vocab-list').innerHTML =
      `<div class="vocab-error">Failed to load vocabulary: ${err.message}</div>`;
  }
}

// ── filters ───────────────────────────────────────────────────────────────────

function bindFilters() {
  document.getElementById('vocab-filters').addEventListener('click', e => {
    const btn = e.target.closest('.vocab-filter');
    if (!btn) return;

    document.querySelectorAll('.vocab-filter')
      .forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    _filter = btn.dataset.state;
    renderVocab();
  });
}

// ── render ────────────────────────────────────────────────────────────────────

function renderVocab() {
  const visible = _filter === ''
    ? _vocab
    : _vocab.filter(w => String(w.state) === _filter);

  document.getElementById('vocab-count').textContent =
    `${visible.length} word${visible.length !== 1 ? 's' : ''}`;

  if (visible.length === 0) {
    document.getElementById('vocab-list').innerHTML =
      '<p class="vocab-empty">No words in this category yet.</p>';
    return;
  }

  // Sort: by state asc, then word alpha
  const sorted = [...visible].sort((a, b) => {
    if (a.state !== b.state) return a.state - b.state;
    return a.word.localeCompare(b.word, undefined, { sensitivity: 'base' });
  });

  document.getElementById('vocab-list').innerHTML = sorted.map(w => {
    const stateLabel = STATE_LABELS[w.state] ?? 'Unknown';
    const stateCls   = STATE_CLASSES[w.state] ?? '';
    const dueDate    = w.due_at ? new Date(w.due_at * 1000).toLocaleDateString() : '—';
    return `<div class="vocab-row">
      <div class="vr-word">${escapeHtmlBasic(w.word)}</div>
      <div class="vr-translation">${escapeHtmlBasic(w.translation || '')}</div>
      <div class="vr-meta">
        <span class="vr-state ${stateCls}">${stateLabel}</span>
        <span class="vr-reps">${w.reps}×</span>
        <span class="vr-due">due ${dueDate}</span>
      </div>
    </div>`;
  }).join('');
}

function escapeHtmlBasic(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}
