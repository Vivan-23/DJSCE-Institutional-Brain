import React from 'react';

export type TicketStatus = 'open' | 'answered' | 'closed';

/** Single source of truth for ticket status wording/colours (help desk + staff queue). */
export const TICKET_STATUS: Record<TicketStatus, { label: string; style: string; hint: string }> = {
  open: {
    label: 'Awaiting reply',
    style: 'bg-blue-500/15 border-blue-500/30 text-blue-300',
    hint: 'Awaiting a reply from the responsible office.',
  },
  answered: {
    label: 'Answered',
    style: 'bg-emerald-500/15 border-emerald-500/30 text-emerald-300',
    hint: 'A faculty member has replied.',
  },
  closed: {
    label: 'Closed',
    style: 'bg-slate-700/20 border-slate-600/40 text-slate-400',
    hint: 'This ticket is closed.',
  },
};

export const PRIORITY_STYLE: Record<string, string> = {
  high: 'text-rose-300',
  normal: 'text-slate-400',
  low: 'text-slate-500',
};

export function TicketBadge({ status }: { status: TicketStatus }) {
  const s = TICKET_STATUS[status] ?? TICKET_STATUS.open;
  return (
    <span className={`shrink-0 text-[12px] font-semibold px-2.5 py-0.5 rounded-full border ${s.style}`}>{s.label}</span>
  );
}
