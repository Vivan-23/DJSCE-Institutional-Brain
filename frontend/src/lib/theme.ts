'use client';
import { useSyncExternalStore } from 'react';

export type Theme = 'dark' | 'light';
import { THEME_STORAGE_KEY as KEY } from './themeScript';

const EVENT = 'theme-changed';

function current(): Theme {
  return document.documentElement.dataset.theme === 'light' ? 'light' : 'dark';
}

function subscribe(cb: () => void) {
  window.addEventListener(EVENT, cb);
  window.addEventListener('storage', cb);
  return () => {
    window.removeEventListener(EVENT, cb);
    window.removeEventListener('storage', cb);
  };
}

export function setTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem(KEY, theme);
  } catch {
    /* private mode: the choice lasts for this page only */
  }
  window.dispatchEvent(new Event(EVENT));
}

export function useTheme(): Theme {
  return useSyncExternalStore(subscribe, current, () => 'dark');
}
