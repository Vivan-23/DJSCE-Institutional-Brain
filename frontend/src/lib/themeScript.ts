// Server-safe (no 'use client'): imported by the root layout.
export const THEME_STORAGE_KEY = 'theme';

/** Runs in <head> before first paint so the stored theme never flashes. Dark by default. */
export const THEME_INIT_SCRIPT = `try{var t=localStorage.getItem('${THEME_STORAGE_KEY}');document.documentElement.dataset.theme=t==='light'?'light':'dark'}catch(e){document.documentElement.dataset.theme='dark'}`;
