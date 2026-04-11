/**
 * LangLab main entry point.
 * Handles user selection, top-level routing, and module init.
 */

import { showView, showToast } from './ui.js';
import { initPlayer, setView as setPlayerView } from './player.js';
import { initFlashcards } from './flashcards.js';
import { initLesson, onLessonVisible } from './lesson.js';
import { initTutor, onTutorVisible, releaseMic } from './tutor.js';
import { initVocab } from './vocab.js';
import { initProgress } from './progress.js';
import { loadApiKey } from './gemini.js';
import { initSpeech } from './speech.js';

let currentUser    = null;
let initializedFor = null;   // user id we already ran init for

// ── startup ──────────────────────────────────────────────────────────────────

async function init() {
  if (localStorage.getItem('langlab_dark') === '1') {
    document.body.classList.add('dark');
  }

  await loadApiKey();

  const savedUser = localStorage.getItem('langlab_user');
  if (savedUser) {
    try {
      const users = await fetchUsers();
      const user  = users.find(u => u.name === savedUser);
      if (user) { await startSession(user); return; }
    } catch { /* fall through */ }
  }

  showPicker();
}

// ── user picker ───────────────────────────────────────────────────────────────

async function showPicker() {
  let users = [];
  try { users = await fetchUsers(); }
  catch { showView('view-picker'); return; }

  const container = document.querySelector('.picker-buttons');
  container.innerHTML = '';

  users.forEach(user => {
    const btn = document.createElement('button');
    btn.className = 'picker-btn';
    btn.innerHTML = `
      <span style="font-size:2rem">
        ${user.default_lang === 'korean' ? '🇰🇷' : user.default_lang === 'spanish' ? '🇪🇸' : '🌐'}
      </span>
      <span>${user.display_name}</span>
      <span class="lang-tag">${langLabel(user.default_lang)}</span>
    `;
    btn.addEventListener('click', () => startSession(user));
    container.appendChild(btn);
  });

  showView('view-picker');
}

function langLabel(lang) {
  return { korean: 'Korean', spanish: 'Spanish' }[lang] || lang;
}

async function startSession(user) {
  currentUser = user;
  localStorage.setItem('langlab_user', user.name);
  buildAppBar(user);
  showView('view-app');

  // Init modules (once per user)
  if (initializedFor !== user.id) {
    await initSpeech(user.default_lang === 'korean' ? 'ko-KR' : 'es-ES');
    initFlashcards(user);
    initLesson(user);
    if (user.default_lang === 'spanish' || true) initTutor(user);  // both users
    initVocab(user);
    initProgress(user);
    initializedFor = user.id;
  }

  const defaultView = user.default_lang === 'korean' ? 'view-player' : 'view-lessons';
  await navigate(defaultView);
}

// ── app bar ───────────────────────────────────────────────────────────────────

function buildAppBar(user) {
  const nav = document.getElementById('app-nav');
  nav.innerHTML = '';

  const views = [
    { id: 'view-player',     label: 'Player',     langs: ['korean'] },
    { id: 'view-lessons',    label: 'Lessons',    langs: ['spanish', 'korean'] },
    { id: 'view-tutor',      label: 'Tutor',      langs: ['spanish', 'korean'] },
    { id: 'view-flashcards', label: 'Flashcards', langs: ['korean', 'spanish'] },
    { id: 'view-vocab',      label: 'Vocab',      langs: ['korean', 'spanish'] },
    { id: 'view-progress',   label: 'Progress',   langs: ['korean', 'spanish'] },
  ].filter(v => v.langs.includes(user.default_lang));

  views.forEach(v => {
    const btn = document.createElement('button');
    btn.className    = 'nav-btn';
    btn.dataset.view = v.id;
    btn.textContent  = v.label;
    btn.addEventListener('click', () => navigate(v.id));
    nav.appendChild(btn);
  });

  document.getElementById('user-chip').textContent = user.display_name;
  document.getElementById('user-chip').addEventListener('click', switchUser);
}

// ── routing ───────────────────────────────────────────────────────────────────

async function navigate(viewId) {
  // Release mic when leaving tutor
  if (viewId !== 'view-tutor') releaseMic();

  showView(viewId);

  if (viewId === 'view-player' && currentUser) {
    await initPlayer(currentUser);
  } else if (viewId === 'view-lessons') {
    onLessonVisible();
  } else if (viewId === 'view-tutor') {
    onTutorVisible();
  }
}

// ── global controls ───────────────────────────────────────────────────────────

window.switchUser = function () {
  currentUser    = null;
  initializedFor = null;
  localStorage.removeItem('langlab_user');
  showPicker();
};

window.toggleDark = function () {
  document.body.classList.toggle('dark');
  localStorage.setItem('langlab_dark', document.body.classList.contains('dark') ? '1' : '0');
};

window.setPlayerView = setPlayerView;
window.openModal     = () => document.getElementById('modalOverlay').classList.add('visible');
window.closeModal    = () => document.getElementById('modalOverlay').classList.remove('visible');

// ── helpers ───────────────────────────────────────────────────────────────────

async function fetchUsers() {
  const res = await fetch('/api/users');
  if (!res.ok) throw new Error('Failed to load users');
  return res.json();
}

// ── boot ──────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', init);
