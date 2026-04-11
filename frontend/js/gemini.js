/**
 * Gemini REST API client — ported from Habla with LangLab adaptations:
 * - API key fetched from /api/config (server-injected) rather than localStorage
 * - Key cached in localStorage as fallback after first load
 */

const API_BASE     = 'https://generativelanguage.googleapis.com/v1beta/models';
const MODELS       = ['gemini-2.0-flash', 'gemini-1.5-flash'];
const MAX_RETRIES  = 3;
const BASE_DELAY   = 2000;
const LS_KEY       = 'langlab_gemini_key';

let _apiKey = localStorage.getItem(LS_KEY) || '';

export async function loadApiKey() {
  try {
    const res  = await fetch('/api/config');
    const data = await res.json();
    if (data.gemini_api_key) {
      _apiKey = data.gemini_api_key;
      localStorage.setItem(LS_KEY, _apiKey);
    }
  } catch { /* use cached key */ }
}

export function getApiKey()      { return _apiKey; }
export function setApiKey(key)   { _apiKey = key.trim(); localStorage.setItem(LS_KEY, _apiKey); }
export function hasApiKey()      { return _apiKey.length > 10; }

// ── retry / model-fallback wrapper ───────────────────────────────────────────

async function fetchWithRetry(buildRequest) {
  let lastError;
  for (const model of MODELS) {
    for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
      try {
        const { url, options } = buildRequest(model);
        const res = await fetch(url, options);
        if (res.ok) return { res, model };

        const err = await res.json().catch(() => ({}));
        const msg = err.error?.message || `API error ${res.status}`;
        if (res.status === 429) {
          await sleep(BASE_DELAY * 2 ** attempt);
          continue;
        }
        lastError = new Error(msg);
        break;
      } catch (e) {
        lastError = e;
        if (attempt < MAX_RETRIES - 1) await sleep(BASE_DELAY * 2 ** attempt);
      }
    }
  }
  throw lastError || new Error('All Gemini models failed');
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

// ── public API ────────────────────────────────────────────────────────────────

export async function generate(prompt, { systemInstruction, temperature = 0.8, maxTokens = 4096 } = {}) {
  const key = getApiKey();
  if (!key) throw new Error('No Gemini API key configured');

  const body = {
    contents: [{ parts: [{ text: prompt }] }],
    generationConfig: { temperature, maxOutputTokens: maxTokens },
  };
  if (systemInstruction) body.systemInstruction = { parts: [{ text: systemInstruction }] };

  const { res } = await fetchWithRetry(model => ({
    url:     `${API_BASE}/${model}:generateContent?key=${key}`,
    options: { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) },
  }));

  const data = await res.json();
  const text = data.candidates?.[0]?.content?.parts?.[0]?.text;
  if (!text) throw new Error('Empty response from Gemini');
  return text;
}

export async function generateStream(prompt, onChunk, { systemInstruction, temperature = 0.8, maxTokens = 4096 } = {}) {
  const key = getApiKey();
  if (!key) throw new Error('No Gemini API key configured');

  const body = {
    contents: [{ parts: [{ text: prompt }] }],
    generationConfig: { temperature, maxOutputTokens: maxTokens },
  };
  if (systemInstruction) body.systemInstruction = { parts: [{ text: systemInstruction }] };

  const { res } = await fetchWithRetry(model => ({
    url:     `${API_BASE}/${model}:streamGenerateContent?alt=sse&key=${key}`,
    options: { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) },
  }));

  const reader  = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer    = '';
  let fullText  = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      const s = line.slice(6).trim();
      if (!s || s === '[DONE]') continue;
      try {
        const chunk = JSON.parse(s).candidates?.[0]?.content?.parts?.[0]?.text || '';
        if (chunk) { fullText += chunk; onChunk(chunk, fullText); }
      } catch { /* skip */ }
    }
  }
  return fullText;
}

export async function chat(messages, { systemInstruction, temperature = 0.8, maxTokens = 2048 } = {}) {
  const key = getApiKey();
  if (!key) throw new Error('No Gemini API key configured');

  const contents = messages.map(m => ({
    role:  m.role === 'assistant' ? 'model' : 'user',
    parts: [{ text: m.text }],
  }));

  const body = { contents, generationConfig: { temperature, maxOutputTokens: maxTokens } };
  if (systemInstruction) body.systemInstruction = { parts: [{ text: systemInstruction }] };

  const { res } = await fetchWithRetry(model => ({
    url:     `${API_BASE}/${model}:generateContent?key=${key}`,
    options: { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) },
  }));

  const data = await res.json();
  return data.candidates?.[0]?.content?.parts?.[0]?.text || '';
}

export function parseJSON(text) {
  let s = text.trim();
  if (s.startsWith('```')) s = s.replace(/^```(?:json)?\s*\n?/, '').replace(/\n?```\s*$/, '');
  s = s.replace(/,\s*([\]}])/g, '$1');
  try { return JSON.parse(s); } catch {
    const m = s.match(/[\[{][\s\S]*[\]}]/);
    if (m) return JSON.parse(m[0].replace(/,\s*([\]}])/g, '$1'));
    throw new Error('Could not parse Gemini JSON response');
  }
}
