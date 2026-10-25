'use client';
import { setTheme, useTheme } from '@/lib/theme';

/** Light/dark switch. Labelled with the theme it switches *to*, so it reads as an action. */
export default function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const theme = useTheme();
  const next = theme === 'dark' ? 'light' : 'dark';
  const label = next === 'light' ? 'Light mode' : 'Dark mode';
  return (
    <button
      type="button"
      onClick={() => setTheme(next)}
      aria-label={`Switch to ${label.toLowerCase()}`}
      title={`Switch to ${label.toLowerCase()}`}
      className="flex items-center gap-1.5 px-2 h-7 rounded-md text-[12px] text-slate-400 hover:text-slate-200 hover:bg-white/[0.05] border border-slate-800 cursor-pointer transition-colors"
    >
      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        {next === 'light' ? (
          <path d="M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10zM12 1v2M12 21v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M1 12h2M21 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4" />
        ) : (
          <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
        )}
      </svg>
      {!compact && <span>{label}</span>}
    </button>
  );
}
