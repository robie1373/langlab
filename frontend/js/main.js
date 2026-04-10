/**
 * LangLab main entry point.
 * Handles user selection and top-level routing.
 */

import { showView, showToast } from './ui.js';
import { initPlayer, setView as setPlayerView } from './player.js';

let currentUser = null;

// ── startup ──────────────────────────────────────────────────────────────────

async function init() {
  // Restore dark mode
  if (localStorage.getItem('langlab_dark') === '1') {
    document.body.classList.add('dark');
  }

  // Check for saved user
  const savedUser = localStorage.getItem('langlab_user');
  if (savedUser) {
    try {
      const users = await fetchUsers();
      const user  = users.find(u => u.name === savedUser);
      if (user) {
        await startSession(user);
        return;
      }
    } catch (e) { /* fall through to picker */ }
  }

  showPicker();
}

// ── user picker ───────────────────────────────────────────────────────────────

async function showPicker() {
  let users = [];
  try {
    users = await fetchUsers();
  } catch (e) {
    showView('view-picker');
    return;
  }

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

  // Route to default view for this user
  await navigate(user.default_lang === 'korean' ? 'view-player' : 'view-lessons');
}

// ── app bar ───────────────────────────────────────────────────────────────────

function buildAppBar(user) {
  // Nav buttons — show relevant views for this user's language
  const nav = document.getElementById('app-nav');
  nav.innerHTML = '';

  const views = [
    { id: 'view-player',    label: 'Player',    langs: ['korean'] },
    { id: 'view-lessons',   label: 'Lessons',   langs: ['spanish', 'korean'] },
    { id: 'view-tutor',     label: 'Tutor',     langs: ['spanish'] },
    { id: 'view-flashcards',label: 'Flashcards',langs: ['korean','spanish'] },
    { id: 'view-vocab',     label: 'Vocab',     langs: ['korean'] },
    { id: 'view-progress',  label: 'Progress',  langs: ['korean','spanish'] },
  ].filter(v => v.langs.includes(user.default_lang));

  views.forEach(v => {
    const btn = document.createElement('button');
    btn.className    = 'nav-btn';
    btn.dataset.view = v.id;
    btn.textContent  = v.label;
    btn.addEventListener('click', () => navigate(v.id));
    nav.appendChild(btn);
  });

  // User chip
  document.getElementById('user-chip').textContent = user.display_name;
  document.getElementById('user-chip').addEventListener('click', switchUser);
}

async function navigate(viewId) {
  showView(viewId);

  if (viewId === 'view-player' && currentUser) {
    await initPlayer(currentUser);
  }
}

// ── controls wired in HTML ─────────────────────────────────────────────────────

window.switchUser = function () {
  currentUser = null;
  localStorage.removeItem('langlab_user');
  showPicker();
};

window.toggleDark = function () {
  document.body.classList.toggle('dark');
  localStorage.setItem('langlab_dark', document.body.classList.contains('dark') ? '1' : '0');
};

window.setPlayerView = setPlayerView;

window.openModal  = () => document.getElementById('modalOverlay').classList.add('visible');
window.closeModal = () => document.getElementById('modalOverlay').classList.remove('visible');

// ── helpers ───────────────────────────────────────────────────────────────────

async function fetchUsers() {
  const res = await fetch('/api/users');
  if (!res.ok) throw new Error('Failed to load users');
  return res.json();
}

// ── boot ──────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', init);
