/**
 * Toast notification system.
 * showToast() is already used by other modules — this file adds
 * achievement-specific showAchievement() and showXP().
 */

const TOAST_DURATION = 4000; // ms before auto-dismiss

export function showToast(message, type = '') {
  const el = document.createElement('div');
  el.className = `toast ${type}`.trim();
  el.innerHTML = `<span class="toast-body"><span class="toast-title">${message}</span></span>`;
  _mount(el);
}

export function showAchievement(badge) {
  const el = document.createElement('div');
  el.className = 'toast achievement';
  el.innerHTML = `
    <span class="toast-icon">${badge.icon ?? '🏅'}</span>
    <span class="toast-body">
      <span class="toast-title">${badge.name}</span>
      <span class="toast-desc">${badge.desc}</span>
    </span>`;
  _mount(el);
}

export function showXP(points, label = '') {
  const el = document.createElement('div');
  el.className = 'toast xp';
  el.innerHTML = `
    <span class="toast-icon">⚡</span>
    <span class="toast-body">
      <span class="toast-title">+${points.toLocaleString()} XP</span>
      ${label ? `<span class="toast-desc">${label}</span>` : ''}
    </span>`;
  _mount(el);
}

export function showMastered(word, rarity) {
  const icons   = { fundamental: '⭐', essential: '💜', interesting: '💚', niche: '⬜' };
  const labels  = { fundamental: 'Fundamental', essential: 'Essential', interesting: 'Interesting', niche: 'Niche' };
  const el = document.createElement('div');
  el.className  = `toast achievement ${rarity ?? ''}`;
  el.innerHTML  = `
    <span class="toast-icon">${icons[rarity] ?? '✨'}</span>
    <span class="toast-body">
      <span class="toast-title">${word} — collected!</span>
      <span class="toast-desc">${labels[rarity] ?? ''} word known cold</span>
    </span>`;
  _mount(el);
}

function _mount(el) {
  const container = document.getElementById('toast-container');
  if (!container) return;
  container.appendChild(el);
  setTimeout(() => el.remove(), TOAST_DURATION + 500);
}
