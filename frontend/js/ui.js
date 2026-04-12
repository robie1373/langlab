/**
 * Shared UI helpers — toasts, modals, view switching.
 */

export function showView(id) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  const el = document.getElementById(id);
  if (el) {
    el.classList.add('active');
    // Re-activate any .view ancestors so nested views stay visible
    let p = el.parentElement;
    while (p) {
      if (p.classList && p.classList.contains('view')) p.classList.add('active');
      p = p.parentElement;
    }
  }

  // Update active state on both desktop nav and mobile menu buttons
  document.querySelectorAll('.nav-btn[data-view], .mobile-menu-btn[data-view]').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.view === id);
  });
}

export function showToast(msg, duration = 2500) {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const el = document.createElement('div');
  el.className = 'toast';
  el.innerHTML = `<span class="toast-body"><span class="toast-title">${msg}</span></span>`;
  container.appendChild(el);
  setTimeout(() => el.remove(), duration + 400);
}

export function escapeHtml(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}

export function showLoading(el, msg = 'Loading…') {
  el.innerHTML = `<div class="loading-state">
    <div class="loading-spinner"></div>
    <p>${escapeHtml(msg)}</p>
  </div>`;
}
