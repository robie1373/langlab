/**
 * Shared UI helpers — toasts, modals, view switching.
 */

export function showView(id) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  const el = document.getElementById(id);
  if (el) el.classList.add('active');

  // Update nav button state (only relevant when the app bar is visible)
  document.querySelectorAll('.nav-btn[data-view]').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.view === id);
  });
}

export function showToast(msg, duration = 2500) {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    Object.assign(container.style, {
      position: 'fixed', bottom: '72px', left: '50%',
      transform: 'translateX(-50%)', zIndex: '500',
      display: 'flex', flexDirection: 'column', gap: '8px',
      pointerEvents: 'none',
    });
    document.body.appendChild(container);
  }
  const toast = document.createElement('div');
  toast.textContent = msg;
  Object.assign(toast.style, {
    background: 'rgba(30,30,30,0.88)', color: '#fff',
    padding: '0.5rem 1rem', borderRadius: '6px',
    fontSize: '0.875rem', backdropFilter: 'blur(4px)',
    opacity: '1', transition: 'opacity 0.3s',
  });
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, duration);
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
