/**
 * Web Speech API wrapper — language-configurable.
 * Default lang is set at init time; can be updated per-call.
 */

let recognition  = null;
let synthesis    = window.speechSynthesis;
let cachedVoice  = null;
let currentLang  = 'es-ES';
let speechRate   = 0.9;

export function setSpeechLang(lang)  { currentLang = lang; cachedVoice = null; }
export function setSpeechRate(rate)  { speechRate = rate; }
export function isRecognitionSupported() { return !!(window.SpeechRecognition || window.webkitSpeechRecognition); }
export function isSynthesisSupported()   { return !!window.speechSynthesis; }

function findVoice() {
  if (cachedVoice) return cachedVoice;
  const voices = synthesis.getVoices();
  cachedVoice  =
    voices.find(v => v.lang === currentLang && v.localService) ||
    voices.find(v => v.lang === currentLang) ||
    voices.find(v => v.lang.startsWith(currentLang.split('-')[0]));
  return cachedVoice;
}

export function initSpeech(lang) {
  if (lang) currentLang = lang;
  return new Promise(resolve => {
    if (synthesis.getVoices().length > 0) { findVoice(); resolve(); return; }
    synthesis.onvoiceschanged = () => { findVoice(); resolve(); };
    setTimeout(resolve, 2000);
  });
}

export function speak(text, { rate, lang, onEnd } = {}) {
  return new Promise(resolve => {
    if (!isSynthesisSupported()) { resolve(); return; }
    synthesis.cancel();
    const utt   = new SpeechSynthesisUtterance(text);
    const voice = findVoice();
    if (voice) utt.voice = voice;
    utt.lang    = lang || currentLang;
    utt.rate    = rate || speechRate;
    utt.pitch   = 1.0;
    utt.onend   = () => { if (onEnd) onEnd(); resolve(); };
    utt.onerror = () => resolve();
    synthesis.speak(utt);
  });
}

export function stopSpeaking() {
  if (isSynthesisSupported()) synthesis.cancel();
}

export function listen({ continuous = false, interimCallback } = {}) {
  return new Promise((resolve, reject) => {
    if (!isRecognitionSupported()) {
      reject(new Error('Speech recognition not supported in this browser'));
      return;
    }
    const SR  = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SR();
    recognition.lang             = currentLang;
    recognition.continuous       = continuous;
    recognition.interimResults   = !!interimCallback;
    recognition.maxAlternatives  = 1;

    let final = '';
    recognition.onresult = ev => {
      let interim = '';
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const t = ev.results[i][0].transcript;
        ev.results[i].isFinal ? (final += t) : (interim += t);
      }
      if (interimCallback) interimCallback(interim, final);
    };
    recognition.onend   = () => { recognition = null; resolve(final.trim()); };
    recognition.onerror = ev => {
      recognition = null;
      ['no-speech','aborted'].includes(ev.error) ? resolve(final.trim()) : reject(new Error(ev.error));
    };
    recognition.start();
  });
}

export function stopListening() { if (recognition) { recognition.abort(); recognition = null; } }
export function isListening()   { return recognition !== null; }
