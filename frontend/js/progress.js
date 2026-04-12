/**
 * Progress & Rewards view — streaks, heat map, badges, session history.
 */

import { showAchievement } from './toast.js';

let _user = null;

export async function initProgress(user) {
  _user = user;
  await render();
}

async function render() {
  try {
    const [progress, achData, vocab, sessions] = await Promise.all([
      fetch(`/api/progress/${_user.id}`).then(r => r.json()),
      fetch(`/api/achievements/${_user.id}`).then(r => r.json()),
      fetch(`/api/vocab/${_user.id}`).then(r => r.json()),
      fetch(`/api/sessions/${_user.id}`).then(r => r.json()),
    ]);
    renderStreak(progress);
    renderHeatmap(progress.heatmap);
    renderBadges(achData);
    renderStats(vocab);
    renderSessions(sessions);
  } catch (err) {
    document.getElementById('progress-stats').innerHTML =
      `<p class="progress-error">Failed to load progress: ${err.message}</p>`;
  }
}

// ── Streak row ────────────────────────────────────────────────────────────────

function renderStreak(p) {
  const { streak, best_streak, total_days, xp_total } = p;

  const isNewBest = streak > 0 && streak >= best_streak;
  const streakLabel = streak === 1 ? '1 day' : `${streak} days`;
  const subtext = streak === 0
    ? 'Start a new streak today'
    : isNewBest && streak > 1
      ? '🏅 New personal best!'
      : `Best: ${best_streak} days`;

  document.getElementById('pr-streak-row').innerHTML = `
    <div class="pr-streak-card ${streak > 0 ? 'highlight' : ''}">
      <span class="pr-sc-number">${streak > 0 ? streakLabel : '—'}</span>
      <span class="pr-sc-label">Current streak</span>
      <span class="pr-sc-sub">${subtext}</span>
    </div>
    <div class="pr-streak-card">
      <span class="pr-sc-number">${total_days}</span>
      <span class="pr-sc-label">Total days studied</span>
      <span class="pr-sc-sub">Always a personal record</span>
    </div>
    <div class="pr-streak-card">
      <span class="pr-sc-number pr-xp-label">${(xp_total ?? 0).toLocaleString()}</span>
      <span class="pr-sc-label">Total XP</span>
    </div>`;
}

// ── Heat map ─────────────────────────────────────────────────────────────────

function renderHeatmap(heatmap) {
  const wrap = document.getElementById('pr-heatmap-wrap');

  // Build a 52-week grid ending today
  const today   = new Date();
  const dayOfWk = today.getDay(); // 0=Sun
  // Start from the Sunday 51 full weeks ago
  const start   = new Date(today);
  start.setDate(today.getDate() - dayOfWk - 51 * 7);

  const weeks = [];
  let cur = new Date(start);
  while (cur <= today) {
    const week = [];
    for (let d = 0; d < 7; d++) {
      const key   = cur.toISOString().slice(0, 10);
      const count = heatmap[key] ?? 0;
      const isFuture = cur > today;
      week.push({ key, count, isFuture });
      cur.setDate(cur.getDate() + 1);
    }
    weeks.push(week);
  }

  const cells = weeks.map(week => `
    <div class="pr-hm-week">
      ${week.map(({ key, count, isFuture }) => isFuture
        ? `<div class="pr-hm-day" style="opacity:0"></div>`
        : `<div class="pr-hm-day" data-count="${Math.min(count, 4)}" title="${key}: ${count} session${count !== 1 ? 's' : ''}"></div>`
      ).join('')}
    </div>`).join('');

  wrap.innerHTML = `
    <div class="pr-heatmap-title">Study history — past year</div>
    <div class="pr-heatmap">${cells}</div>`;
}

// ── Badge grid ────────────────────────────────────────────────────────────────

function renderBadges({ earned, badge_defs, badge_groups, group_labels }) {
  const earnedSet = new Set(earned);
  const byGroup   = {};
  badge_defs.forEach(b => {
    (byGroup[b.group] = byGroup[b.group] ?? []).push(b);
  });

  const earnedCount = earned.length;
  const totalCount  = badge_defs.length;

  let html = `<div class="pr-badge-group-title">Badges — ${earnedCount} / ${totalCount}</div>`;
  for (const group of badge_groups) {
    const badges = byGroup[group];
    if (!badges?.length) continue;
    html += `<div class="pr-badge-group-title">${group_labels[group]}</div>
             <div class="pr-badge-row">`;
    for (const b of badges) {
      const cls = earnedSet.has(b.key) ? 'earned' : 'unearned';
      html += `<div class="pr-badge ${cls}" title="${b.desc}">
        <span class="badge-icon">${b.icon}</span>
        <span class="badge-name">${b.name}</span>
      </div>`;
    }
    html += '</div>';
  }

  document.getElementById('pr-badges-wrap').innerHTML = html;
}

// ── Vocab stats ───────────────────────────────────────────────────────────────

function renderStats(vocab) {
  const counts = [0, 0, 0, 0];
  let mastered = 0;
  vocab.forEach(w => {
    counts[Math.min(w.state, 3)]++;
    if (w.state === 2 && w.stability >= 21 && w.reps >= 3) mastered++;
  });
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
      <div class="progress-card">
        <span class="pc-num" style="color:var(--accent)">${mastered}</span>
        <span class="pc-label">Known cold</span>
      </div>
    </div>`;
}

// ── Session list ──────────────────────────────────────────────────────────────

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

// ── Real-time achievement check (called from other modules after actions) ─────

export async function checkAchievements(userId) {
  try {
    const res  = await fetch(`/api/achievements/check/${userId}`, { method: 'POST' });
    const data = await res.json();
    for (const badge of (data.awarded ?? [])) {
      showAchievement(badge);
    }
  } catch (_) { /* non-critical */ }
}
