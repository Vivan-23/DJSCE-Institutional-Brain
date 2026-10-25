'use client';
import React, { useCallback, useEffect, useState } from 'react';
import { apiFetch } from '@/lib/api';
import { formatDateTime } from '@/lib/format';
import SourceList, { type Source } from '@/components/knowledge/SourceList';
import { PRIORITY_STYLE, TICKET_STATUS, TicketBadge, type TicketStatus } from '@/components/helpdesk/TicketBadge';
import EmptyState from '@/components/ui/EmptyState';
import { renderBold } from '@/lib/renderBold';
import { useMe } from '@/lib/roles';

interface StaffTicket {
  id: string;
  subject: string;
  description: string;
  status: TicketStatus;
  category: string;
  priority: string;
  routed_to: string;
  reply: string | null;
  created_at: string;
  raised_by: string | null;
  raised_by_role: string | null;
  triage_method: 'llm' | 'keyword' | string;
  triage_rationale: string | null;
  ai_draft_reply: string | null;
  ai_sources: Source[];
}

const FILTERS: (TicketStatus | 'all')[] = ['open', 'answered', 'closed', 'all'];

export default function TicketQueuePage() {
  const me = useMe(true);
  // Administrators may read the queue for oversight; only faculty reply (enforced by the backend).
  const readOnly = me?.role === 'admin';
  const [filter, setFilter] = useState<TicketStatus | 'all'>('open');
  const [tickets, setTickets] = useState<StaffTicket[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback((status: TicketStatus | 'all') => {
    const qs = status === 'all' ? '' : `?status=${status}`;
    apiFetch(`/api/v1/helpdesk/tickets${qs}`)
      .then(async (r) => {
        if (!r.ok) throw new Error(r.status === 403 ? 'The ticket queue is handled by faculty (administrators can read it).' : `HTTP ${r.status}`);
        return r.json();
      })
      .then((data: StaffTicket[]) => {
        setTickets(data);
        setError('');
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(() => {
    load(filter);
  }, [filter, load]);

  const selected = tickets.find((t) => t.id === selectedId) ?? null;

  const select = (t: StaffTicket) => {
    setSelectedId(t.id);
    setDraft(t.reply ?? '');
  };

  const replaceTicket = (updated: StaffTicket) =>
    setTickets((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));

  const send = async (close: boolean) => {
    if (!selected || !draft.trim()) return;
    setBusy(true);
    const res = await apiFetch(`/api/v1/helpdesk/tickets/${selected.id}/reply`, {
      method: 'POST',
      body: JSON.stringify({ reply: draft, close }),
    });
    setBusy(false);
    if (res.ok) {
      replaceTicket(await res.json());
      load(filter);
    }
  };

  const retriage = async () => {
    if (!selected) return;
    setBusy(true);
    const res = await apiFetch(`/api/v1/helpdesk/tickets/${selected.id}/retriage`, { method: 'POST' });
    setBusy(false);
    if (res.ok) replaceTicket(await res.json());
  };

  return (
    <main className="p-4 sm:p-6 md:p-10 max-w-7xl mx-auto space-y-5">
      <div>
        <h1 className="text-xl md:text-2xl font-semibold text-slate-100 tracking-[-0.02em]">Ticket Queue</h1>
        <p className="text-slate-400 text-xs sm:text-sm mt-1">
          Tickets are triaged and drafted by AI. Review every draft — nothing reaches the student until you send it.
        </p>
        {readOnly && (
          <p className="mt-2 text-[0.8125rem] text-amber-300" role="note">Read-only view: faculty members reply to tickets.</p>
        )}
      </div>

      <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Filter tickets by status">
        {FILTERS.map((f) => (
          <button
            key={f}
            role="tab"
            aria-selected={filter === f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1.5 rounded text-xs font-medium border cursor-pointer ${
              filter === f
                ? 'bg-blue-600/15 text-blue-300 border-blue-500/40'
                : 'text-slate-400 border-slate-800 hover:text-slate-200'
            }`}
          >
            {f === 'all' ? 'All' : TICKET_STATUS[f].label}
          </button>
        ))}
      </div>

      {error && <p role="alert" className="text-rose-400 text-xs">{error}</p>}

      <div className="grid lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] gap-4">
        <ul className="glass-panel divide-y divide-white/[0.05] overflow-hidden self-start" aria-label="Tickets">
          {tickets.length === 0 && !error && (
            <li><EmptyState icon="check" title="All caught up" body="No tickets in this view." /></li>
          )}
          {tickets.map((t) => (
            <li key={t.id}>
              <button
                type="button"
                onClick={() => select(t)}
                className={`w-full text-left px-4 py-3 cursor-pointer transition-colors ${
                  t.id === selectedId ? 'bg-white/[0.05]' : 'hover:bg-white/[0.025]'
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <p className="text-[0.8125rem] font-medium text-slate-100 truncate">{t.subject}</p>
                  <TicketBadge status={t.status} />
                </div>
                <p className="text-[0.75rem] text-slate-500 mt-1 truncate">
                  <span className={PRIORITY_STYLE[t.priority] ?? ''}>{t.priority} priority</span> · {t.routed_to} ·{' '}
                  {t.raised_by ?? 'Unknown'} · {formatDateTime(t.created_at)}
                </p>
              </button>
            </li>
          ))}
        </ul>

        <section className="glass-panel p-5 space-y-4 min-h-[16rem]" aria-label="Ticket detail">
          {!selected ? (
            <EmptyState icon="cursor" title="No ticket selected" body="Pick a ticket on the left to review the AI triage and the draft reply before sending it." />
          ) : (
            <>
              <div>
                <p className="text-base font-semibold text-slate-100">{selected.subject}</p>
                <p className="text-[0.75rem] text-slate-500 mt-0.5">
                  Raised by {selected.raised_by ?? 'Unknown'} ({selected.raised_by_role ?? 'user'}) · {formatDateTime(selected.created_at)}
                </p>
                <p className="text-xs text-slate-300 mt-2 whitespace-pre-wrap">{selected.description}</p>
              </div>

              <div className="rounded border border-slate-800 bg-slate-950/60 p-3 text-[0.75rem] text-slate-300 space-y-1">
                <p className="text-[0.6875rem] font-semibold text-slate-400">
                  Triage · {selected.triage_method === 'llm' ? 'AI classifier' : 'Keyword rules (offline fallback)'}
                </p>
                <p>
                  Category <span className="font-mono text-slate-200">{selected.category}</span> · Priority{' '}
                  <span className={PRIORITY_STYLE[selected.priority] ?? ''}>{selected.priority}</span> · Routed to{' '}
                  <span className="text-slate-200">{selected.routed_to}</span>
                </p>
                {selected.triage_rationale && <p className="text-slate-400">{selected.triage_rationale}</p>}
                {!readOnly && (
                <button
                  type="button"
                  onClick={retriage}
                  disabled={busy}
                  className="text-blue-300 hover:text-blue-200 disabled:opacity-50 cursor-pointer"
                >
                  Re-run triage &amp; draft
                </button>
                )}
              </div>

              <div className="rounded border border-blue-500/20 bg-blue-500/5 p-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-[0.6875rem] font-semibold text-blue-300">AI-suggested reply (not sent)</p>
                  {selected.ai_draft_reply && (
                    <button
                      type="button"
                      onClick={() => setDraft(selected.ai_draft_reply ?? '')}
                      className="text-[0.75rem] text-blue-300 hover:text-blue-200 cursor-pointer"
                    >
                      Use as starting point
                    </button>
                  )}
                </div>
                <p className="text-xs text-slate-200 mt-1.5 whitespace-pre-wrap">
                  {selected.ai_draft_reply ? renderBold(selected.ai_draft_reply) : 'No draft was generated (language model unavailable).'}
                </p>
                <SourceList sources={selected.ai_sources} warnInternal />
              </div>

              {!readOnly && (
              <div className="space-y-2">
                <label htmlFor="staff-reply" className="text-[0.6875rem] font-semibold text-slate-400">
                  Your reply to the {selected.raised_by_role === 'student' ? 'student' : 'requester'}
                </label>
                <textarea
                  id="staff-reply"
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  rows={5}
                  className="w-full bg-slate-900 border border-slate-700 rounded-md px-3.5 py-2 text-xs sm:text-sm text-slate-100 focus:outline-none focus:border-blue-500"
                />
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => send(false)}
                    disabled={busy || !draft.trim()}
                    className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-md text-xs font-semibold disabled:opacity-40 cursor-pointer"
                  >
                    Send reply
                  </button>
                  <button
                    type="button"
                    onClick={() => send(true)}
                    disabled={busy || !draft.trim()}
                    className="bg-slate-800 hover:bg-slate-700 text-slate-200 px-4 py-2 rounded-md text-xs font-semibold border border-slate-700 disabled:opacity-40 cursor-pointer"
                  >
                    Send &amp; close
                  </button>
                </div>
              </div>
              )}
            </>
          )}
        </section>
      </div>
    </main>
  );
}
