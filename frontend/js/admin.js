/**
 * Admin / Library view.
 * Handles vocab import (.apkg) and lesson ingest (VTT + MP3).
 */

let _users = [];

export async function initAdmin(users) {
  _users = users;
  _populateUserSelects();
  await _refreshStats();
  _bindHandlers();
}

// ── populate user dropdowns ────────────────────────────────────────────────

function _populateUserSelects() {
  ['admin-vocab-user', 'admin-lesson-user'].forEach(id => {
    const sel = document.getElementById(id);
    sel.innerHTML = _users.map(u =>
      `<option value="${u.id}">${u.display_name}</option>`
    ).join('');
  });

  // Default lesson-lang to Spanish for Anna (user 2) when she's selected
  document.getElementById('admin-lesson-user').addEventListener('change', _syncLessonLang);
  document.getElementById('admin-vocab-user').addEventListener('change', _syncVocabLang);
  _syncLessonLang();
  _syncVocabLang();
}

function _syncLessonLang() {
  const uid  = parseInt(document.getElementById('admin-lesson-user').value);
  const user = _users.find(u => u.id === uid);
  if (user) document.getElementById('admin-lesson-lang').value = user.default_lang;
}

function _syncVocabLang() {
  const uid  = parseInt(document.getElementById('admin-vocab-user').value);
  const user = _users.find(u => u.id === uid);
  if (user) document.getElementById('admin-vocab-lang').value = user.default_lang;
}

// ── library stats ─────────────────────────────────────────────────────────

async function _refreshStats() {
  try {
    const data = await fetch('/api/admin/library').then(r => r.json());

    // Vocab stats per user
    _users.forEach(u => {
      const info = data.vocab[String(u.id)];
      if (!info) return;
      const uid  = parseInt(document.getElementById('admin-vocab-user').value);
      if (uid === u.id) {
        document.getElementById('admin-vocab-stat').textContent =
          `${info.count.toLocaleString()} words in ${info.name}'s deck`;
      }
    });
    _updateVocabStat(data);

    // Lesson stats
    const counts = Object.entries(data.lessons);
    const lessonLang = document.getElementById('admin-lesson-lang').value;
    const n = data.lessons[lessonLang] || 0;
    document.getElementById('admin-lesson-stat').textContent =
      n === 0 ? 'No lessons loaded' : `${n} ${lessonLang} lesson${n !== 1 ? 's' : ''} loaded`;
  } catch { /* server may not be running */ }
}

function _updateVocabStat(data) {
  const uid  = parseInt(document.getElementById('admin-vocab-user').value);
  const info = data.vocab[String(uid)];
  if (info) {
    document.getElementById('admin-vocab-stat').textContent =
      `${info.count.toLocaleString()} words in ${info.name}'s deck`;
  }
}

// ── log ───────────────────────────────────────────────────────────────────

function _log(msg, type = 'info') {
  const log = document.getElementById('admin-log');
  const div = document.createElement('div');
  div.className = `log-line log-${type}`;
  div.textContent = `${new Date().toLocaleTimeString()} — ${msg}`;
  log.prepend(div);
  // Keep last 20 lines
  while (log.children.length > 20) log.removeChild(log.lastChild);
}

// ── drop zone helpers ─────────────────────────────────────────────────────

function _bindDropZone(zoneId, inputId, nameId, { multiple = false } = {}) {
  const zone  = document.getElementById(zoneId);
  const input = document.getElementById(inputId);
  const nameEl = document.getElementById(nameId);

  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    const files = Array.from(e.dataTransfer.files);
    _setFiles(input, nameEl, files);
  });
  input.addEventListener('change', () => {
    _setFiles(input, nameEl, Array.from(input.files));
  });
}

function _setFiles(input, nameEl, files) {
  if (!files.length) return;
  // Assign to the file input via DataTransfer
  const dt = new DataTransfer();
  files.forEach(f => dt.items.add(f));
  input.files = dt.files;
  nameEl.textContent = files.length === 1
    ? files[0].name
    : `${files.length} files selected`;
}

// ── event handlers ────────────────────────────────────────────────────────

function _bindHandlers() {
  _bindDropZone('admin-apkg-zone', 'admin-apkg-file', 'admin-apkg-name');
  _bindDropZone('admin-vtt-zone',  'admin-vtt-files', 'admin-vtt-names', { multiple: true });

  // Re-sync lang dropdowns when user changes
  document.getElementById('admin-vocab-user').addEventListener('change', async () => {
    _syncVocabLang();
    const data = await fetch('/api/admin/library').then(r => r.json()).catch(() => ({}));
    if (data.vocab) _updateVocabStat(data);
  });
  document.getElementById('admin-lesson-user').addEventListener('change', _syncLessonLang);
  document.getElementById('admin-lesson-lang').addEventListener('change', _refreshStats);

  document.getElementById('admin-import-btn').addEventListener('click', _doImportApkg);
  document.getElementById('admin-ingest-btn').addEventListener('click', _doIngestVtt);
}

async function _doImportApkg() {
  const file = document.getElementById('admin-apkg-file').files[0];
  if (!file) { _log('No .apkg file selected.', 'warn'); return; }

  const user_id   = document.getElementById('admin-vocab-user').value;
  const language  = document.getElementById('admin-vocab-lang').value;
  const deck_name = document.getElementById('admin-deck-name').value.trim();

  const btn = document.getElementById('admin-import-btn');
  btn.disabled = true;
  btn.textContent = 'Importing…';
  _log(`Importing ${file.name}…`);

  const form = new FormData();
  form.append('user_id',   user_id);
  form.append('language',  language);
  form.append('deck_name', deck_name);
  form.append('file', file, file.name);

  try {
    const res  = await fetch('/api/admin/import-apkg', { method: 'POST', body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || res.statusText);
    _log(`✓ Imported ${data.imported} words into "${data.deck}" (${data.skipped} skipped).`, 'ok');
    await _refreshStats();
  } catch (e) {
    _log(`✗ ${e.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Import Vocab';
  }
}

async function _doIngestVtt() {
  const files = Array.from(document.getElementById('admin-vtt-files').files);
  if (!files.length) { _log('No VTT files selected.', 'warn'); return; }

  const vtts = files.filter(f => f.name.toLowerCase().endsWith('.vtt'));
  if (!vtts.length) { _log('No .vtt files in selection.', 'warn'); return; }

  const language = document.getElementById('admin-lesson-lang').value;
  const user_id  = document.getElementById('admin-lesson-user').value;

  const btn = document.getElementById('admin-ingest-btn');
  btn.disabled = true;
  btn.textContent = 'Ingesting…';
  _log(`Ingesting ${vtts.length} VTT file${vtts.length !== 1 ? 's' : ''}…`);

  const form = new FormData();
  form.append('language', language);
  form.append('user_id',  user_id);
  files.forEach(f => form.append('files', f, f.name));

  try {
    const res  = await fetch('/api/admin/ingest-vtt', { method: 'POST', body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || res.statusText);
    _log(`✓ ${data.lessons} lesson${data.lessons !== 1 ? 's' : ''} added, ${data.words} words extracted.`, 'ok');
    await _refreshStats();
  } catch (e) {
    _log(`✗ ${e.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Ingest Lessons';
  }
}
