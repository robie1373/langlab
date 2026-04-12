/**
 * Pimsleur VTT player module.
 *
 * Data contract (from /api/lessons/:lang):
 *   lesson = { id, title, mp3_path, entries: [{ start, end, lines[], korean[] }] }
 *
 * Vocab state contract (from /api/vocab/:userId):
 *   vocabMap = Map<word_string, { word_id, state }>   (state 0-3 per FSRS)
 *
 * Word state is 0=New/1=Learning/3=Relearning → show indicator
 *               2=Review → no indicator (known)
 */

import { showToast } from './ui.js';

let lessons       = [];
let currentIdx    = 0;
let viewMode      = 'korean';
let lastActiveEl  = null;
let pauseAt       = null;
let jkPlay        = false;
let currentUser   = null;
let vocabMap      = new Map();  // word → { word_id, state }
let sessionLogged = false;

const audio = () => document.getElementById('player-audio');
const sel   = () => document.getElementById('lessonSel');

// ── public init ─────────────────────────────────────────────────────────────

export async function initPlayer(user) {
  currentUser = user;
  await Promise.all([loadLessons(), loadVocab()]);
  buildSelector();
  restoreLesson();
  bindControls();
}

// ── data loading ─────────────────────────────────────────────────────────────

async function loadLessons() {
  const lang = currentUser.default_lang;
  const res  = await fetch(`/api/lessons/${lang}`);
  lessons    = await res.json();
}

async function loadVocab() {
  if (!currentUser) return;
  const res  = await fetch(`/api/vocab/${currentUser.id}`);
  const list = await res.json();
  vocabMap   = new Map(list.map(v => [v.word, { word_id: v.id, state: v.state }]));
}

// ── selector ─────────────────────────────────────────────────────────────────

function buildSelector() {
  const s = sel();
  s.innerHTML = '';
  lessons.forEach((l, i) => {
    const opt = document.createElement('option');
    opt.value   = i;
    opt.textContent = l.title;
    s.appendChild(opt);
  });
  s.addEventListener('change', () => loadLesson(+s.value));
}

function restoreLesson() {
  const saved = +(localStorage.getItem('langlab_lesson') || 0);
  const idx   = Math.min(saved, lessons.length - 1);
  sel().value = idx;
  loadLesson(idx);
}

// ── lesson load ───────────────────────────────────────────────────────────────

async function loadLesson(idx) {
  if (!lessons.length) return;
  currentIdx   = idx;
  lastActiveEl = null;
  pauseAt      = null;
  sessionLogged = false;
  localStorage.setItem('langlab_lesson', idx);

  const lesson = lessons[idx];
  const a      = audio();
  a.src        = `/audio/${currentUser.default_lang}/${lesson.mp3_path}`;
  a.removeEventListener('timeupdate', onTimeUpdate);
  a.addEventListener('timeupdate', onTimeUpdate);

  // Fetch full entry data on first load; cache it on the lesson object.
  if (!lesson.entries) {
    const res     = await fetch(`/api/lessons/${currentUser.default_lang}/${lesson.lesson_path}`);
    const data    = await res.json();
    lesson.entries = data.entries ?? [];
  }

  render();
}

// ── view / dark ───────────────────────────────────────────────────────────────

export function setView(mode) {
  viewMode = mode;
  document.getElementById('btnKorean').classList.toggle('on', mode === 'korean');
  document.getElementById('btnFull').classList.toggle('on', mode === 'full');
  render();
}

// ── render ────────────────────────────────────────────────────────────────────

function isKorean(str) {
  return /[\uAC00-\uD7AF\u1100-\u11FF\u3130-\u318F]/.test(str);
}

/**
 * Split a Korean string into word-like tokens for vocab indicators.
 * We split on spaces and punctuation, keeping each part separately.
 * Each token that is purely Korean gets a clickable span if it's in vocabMap.
 */
function renderKoreanLine(text, entryStart) {
  const fragment = document.createDocumentFragment();
  // Split by spaces, keeping the space in the stream
  const parts = text.split(/(\s+)/);
  parts.forEach(part => {
    if (/\s+/.test(part)) {
      fragment.appendChild(document.createTextNode(part));
      return;
    }
    // Strip trailing punctuation for lookup, keep it for display
    const clean = part.replace(/[。、，。！？,.!?'"'"'"»«…—–\-]+$/, '');
    const trail = part.slice(clean.length);
    const info  = vocabMap.get(clean);

    if (clean && isKorean(clean)) {
      const span = document.createElement('span');
      span.className   = 'word-token ko';
      span.textContent = clean;
      if (info !== undefined) {
        span.dataset.state  = info.state;
        span.dataset.wordId = info.word_id;
        span.dataset.word   = clean;
      } else {
        // Word exists in text but not yet in our vocab — treat as new (state 0)
        span.dataset.state = '0';
        span.dataset.word  = clean;
      }
      span.addEventListener('click', e => {
        e.stopPropagation();
        openRatingCard(span, clean, info);
      });
      fragment.appendChild(span);
      if (trail) fragment.appendChild(document.createTextNode(trail));
    } else {
      fragment.appendChild(document.createTextNode(part));
    }
  });
  return fragment;
}

function render() {
  const lesson  = lessons[currentIdx];
  if (!lesson) return;
  const entries   = lesson.entries;
  const container = document.getElementById('entries');
  const nodes     = [];

  entries.forEach(e => {
    const display = viewMode === 'korean' ? e.korean : e.lines;
    if (!display.length) return;

    const div = document.createElement('div');
    div.className       = 'entry';
    div.dataset.start   = e.start;
    div.dataset.end     = e.end;

    display.forEach((line, i) => {
      if (i > 0) div.appendChild(document.createElement('br'));
      if (isKorean(line)) {
        div.appendChild(renderKoreanLine(line, e.start));
      } else {
        const span = document.createElement('span');
        span.className   = 'en';
        span.textContent = line;
        div.appendChild(span);
      }
    });

    div.addEventListener('click', () => {
      audio().currentTime = e.start;
      audio().play();
    });

    nodes.push(div);
  });

  container.replaceChildren(...nodes);
}

// ── audio sync ────────────────────────────────────────────────────────────────

function scrollToMiddle(el) {
  const barH   = document.querySelector('.audio-bar').offsetHeight;
  const usable = window.innerHeight - barH;
  const rect   = el.getBoundingClientRect();
  const elMid  = rect.top + rect.height / 2;
  const delta  = elMid - usable / 2;
  if (Math.abs(delta) > usable / 6) {
    window.scrollTo({ top: window.scrollY + delta, behavior: 'smooth' });
  }
}

function stepCue(delta) {
  const entries = Array.from(document.querySelectorAll('.entry'));
  if (!entries.length) return;
  const a = audio();

  let idx = lastActiveEl ? entries.indexOf(lastActiveEl) : -1;
  if (idx < 0) {
    const t = a.currentTime;
    idx = entries.findIndex(el => +el.dataset.end > t);
    if (idx < 0) idx = entries.length - 1;
  }

  idx = Math.max(0, Math.min(entries.length - 1, idx + delta));
  const el = entries[idx];

  entries.forEach(e => e.classList.remove('active'));
  el.classList.add('active');
  lastActiveEl = el;
  scrollToMiddle(el);

  pauseAt        = +el.dataset.end;
  a.currentTime  = +el.dataset.start;
  jkPlay         = true;
  a.play();
}

function onTimeUpdate() {
  const t = this.currentTime;

  if (pauseAt !== null && t >= pauseAt) {
    this.pause();
    pauseAt = null;
    return;
  }
  if (this.paused) return;

  // Log session on first play
  if (!sessionLogged && t > 0) {
    sessionLogged = true;
    logSession();
  }

  let activeEl = null;
  document.querySelectorAll('.entry').forEach(el => {
    el.classList.remove('active');
    if (t >= +el.dataset.start && t < +el.dataset.end) activeEl = el;
  });

  const toHighlight = activeEl || lastActiveEl;
  if (toHighlight) toHighlight.classList.add('active');

  if (activeEl && activeEl !== lastActiveEl) {
    lastActiveEl = activeEl;
    scrollToMiddle(activeEl);
  }
}

// ── session logging ───────────────────────────────────────────────────────────

async function logSession() {
  if (!currentUser || !lessons[currentIdx]) return;
  const lesson = lessons[currentIdx];
  await fetch('/api/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_id:      currentUser.id,
      language:     currentUser.default_lang,
      session_type: 'pimsleur',
      lesson_path:  lesson.lesson_path || lesson.id,
    }),
  });
}

// ── rating card ───────────────────────────────────────────────────────────────

let ratingCard = null;

function openRatingCard(anchor, word, info) {
  if (!ratingCard) {
    ratingCard = document.getElementById('ratingCard');
  }
  const card = ratingCard;

  // Populate
  card.querySelector('.word-display').textContent  = word;
  const translationEl = card.querySelector('.translation');
  // Look up translation from lessons data or leave blank
  translationEl.textContent = info?.translation || '';

  // Position near the clicked token
  const rect = anchor.getBoundingClientRect();
  const top  = Math.min(rect.bottom + 8, window.innerHeight - 200);
  const left = Math.min(rect.left, window.innerWidth - 290);
  card.style.top  = `${top}px`;
  card.style.left = `${left}px`;
  card.classList.add('visible');

  // Wire rating buttons
  card.querySelectorAll('.rating-btn').forEach(btn => {
    btn.onclick = async () => {
      const rating = +btn.dataset.r;
      card.classList.remove('visible');
      const result = await rateWord(word, info?.word_id, rating);
      if (result) {
        // Update vocabMap with new state
        vocabMap.set(word, { word_id: result.word_id, state: result.state });
        // Update all tokens for this word in the current view
        document.querySelectorAll(`.word-token[data-word="${CSS.escape(word)}"]`).forEach(t => {
          t.dataset.state = result.state;
        });
      }
    };
  });

  // Mark known (jump straight to state 2)
  card.querySelector('.btn-mark-known').onclick = async () => {
    card.classList.remove('visible');
    const result = await rateWord(word, info?.word_id, 4); // Easy = promote quickly
    if (result) {
      vocabMap.set(word, { word_id: result.word_id, state: 2 });
      document.querySelectorAll(`.word-token[data-word="${CSS.escape(word)}"]`).forEach(t => {
        t.dataset.state = '2';
      });
      showToast(`Marked known: ${word}`);
    }
  };
}

async function rateWord(word, wordId, rating) {
  if (!currentUser) return null;
  // If we don't have a word_id yet (word from transcript not yet in vocab table),
  // the server will handle creation on the fly via rate_word.
  const body = {
    user_id: currentUser.id,
    rating,
  };
  if (wordId) {
    body.word_id = wordId;
  } else {
    body.word    = word;
    body.language = currentUser.default_lang;
  }

  const res  = await fetch('/api/vocab/rate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return res.ok ? res.json() : null;
}

// Close rating card on outside click
document.addEventListener('click', e => {
  if (ratingCard && !ratingCard.contains(e.target)) {
    ratingCard.classList.remove('visible');
  }
});

// ── keyboard controls ─────────────────────────────────────────────────────────

function bindControls() {
  audio().addEventListener('play', () => {
    if (!jkPlay) pauseAt = null;
    jkPlay = false;
  });

  document.addEventListener('keydown', ev => {
    const tag = ev.target.tagName;
    if (['SELECT','INPUT','TEXTAREA','AUDIO'].includes(tag)) return;
    // Don't fire if a rating card is open
    if (ratingCard?.classList.contains('visible')) return;

    const a = audio();
    switch (ev.key) {
      case ' ':
        ev.preventDefault();
        pauseAt = null;
        a.paused ? a.play() : a.pause();
        break;
      case 'a': case 'A':
        ev.preventDefault(); pauseAt = null;
        a.currentTime = Math.max(0, a.currentTime - 5);
        break;
      case 'd': case 'D':
        ev.preventDefault(); pauseAt = null;
        a.currentTime = Math.min(a.duration || 1e9, a.currentTime + 5);
        break;
      case 'j': case 'J': ev.preventDefault(); stepCue(+1); break;
      case 'k': case 'K': ev.preventDefault(); stepCue(-1); break;
      case 'r': case 'R':
        ev.preventDefault();
        if (lastActiveEl) { a.currentTime = +lastActiveEl.dataset.start; a.play(); }
        break;
      case 'm': case 'M':
        ev.preventDefault();
        a.muted = !a.muted;
        document.getElementById('mute-badge').classList.toggle('visible', a.muted);
        break;
      case '?':
        ev.preventDefault();
        document.getElementById('modalOverlay').classList.add('visible');
        break;
      case 'Escape':
        document.getElementById('modalOverlay').classList.remove('visible');
        if (ratingCard) ratingCard.classList.remove('visible');
        break;
      case 'ArrowRight': case 'ArrowDown': {
        const next = Math.min(currentIdx + 1, lessons.length - 1);
        sel().value = next; loadLesson(next);
        break;
      }
      case 'ArrowLeft': case 'ArrowUp': {
        const prev = Math.max(currentIdx - 1, 0);
        sel().value = prev; loadLesson(prev);
        break;
      }
    }
  });
}
