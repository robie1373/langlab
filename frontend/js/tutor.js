/**
 * Conversational AI tutor — language-aware (Korean/Spanish).
 * Korean: Robie is a beginner; tutor responds in Korean + English, feedback in English.
 * Spanish: Anna; tutor responds in Castilian Spanish, English feedback.
 */

import { chat } from './gemini.js';
import { speak, listen, stopListening, stopSpeaking, isListening,
         isRecognitionSupported, setSpeechLang } from './speech.js';
import { showToast, escapeHtml } from './ui.js';

let _user         = null;
let _chatHistory  = [];
let _isProcessing = false;
let _micTimeout   = null;
const MIC_TIMEOUT = 60_000;

// ── scenarios ─────────────────────────────────────────────────────────────────

const SPANISH_SCENARIOS = {
  free:     'Tienes una conversación libre con la estudiante. Habla de cualquier tema que surja.',
  cafe:     'Estás en una cafetería en Madrid. Eres la camarera. Toma el pedido y charla un poco.',
  market:   'Estás en el Mercado de San Miguel en Madrid. Eres una vendedora. Ayuda a la estudiante.',
  travel:   'Eres una amiga española que ayuda a planificar un viaje por España.',
  work:     'Eres la entrevistadora en una entrevista de trabajo en Barcelona.',
  doctor:   'Eres la recepcionista y luego la doctora en una consulta médica en Sevilla.',
  culture:  'Eres una amiga española apasionada por la cultura española.',
};

const KOREAN_SCENARIOS = {
  free:     '학생과 자유롭게 대화합니다. 어떤 주제도 좋습니다.',
  cafe:     '한국 카페에서 직원 역할을 합니다. 주문을 받고 간단한 대화를 나눕니다.',
  market:   '재래시장에서 상인 역할을 합니다. 학생이 물건을 사도록 도와줍니다.',
  phone:    '전화 통화 연습입니다. 상대방 역할을 합니다.',
  intro:    '처음 만나는 사람으로서 자기소개 연습을 합니다.',
  direction:'길을 안내해 드립니다. 학생이 길을 묻습니다.',
  restaurant: '한식당에서 종업원 역할을 합니다. 메뉴를 설명하고 주문을 받습니다.',
};

function getScenarios() {
  return _user?.default_lang === 'korean' ? KOREAN_SCENARIOS : SPANISH_SCENARIOS;
}

// ── system prompts ────────────────────────────────────────────────────────────

function getSystemPrompt(scenario) {
  if (_user?.default_lang === 'korean') {
    const scenarioDesc = KOREAN_SCENARIOS[scenario] || KOREAN_SCENARIOS.free;
    return `당신은 서울 출신의 한국어 선생님 지수입니다. 학생은 이제 막 배우기 시작한 초보자입니다.

중요한 규칙:
- 절대 로마자 표기(romanization)를 사용하지 마세요. 한글만 사용하세요.
- 매우 짧고 간단한 문장을 사용하세요 (초보자 수준).
- 응답 후 "---FEEDBACK---" 구분자를 추가하세요.
- 피드백은 영어로 작성하세요:
  GRAMMAR: [grammar corrections or "Good grammar!"]
  VOCAB: [vocabulary suggestions or "Good word choice!"]
  NOTE: [one encouraging comment in English]

시나리오: ${scenarioDesc}

응답 형식:
[한국어 응답 (매우 짧고 간단하게) + 괄호 안에 영어 번역]
---FEEDBACK---
GRAMMAR: [English]
VOCAB: [English]
NOTE: [English encouragement]`;

  } else {
    // Spanish (Anna)
    const scenarioDesc = SPANISH_SCENARIOS[scenario] || SPANISH_SCENARIOS.free;
    return `Eres una tutora nativa de español de Madrid llamada Elena. Hablas castellano.

REGLAS:
- Usa SIEMPRE castellano: vosotros/as, vocabulario español (ordenador, coche, vale, guay).
- Habla de forma natural y coloquial. Responde SIEMPRE en español.
- Si la estudiante habla en inglés, anímala a usar el español.
- Después de tu respuesta, añade "---FEEDBACK---" con:
  GRAMÁTICA: [correcciones o "Sin errores"]
  VOCABULARIO: [sugerencias o "Buen uso"]
  NOTA: [comentario de ánimo breve]

ESCENARIO: ${scenarioDesc}

Formato:
[Tu respuesta en español]
---FEEDBACK---
GRAMÁTICA: [...]
VOCABULARIO: [...]
NOTA: [...]`;
  }
}

// ── goodbye detection ─────────────────────────────────────────────────────────

const GOODBYE_PATTERNS_ES = [
  /\badios\b/i, /\badiós\b/i, /\bhasta luego\b/i, /\bnos vemos\b/i,
  /\bchao\b/i, /\bbuenas noches\b/i, /\bme voy\b/i,
];
const GOODBYE_PATTERNS_KO = [
  /안녕히 계세요/i, /안녕히 가세요/i, /잘 있어요/i, /다음에 봐요/i,
  /잘 가요/i, /또 봐요/i,
];

function isGoodbye(text) {
  const patterns = _user?.default_lang === 'korean' ? GOODBYE_PATTERNS_KO : GOODBYE_PATTERNS_ES;
  return patterns.some(p => p.test(text));
}

// ── public API ────────────────────────────────────────────────────────────────

export function initTutor(user) {
  _user = user;
  setSpeechLang(user.default_lang === 'korean' ? 'ko-KR' : 'es-ES');
  populateScenarios();

  document.getElementById('tutor-scenario')
    .addEventListener('change', () => resetChat());

  document.getElementById('btn-mic')
    .addEventListener('click', handleMicClick);

  const sendBtn   = document.getElementById('btn-send-tutor');
  const textInput = document.getElementById('tutor-text-input');

  sendBtn.addEventListener('click', () => submitText());
  textInput.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submitText(); }
  });

  document.getElementById('btn-end-convo')
    .addEventListener('click', endConversation);

  resetChat();
}

export function onTutorVisible() {
  document.getElementById('tutor-text-input')?.focus();
}

export function releaseMic() {
  stopListening();
  stopSpeaking();
  clearTimeout(_micTimeout);
  setMicStatus(false);
}

// ── internals ─────────────────────────────────────────────────────────────────

function populateScenarios() {
  const sel = document.getElementById('tutor-scenario');
  const scenarios = getScenarios();
  sel.innerHTML = Object.entries(scenarios)
    .map(([val, _]) => {
      const labels = {
        free: 'Free conversation', cafe: 'Café',
        market: 'Market', travel: 'Travel', work: 'Job interview',
        doctor: "Doctor's office", culture: 'Culture chat',
        phone: 'Phone call', intro: 'Self-introduction',
        direction: 'Directions', restaurant: 'Restaurant',
      };
      return `<option value="${val}">${labels[val] || val}</option>`;
    }).join('');
}

function submitText() {
  const input = document.getElementById('tutor-text-input');
  const text  = input.value.trim();
  if (text) { input.value = ''; handleStudentMessage(text); }
}

function setMicStatus(active) {
  const btn    = document.getElementById('btn-mic');
  const status = document.getElementById('mic-status');
  if (active) {
    btn.classList.add('recording');
    status.classList.remove('hidden');
  } else {
    btn.classList.remove('recording');
    status.classList.add('hidden');
    clearTimeout(_micTimeout);
  }
}

async function handleMicClick() {
  if (isListening()) { stopListening(); setMicStatus(false); return; }
  if (!isRecognitionSupported()) {
    showToast('Speech recognition not available in this browser (try Chrome)');
    return;
  }

  setMicStatus(true);
  _micTimeout = setTimeout(() => {
    if (isListening()) { stopListening(); setMicStatus(false); }
  }, MIC_TIMEOUT);

  try {
    const transcript = await listen({
      interimCallback: interim => {
        document.getElementById('tutor-text-input').value = interim;
        clearTimeout(_micTimeout);
        _micTimeout = setTimeout(() => {
          if (isListening()) { stopListening(); setMicStatus(false); }
        }, MIC_TIMEOUT);
      }
    });
    setMicStatus(false);
    if (transcript) {
      document.getElementById('tutor-text-input').value = '';
      handleStudentMessage(transcript);
    } else {
      showToast('No speech detected');
    }
  } catch (err) {
    setMicStatus(false);
    showToast('Mic error: ' + err.message);
  }
}

async function handleStudentMessage(text) {
  if (_isProcessing) return;
  _isProcessing = true;

  const chatArea = document.getElementById('tutor-chat');
  const welcome  = chatArea.querySelector('.chat-welcome');
  if (welcome) welcome.remove();

  document.getElementById('btn-end-convo').classList.remove('hidden');
  addMessage('student', text);

  const typingEl = addTypingIndicator();
  _chatHistory.push({ role: 'user', text });

  const scenario = document.getElementById('tutor-scenario').value || 'free';

  try {
    const response = await chat(_chatHistory, {
      systemInstruction: getSystemPrompt(scenario),
      temperature: 0.85,
    });

    const [conversational, feedbackRaw] = response.split('---FEEDBACK---');
    const reply = conversational.trim();
    _chatHistory.push({ role: 'assistant', text: reply });

    typingEl.remove();
    addMessage('tutor', reply);
    speak(reply);

    if (feedbackRaw?.trim()) showFeedback(feedbackRaw.trim());

    if (isGoodbye(text) || isGoodbye(reply)) {
      setTimeout(() => endConversation(), 3000);
    }
  } catch (err) {
    typingEl.remove();
    addMessage('tutor', `Error: ${err.message}`);
  }

  _isProcessing = false;
}

function addMessage(role, text) {
  const chatArea = document.getElementById('tutor-chat');
  const tutorName = _user?.default_lang === 'korean' ? '지수' : 'Elena';
  const avatar = role === 'tutor' ? tutorName[0] : (_user?.display_name?.[0] || 'U');
  const div = document.createElement('div');
  div.className = `chat-msg ${role}`;
  div.innerHTML = `
    <div class="chat-avatar">${escapeHtml(avatar)}</div>
    <div class="chat-bubble">${escapeHtml(text).replace(/\n/g, '<br>')}</div>`;
  chatArea.appendChild(div);
  chatArea.scrollTop = chatArea.scrollHeight;
}

function addTypingIndicator() {
  const chatArea = document.getElementById('tutor-chat');
  const div = document.createElement('div');
  div.className = 'chat-msg tutor';
  div.innerHTML = `
    <div class="chat-avatar">…</div>
    <div class="chat-bubble">
      <div class="typing-dots"><span></span><span></span><span></span></div>
    </div>`;
  chatArea.appendChild(div);
  chatArea.scrollTop = chatArea.scrollHeight;
  return div;
}

function showFeedback(raw) {
  const panel   = document.getElementById('tutor-feedback');
  const content = document.getElementById('feedback-content');
  panel.classList.remove('hidden');

  const lines = raw.split('\n').filter(l => l.trim());
  let html = '';

  for (const line of lines) {
    const [key, ...rest] = line.split(':');
    const val = rest.join(':').trim();
    const k   = key.trim().toUpperCase().replace('Á', 'A').replace('Ó', 'O');

    if (!val) continue;
    if (['GRAMMAR', 'GRAMATICA', 'GRAMÁTICA'].includes(k)) {
      if (!val.match(/^(sin errores|good grammar|perfecto)/i))
        html += `<div class="fb-item"><span class="fb-grammar">Grammar</span> ${escapeHtml(val)}</div>`;
    } else if (['VOCABULARIO', 'VOCAB'].includes(k)) {
      if (!val.match(/^(buen uso|good word)/i))
        html += `<div class="fb-item"><span class="fb-vocab">Vocab</span> ${escapeHtml(val)}</div>`;
    } else if (['NOTA', 'NOTE'].includes(k)) {
      if (val) html += `<div class="fb-note">${escapeHtml(val)}</div>`;
    }
  }

  if (!html) html = '<p class="fb-ok">Looks great!</p>';
  content.innerHTML = html;
}

function endConversation() {
  stopSpeaking();
  resetChat();
  showToast(_user?.default_lang === 'korean' ? '대화가 끝났습니다!' : '¡Conversación terminada!');
}

function resetChat() {
  _chatHistory = [];
  const chatArea = document.getElementById('tutor-chat');
  const lang = _user?.default_lang || 'korean';
  chatArea.innerHTML = `<div class="chat-welcome">
    <p>${lang === 'korean'
      ? '시나리오를 선택하고 마이크 버튼을 누르거나 아래에 입력하세요.'
      : 'Elige un escenario y pulsa el micrófono o escribe tu mensaje.'}</p>
  </div>`;
  document.getElementById('tutor-feedback').classList.add('hidden');
  document.getElementById('btn-end-convo').classList.add('hidden');
}
