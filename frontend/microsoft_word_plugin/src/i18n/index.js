import { ref } from 'vue';
import enUS from '../locales/en-US.js';
import idID from '../locales/id-ID.js';
import zhCN from '../locales/zh-CN.js';

const STORAGE_KEY = 'wence-interface-language';
const messages = { 'zh-CN': zhCN, 'en-US': enUS, 'id-ID': idID };

function normalizeLocale(value) {
  if (!value) return 'zh-CN';
  const normalized = String(value).toLowerCase();
  if (normalized === 'en-us' || normalized.startsWith('en')) return 'en-US';
  if (normalized === 'id-id' || normalized === 'id' || normalized.startsWith('id')) return 'id-ID';
  return 'zh-CN';
}

let storedLocale = '';
try {
  storedLocale = window.localStorage.getItem(STORAGE_KEY) || '';
} catch (_) {
  storedLocale = '';
}

export const locale = ref(normalizeLocale(storedLocale));

export function setLocale(value) {
  const nextLocale = normalizeLocale(value);
  locale.value = nextLocale;
  document.documentElement.lang = nextLocale;
  try {
    window.localStorage.setItem(STORAGE_KEY, nextLocale);
  } catch (_) {
    // Some Office hosts can disable localStorage; backend settings remain the fallback.
  }
}

export function t(key, params = {}) {
  const resolve = (source) => key.split('.').reduce((value, part) => value?.[part], source);
  const template = resolve(messages[locale.value]) ?? resolve(messages['zh-CN']) ?? key;
  return Object.entries(params).reduce(
    (result, [name, value]) => result.replaceAll(`{${name}}`, String(value)),
    String(template)
  );
}

export const i18n = {
  install(app) {
    app.config.globalProperties.$t = t;
    app.provide('i18n', { locale, setLocale, t });
    setLocale(locale.value);
  }
};
