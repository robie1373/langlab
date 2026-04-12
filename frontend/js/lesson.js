/**
 * AI Lesson module — language-aware.
 * Generates personalized lessons via Gemini and walks through phases.
 */

import { generate, parseJSON, hasApiKey } from './gemini.js';
import { speak, setSpeechLang } from './speech.js';
import { showToast, escapeHtml, showLoading } from './ui.js';
import { checkAchievements } from './progress.js';

let _user        = null;
let _lessonData  = null;
let _currentPhase = 0;
let _sessionId   = null;

// ── phase list ────────────────────────────────────────────────────────────────

function getPhases() {
  return _user?.default_lang === 'spanish'
    ? ['vocab', 'grammar', 'dialogue', 'culture', 'summary']
    : ['vocab', 'grammar', 'reading',  'culture', 'summary'];
}

// ── topics ────────────────────────────────────────────────────────────────────

const KOREAN_TOPICS = [
  '인사 — 만남과 헤어짐',
  '가족 소개',
  '날씨 이야기',
  '음식 주문하기',
  '쇼핑',
  '길 묻기',
  '직업과 일상',
  '취미와 여가',
  '집 묘사하기',
  '시간과 날짜',
];

const SPANISH_TOPICS = [
  'La vida cotidiana en España',
  'Viajes por España',
  'La gastronomía española',
  'El arte y la cultura',
  'Relaciones personales',
  'El mundo laboral',
  'Salud y bienestar',
  'La naturaleza y el medio ambiente',
  'Tradiciones y celebraciones',
  'Literatura y cine español',
];

function pickTopic(lang) {
  const pool = lang === 'spanish' ? SPANISH_TOPICS : KOREAN_TOPICS;
  return pool[Math.floor(Math.random() * pool.length)];
}

// ── prompts ───────────────────────────────────────────────────────────────────

function buildKoreanPrompt(topic) {
  return `Generate a Korean lesson for a beginner who just finished Pimsleur Unit 1.

Topic: "${topic}"

CRITICAL RULES:
- NEVER use romanization. Korean text uses 한글 only.
- All Korean text must be 한글.
- Keep sentences short and simple.

Return ONLY valid JSON with this exact structure:
{
  "title": "Lesson title in Korean",
  "topic": "${topic}",
  "vocab": [
    { "word": "한글", "translation": "English meaning", "example": "Short Korean sentence" }
  ],
  "grammar": {
    "title": "Grammar concept name",
    "explanation": "English explanation with Korean examples",
    "examples": [{ "korean": "Korean sentence in 한글", "english": "English translation" }]
  },
  "reading": {
    "title": "Passage title in Korean",
    "text": "Short passage in Korean (5-8 sentences, beginner vocabulary, 한글 only)",
    "translation": "English translation of the full passage"
  },
  "culture": {
    "title": "Culture note title",
    "content": "2-3 paragraphs about Korean culture related to the topic (in English, with Korean terms in 한글 where appropriate)",
    "funFact": "One interesting Korean culture fact"
  }
}

Requirements:
- 6-8 vocab words, 한글 only — NO romanization
- Grammar: one clear beginner concept (topic markers 은/는, polite endings -요, etc.)
- Reading: 5-8 sentences, very simple vocabulary, 한글 only
- NO romanization anywhere in the response`;
}

function buildSpanishPrompt(topic) {
  return `Generate a Castilian Spanish lesson for an intermediate (B1-B2) female learner.

Topic: "${topic}"

Return ONLY valid JSON:
{
  "title": "Lesson title in Spanish",
  "topic": "${topic}",
  "vocab": [
    { "word": "word", "translation": "English", "example": "Castilian example sentence", "gender": "m or f if noun" }
  ],
  "grammar": {
    "title": "Grammar concept",
    "explanation": "Clear explanation in English with Spanish examples",
    "examples": [{ "spanish": "example", "english": "translation" }]
  },
  "dialogue": {
    "title": "Dialogue scenario title",
    "context": "Brief scene description",
    "lines": [{ "speaker": "Name", "text": "Dialogue line", "translation": "English" }]
  },
  "culture": {
    "title": "Culture note title",
    "content": "2-3 paragraphs about Spain and the topic (in Spanish with key terms explained)",
    "funFact": "Fun fact in Spanish"
  }
}

Requirements:
- 8-10 vocab words, Castilian Spanish (vosotros, not ustedes)
- Grammar: intermediate concept (subjunctive, conditionals, etc.)
- Dialogue: 8-10 lines, realistic Castilian setting, click to hear pronunciation
- Culture: Spain-specific, not Latin American`;
}

// ── session logging ───────────────────────────────────────────────────────────

async function logSession() {
  try {
    const res = await fetch('/api/sessions', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id:      _user.id,
        language:     _user.default_lang,
        session_type: 'ai_lesson',
      }),
    });
    const data = await res.json();
    _sessionId = data.id;
    checkAchievements(_user.id);
  } catch { /* non-critical */ }
}

// ── public API ────────────────────────────────────────────────────────────────

export function initLesson(user) {
  _user = user;
  document.getElementById('btn-lesson-start').addEventListener('click', generateLesson);
  document.getElementById('btn-lesson-back').addEventListener('click', prevPhase);
  document.getElementById('btn-lesson-next').addEventListener('click', nextPhase);
}

export function onLessonVisible() {
  if (!_lessonData) showStartScreen();
}

// ── screens ───────────────────────────────────────────────────────────────────

function showStartScreen() {
  document.getElementById('lesson-start').classList.remove('hidden');
  document.getElementById('lesson-content').classList.add('hidden');
  document.getElementById('lesson-nav').classList.add('hidden');
  document.getElementById('lesson-phase-label').textContent = '—';
  document.getElementById('lesson-progress-fill').style.width = '0%';
}

async function generateLesson() {
  if (!hasApiKey()) { showToast('No Gemini API key configured'); return; }

  const lang = _user.default_lang;
  setSpeechLang(lang === 'korean' ? 'ko-KR' : 'es-ES');

  document.getElementById('lesson-start').classList.add('hidden');
  const content = document.getElementById('lesson-content');
  content.classList.remove('hidden');
  document.getElementById('lesson-nav').classList.add('hidden');

  const topic  = pickTopic(lang);
  const prompt = lang === 'spanish' ? buildSpanishPrompt(topic) : buildKoreanPrompt(topic);
  const sysMsg = lang === 'spanish'
    ? 'You are a Castilian Spanish teaching assistant. Respond with valid JSON only.'
    : 'You are a Korean language teaching assistant. Respond with valid JSON only. Never use romanization.';

  showLoading(content, lang === 'spanish'
    ? 'Generando tu lección personalizada…'
    : '학습 자료를 생성하고 있습니다…');

  try {
    const raw = await generate(prompt, { systemInstruction: sysMsg, temperature: 0.85, maxTokens: 4096 });
    _lessonData   = parseJSON(raw);
    _currentPhase = 0;
    await logSession();
    document.getElementById('lesson-nav').classList.remove('hidden');
    renderPhase();
  } catch (err) {
    content.innerHTML = `<div class="lesson-error">
      <p>Could not generate lesson: ${escapeHtml(err.message)}</p>
      <button class="lesson-start-btn" id="btn-lesson-retry">Try again</button>
    </div>`;
    document.getElementById('btn-lesson-retry').addEventListener('click', generateLesson);
  }
}

// ── phase nav ─────────────────────────────────────────────────────────────────

function nextPhase() {
  const phases = getPhases();
  if (_currentPhase < phases.length - 1) { _currentPhase++; renderPhase(); }
}

function prevPhase() {
  if (_currentPhase > 0) { _currentPhase--; renderPhase(); }
}

// ── rendering ─────────────────────────────────────────────────────────────────

const PHASE_LABELS = {
  vocab:    { korean: '어휘', spanish: 'Vocabulario' },
  grammar:  { korean: '문법', spanish: 'Gramática' },
  reading:  { korean: '읽기', spanish: 'Lectura' },
  dialogue: { korean: '대화', spanish: 'Diálogo' },
  culture:  { korean: '문화', spanish: 'Cultura' },
  summary:  { korean: '완료', spanish: 'Resumen' },
};

function renderPhase() {
  const phases = getPhases();
  const phase  = phases[_currentPhase];
  const lang   = _user?.default_lang || 'korean';
  const pct    = ((_currentPhase + 1) / phases.length) * 100;

  document.getElementById('lesson-progress-fill').style.width = `${pct}%`;
  document.getElementById('lesson-phase-label').textContent =
    PHASE_LABELS[phase]?.[lang] || phase;

  const backBtn = document.getElementById('btn-lesson-back');
  const nextBtn = document.getElementById('btn-lesson-next');
  backBtn.disabled   = _currentPhase === 0;
  nextBtn.textContent = _currentPhase === phases.length - 1 ? 'Finish' : 'Next →';

  const content = document.getElementById('lesson-content');
  switch (phase) {
    case 'vocab':    renderVocab(content);    break;
    case 'grammar':  renderGrammar(content);  break;
    case 'reading':  renderReading(content);  break;
    case 'dialogue': renderDialogue(content); break;
    case 'culture':  renderCulture(content);  break;
    case 'summary':  renderSummary(content);  break;
  }
}

function renderVocab(el) {
  const v = _lessonData.vocab || [];
  el.innerHTML = `
    <div class="lesson-phase">
      <h3 class="phase-title">${escapeHtml(_lessonData.title || '')}</h3>
      <p class="phase-hint">Tap a card to hear it spoken.</p>
      <div class="lesson-vocab-grid">
        ${v.map((item, i) => `
          <div class="lesson-vocab-card" data-idx="${i}">
            <div class="lv-word">${escapeHtml(item.word)}${item.gender ? `<small class="lv-gender">(${escapeHtml(item.gender)})</small>` : ''}</div>
            <div class="lv-translation">${escapeHtml(item.translation)}</div>
            ${item.example ? `<div class="lv-example">${escapeHtml(item.example)}</div>` : ''}
          </div>
        `).join('')}
      </div>
    </div>`;

  el.querySelectorAll('.lesson-vocab-card').forEach(card => {
    card.addEventListener('click', () => {
      const item = v[parseInt(card.dataset.idx)];
      speak(item.example || item.word);
    });
  });
}

function renderGrammar(el) {
  const g = _lessonData.grammar || {};
  el.innerHTML = `
    <div class="lesson-phase">
      <h3 class="phase-title">${escapeHtml(g.title || '')}</h3>
      <div class="grammar-box">
        <p class="grammar-explanation">${escapeHtml(g.explanation || '').replace(/\n/g, '<br>')}</p>
        ${(g.rules || []).map(r => `<div class="grammar-rule">${escapeHtml(r)}</div>`).join('')}
        <div class="grammar-examples">
          ${(g.examples || []).map(ex => {
            const src = ex.korean || ex.spanish || '';
            const eng = ex.english || ex.translation || '';
            return `<div class="grammar-example clickable" data-text="${escapeHtml(src)}">
              <span class="ge-src">${escapeHtml(src)}</span>
              <span class="ge-eng">${escapeHtml(eng)}</span>
            </div>`;
          }).join('')}
        </div>
      </div>
    </div>`;

  el.querySelectorAll('.grammar-example.clickable').forEach(ex => {
    ex.addEventListener('click', () => speak(ex.dataset.text));
  });
}

function renderReading(el) {
  const r = _lessonData.reading || {};
  el.innerHTML = `
    <div class="lesson-phase">
      <h3 class="phase-title">${escapeHtml(r.title || '')}</h3>
      <div class="reading-passage">${escapeHtml(r.text || '').replace(/\n/g, '<br>')}</div>
      <div class="reading-actions">
        <button class="reading-btn" id="btn-read-aloud">▶ Read aloud</button>
      </div>
      <details class="reading-translation">
        <summary>Show English translation</summary>
        <p>${escapeHtml(r.translation || '')}</p>
      </details>
    </div>`;

  document.getElementById('btn-read-aloud')
    .addEventListener('click', () => speak(r.text || ''));
}

function renderDialogue(el) {
  const d = _lessonData.dialogue || {};
  el.innerHTML = `
    <div class="lesson-phase">
      <h3 class="phase-title">${escapeHtml(d.title || '')}</h3>
      <p class="phase-hint">${escapeHtml(d.context || '')}</p>
      <div class="dialogue-lines">
        ${(d.lines || []).map((line, i) => `
          <div class="dialogue-line ${i % 2 === 0 ? 'side-a' : 'side-b'}" data-text="${escapeHtml(line.text)}">
            <span class="dl-speaker">${escapeHtml(line.speaker)}</span>
            <div class="dl-content">
              <div class="dl-text">${escapeHtml(line.text)}</div>
              ${line.translation ? `<div class="dl-en">${escapeHtml(line.translation)}</div>` : ''}
            </div>
          </div>
        `).join('')}
      </div>
    </div>`;

  el.querySelectorAll('.dialogue-line').forEach(line => {
    line.addEventListener('click', () => speak(line.dataset.text));
  });
}

function renderCulture(el) {
  const c = _lessonData.culture || {};
  el.innerHTML = `
    <div class="lesson-phase">
      <div class="culture-card">
        <h3 class="phase-title">${escapeHtml(c.title || 'Culture')}</h3>
        <div class="culture-content">${escapeHtml(c.content || '').replace(/\n/g, '<br>')}</div>
        ${c.funFact ? `<div class="culture-fact">💡 ${escapeHtml(c.funFact)}</div>` : ''}
      </div>
    </div>`;
}

function renderSummary(el) {
  const lang    = _user?.default_lang || 'korean';
  const vocabN  = (_lessonData.vocab || []).length;
  el.innerHTML = `
    <div class="lesson-phase lesson-summary">
      <div class="summary-check">✓</div>
      <h3>${lang === 'spanish' ? '¡Lección completada!' : '수업 완료!'}</h3>
      <p class="summary-topic">${escapeHtml(_lessonData.topic || _lessonData.title || '')}</p>
      <div class="summary-stats">
        <div class="summary-stat">
          <span class="ss-num">${vocabN}</span>
          <span class="ss-label">${lang === 'spanish' ? 'palabras' : '단어'}</span>
        </div>
      </div>
      <button class="lesson-start-btn" id="btn-new-lesson">New lesson</button>
    </div>`;

  document.getElementById('btn-new-lesson').addEventListener('click', () => {
    _lessonData = null;
    _sessionId  = null;
    showStartScreen();
  });
}
