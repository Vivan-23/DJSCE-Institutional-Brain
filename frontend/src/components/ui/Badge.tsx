import React from 'react';

export type Tone = 'neutral' | 'accent' | 'success' | 'warning' | 'danger';

const DOT: Record<Tone, string> = {
  neutral: 'bg-slate-500',
  accent: 'bg-blue-500',
  success: 'bg-emerald-400',
  warning: 'bg-amber-400',
  danger: 'bg-rose-400',
};

/** Single status-badge style for the whole app: neutral pill, coloured dot, plain label. */
export function Badge({ tone = 'neutral', children, title }: { tone?: Tone; children: React.ReactNode; title?: string }) {
  return (
    <span
      title={title}
      className="inline-flex items-center gap-1.5 shrink-0 h-5 px-2 rounded-full border border-white/[0.08] bg-white/[0.03] text-[0.75rem] text-slate-300 whitespace-nowrap"
    >
      <span className={`w-1.5 h-1.5 rounded-full ${DOT[tone]}`} aria-hidden="true" />
      {children}
    </span>
  );
}

/** Small outlined tag for secondary attributes (version, visibility, department). */
export function Tag({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center h-5 px-1.5 rounded border border-white/[0.08] text-[0.6875rem] text-slate-400 whitespace-nowrap">
      {children}
    </span>
  );
}
