import React from 'react';

/** Centered placeholder for empty lists and unselected detail panes. */
export default function EmptyState({ title, body, action, icon = 'inbox' }: {
  title: string;
  body?: React.ReactNode;
  action?: React.ReactNode;
  icon?: 'inbox' | 'check' | 'cursor' | 'search' | 'calendar';
}) {
  const paths = {
    inbox: 'M22 12h-6l-2 3h-4l-2-3H2M5.5 5h13L22 12v6a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-6z',
    check: 'M22 11.1V12a10 10 0 1 1-5.9-9.1M22 4 12 14l-3-3',
    cursor: 'M3 3l7.1 17 2.5-7.4L20 10.1zM13 13l6 6',
    search: 'M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM21 21l-4.3-4.3',
    calendar: 'M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zM16 2v4M8 2v4M3 10h18',
  };
  return (
    <div className="flex flex-col items-center justify-center text-center py-12 px-6">
      <div className="w-10 h-10 rounded-lg border border-white/[0.08] bg-white/[0.03] flex items-center justify-center text-slate-500 mb-3">
        <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d={paths[icon]} />
        </svg>
      </div>
      <p className="text-[0.8125rem] font-medium text-slate-200">{title}</p>
      {body && <p className="mt-1 text-[0.75rem] text-slate-500 max-w-sm leading-relaxed">{body}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
