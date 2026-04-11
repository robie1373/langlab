/**
 * Progress view — session history + vocabulary stats.
 */

let _user = null;

export async function initProgress(user) {
  _user = user;
  await render();
}

async function render() {
  try {
    const [sessions, vocab] = await Promise.all([
      fetch(`/api/sessions/${_user.id}`).then(r => r.json()),
      fetch(`/api/vocab/${_user.id}`).then(r => r.json()),
    ]);
    renderStats(vocab);
    renderSessions(sessions);
  } catch (err) {
    document.getElementById('progress-stats').innerHTML =
      `<p class="progress-error">Failed to load progress: ${err.message}</p>`;
  }
}

function renderStats(vocab) {
  const counts = [0, 0, 0, 0];
  vocab.forEach(w => { counts[Math.min(w.state, 3)]++; });
  const total = vocab.length;

  document.getElementById('progress-stats').innerHTML = `
    <div class="progress-cards">
      <div class="progress-card">
        <span class="pc-num">${total}</span>
        <span class="pc-label">Total words</span>
      </div>
      <div class="progress-card">
        <span class="pc-num state-new">${counts[0]}</span>
        <span class="pc-label">New</span>
      </div>
      <div class="progress-card">
        <span class="pc-num state-learning">${counts[1]}</span>
        <span class="pc-label">Learning</span>
      </div>
      <div class="progress-card">
        <span class="pc-num state-review">${counts[2]}</span>
        <span class="pc-label">Review</span>
      </div>
    </div>`;
}

function renderSessions(sessions) {
  if (sessions.length === 0) {
    document.getElementById('progress-sessions').innerHTML =
      '<p class="progress-empty">No sessions yet.</p>';
    return;
  }

  const SESSION_ICONS = {
    pimsleur:   '🎧',
    flashcard:  '📇',
    ai_lesson:  '📚',
    tutor:      '💬',
    free:       '✏️',
  };

  document.getElementById('progress-sessions').innerHTML = `
    <h3 class="progress-section-title">Recent Sessions</h3>
    <div class="session-list">
      ${sessions.slice(0, 50).map(s => {
        const icon = SESSION_ICONS[s.session_type] || '📝';
        const date = new Date(s.timestamp).toLocaleDateString(undefined, {
          month: 'short', day: 'numeric', year: 'numeric',
        });
        const time = new Date(s.timestamp).toLocaleTimeString(undefined, {
          hour: '2-digit', minute: '2-digit',
        });
        return `<div class="session-row">
          <span class="sr-icon">${icon}</span>
          <div class="sr-info">
            <span class="sr-type">${s.session_type.replace('_', ' ')}</span>
            ${s.lesson_path ? `<span class="sr-lesson">${s.lesson_path}</span>` : ''}
          </div>
          <div class="sr-when">
            <span class="sr-date">${date}</span>
            <span class="sr-time">${time}</span>
          </div>
        </div>`;
      }).join('')}
    </div>`;
}
