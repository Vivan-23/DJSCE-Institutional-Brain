'use client';
import React, { useCallback, useEffect, useState } from 'react';
import { apiFetch } from '@/lib/api';
import { formatDateTime } from '@/lib/format';
import { useMe } from '@/lib/roles';
import SourceList, { type Source } from '@/components/knowledge/SourceList';
import HowToGuides from '@/components/helpdesk/HowToGuides';
import { TICKET_STATUS, TicketBadge, type TicketStatus } from '@/components/helpdesk/TicketBadge';

interface Category {
  key: string;
  label: string;
  routed_to: string;
  quick_questions: string[];
}

interface Ticket {
  id: string;
  subject: string;
  description: string;
  status: TicketStatus;
  category: string;
  priority: string;
  routed_to: string;
  reply: string | null;
  replied_at: string | null;
  created_at: string;
}

interface Answer {
  question: string;
  text: string;
  sources: Source[];
}

const inputCls =
  'w-full bg-slate-900 border border-slate-700 rounded-lg px-3.5 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 focus-visible:ring-2 focus-visible:ring-blue-500/40';

export default function HelpDeskPage() {
  const me = useMe(true);
  const [categories, setCategories] = useState<Category[]>([]);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [asking, setAsking] = useState(false);
  const [question, setQuestion] = useState('');

  const [subject, setSubject] = useState('');
  const [description, setDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [notice, setNotice] = useState<{ kind: 'ok' | 'error'; text: string } | null>(null);

  const loadTickets = useCallback(() => {
    apiFetch('/api/v1/helpdesk/tickets/mine')
      .then((r) => (r.ok ? r.json() : []))
      .then(setTickets)
      .catch(() => {});
  }, []);

  useEffect(() => {
    apiFetch('/api/v1/helpdesk/categories')
      .then((r) => (r.ok ? r.json() : []))
      .then(setCategories)
      .catch(() => {});
    loadTickets();
  }, [loadTickets]);

  const ask = async (q: string) => {
    const text = q.trim();
    if (!text || asking) return;
    setAsking(true);
    setQuestion(text);
    setAnswer(null);
    try {
      const res = await apiFetch('/api/v1/chat', {
        method: 'POST',
        body: JSON.stringify({ messages: [{ role: 'user', content: text }] }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? `HTTP ${res.status}`);
      setAnswer({ question: text, text: data.response, sources: data.sources ?? [] });
    } catch (err: unknown) {
      setAnswer({
        question: text,
        text: `The assistant could not answer right now (${err instanceof Error ? err.message : 'error'}). You can raise a ticket instead.`,
        sources: [],
      });
    } finally {
      setAsking(false);
    }
  };

  const escalate = () => {
    if (!answer) return;
    setSubject(answer.question.slice(0, 200));
    setDescription(`${answer.question}\n\nThe assistant's answer did not resolve my query.`);
    document.getElementById('raise-ticket')?.scrollIntoView({ behavior: 'smooth' });
    document.getElementById('hd-subject')?.focus({ preventScroll: true });
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setNotice(null);
    try {
      const res = await apiFetch('/api/v1/helpdesk/tickets', {
        method: 'POST',
        body: JSON.stringify({ subject, description }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Please check the subject and description.');
      setNotice({ kind: 'ok', text: `Ticket raised and sent to ${data.routed_to}. The reply will appear under My tickets.` });
      setSubject('');
      setDescription('');
      loadTickets();
    } catch (err: unknown) {
      setNotice({ kind: 'error', text: err instanceof Error ? err.message : 'Could not raise the ticket.' });
    } finally {
      setSubmitting(false);
    }
  };

  const closeTicket = async (id: string) => {
    const res = await apiFetch(`/api/v1/helpdesk/tickets/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ status: 'closed' }),
    });
    if (res.ok) loadTickets();
  };

  const labelFor = (key: string) => categories.find((c) => c.key === key)?.label ?? key;

  // The Help Desk is for students and faculty (the backend returns 403 to other roles).
  if (me && me.role !== 'student' && me.role !== 'employee') {
    return (
      <main className="p-4 sm:p-6 md:p-10 max-w-3xl mx-auto">
        <h1 className="text-xl md:text-2xl font-semibold text-slate-100 tracking-[-0.02em]">Help Desk</h1>
        <p className="text-slate-400 text-sm mt-2">
          The Help Desk is for students and faculty. Committee Coordinators manage work from My Work; System
          Administrators can review tickets read-only in the Ticket Queue.
        </p>
      </main>
    );
  }

  const quickQuestions = categories.flatMap((c) => c.quick_questions.map((q) => ({ q, label: c.label }))).slice(0, 6);

  return (
    <main className="p-4 sm:p-6 md:p-10 max-w-6xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl md:text-2xl font-semibold text-slate-100 tracking-[-0.02em]">Help Desk</h1>
        <p className="text-slate-400 text-sm mt-1">
          Ask a question for an instant answer from published department information, or raise a ticket for a person to answer.
        </p>
        <a
          href="#raise-ticket"
          className="lg:hidden inline-block mt-2 text-sm font-medium text-blue-400 hover:text-blue-300 underline underline-offset-2"
        >
          Jump to Raise a Ticket ↓
        </a>
      </div>

      <div className="grid gap-5 lg:grid-cols-2 items-start">
        {/* Ask */}
        <section className="glass-panel p-5 space-y-4" aria-labelledby="ask-heading">
          <div>
            <h2 id="ask-heading" className="text-base font-semibold text-slate-100">Ask a Question</h2>
            <p className="text-[0.8125rem] text-slate-400 mt-0.5">Answers come from published information, with sources.</p>
          </div>
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              ask(question);
            }}
          >
            <label htmlFor="hd-question" className="sr-only">Your question</label>
            <input
              id="hd-question"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="e.g. Which electives are offered in Semester VI?"
              className={`${inputCls} flex-1 min-w-0`}
            />
            <button
              type="submit"
              disabled={asking || !question.trim()}
              className="bg-blue-600 hover:bg-blue-500 text-white px-5 py-2.5 rounded-lg text-sm font-semibold disabled:opacity-40 cursor-pointer shrink-0"
            >
              {asking ? 'Searching…' : 'Ask'}
            </button>
          </form>

          {quickQuestions.length > 0 && (
            <div>
              <p className="text-[0.75rem] font-medium text-slate-500 mb-1.5">Common questions</p>
              <div className="flex flex-col gap-1">
                {quickQuestions.map(({ q, label }) => (
                  <button
                    key={q}
                    type="button"
                    onClick={() => ask(q)}
                    disabled={asking}
                    className="text-left text-[0.8125rem] text-blue-300 hover:text-blue-200 disabled:opacity-50 cursor-pointer rounded px-1 py-0.5 focus-visible:outline-2 focus-visible:outline-blue-500"
                  >
                    {q} <span className="text-slate-500">· {label}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {asking && <p className="text-[0.8125rem] text-slate-400" role="status">Looking for an answer…</p>}
          {answer && (
            <div className="rounded-lg border border-slate-800 bg-slate-950/70 p-4" aria-live="polite">
              <p className="text-[0.75rem] font-semibold text-blue-400 mb-1">AI answer · public information only</p>
              <p className="text-[0.8125rem] text-slate-400 mb-2">{answer.question}</p>
              <p className="text-sm text-slate-200 whitespace-pre-wrap leading-relaxed">{answer.text}</p>
              <SourceList sources={answer.sources} />
              <button
                type="button"
                onClick={escalate}
                className="mt-3 text-[0.8125rem] font-semibold text-amber-300 hover:text-amber-200 cursor-pointer"
              >
                Not answered? Raise a ticket with this question →
              </button>
            </div>
          )}
        </section>

        {/* Raise */}
        <section id="raise-ticket" className="glass-panel p-5 space-y-3 scroll-mt-4" aria-labelledby="raise-heading">
          <div>
            <h2 id="raise-heading" className="text-base font-semibold text-slate-100">Raise a Ticket</h2>
            <p className="text-[0.8125rem] text-slate-400 mt-0.5">
              Use this when the instant answer doesn&apos;t help or your query is personal. It goes to the responsible
              office, and a faculty member writes the reply.
            </p>
          </div>
          <form onSubmit={submit} className="space-y-3">
            <div>
              <label htmlFor="hd-subject" className="block text-[0.8125rem] font-medium text-slate-300 mb-1">Subject</label>
              <input
                id="hd-subject"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="A short title for your query"
                required
                minLength={3}
                maxLength={200}
                className={inputCls}
              />
            </div>
            <div>
              <label htmlFor="hd-description" className="block text-[0.8125rem] font-medium text-slate-300 mb-1">Description</label>
              <textarea
                id="hd-description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe your query in detail"
                required
                minLength={5}
                rows={5}
                className={inputCls}
              />
            </div>
            {notice && (
              <p role="status" className={`text-[0.8125rem] ${notice.kind === 'ok' ? 'text-emerald-400' : 'text-rose-400'}`}>
                {notice.kind === 'ok' ? '✓ ' : '⚠ '}
                {notice.text}
              </p>
            )}
            <button
              type="submit"
              disabled={submitting}
              className="w-full sm:w-auto bg-blue-600 hover:bg-blue-500 text-white px-5 py-2.5 rounded-lg text-sm font-semibold disabled:opacity-40 cursor-pointer"
            >
              {submitting ? 'Submitting…' : 'Submit Ticket'}
            </button>
          </form>
        </section>
      </div>

      {/* Mine */}
      <section className="glass-panel p-5 space-y-3" aria-labelledby="mine-heading">
        <h2 id="mine-heading" className="text-base font-semibold text-slate-100">
          My tickets ({tickets.length})
        </h2>
        {tickets.length === 0 ? (
          <p className="text-[0.8125rem] text-slate-500">You haven&apos;t raised any tickets yet.</p>
        ) : (
          <ul className="space-y-3">
            {tickets.map((t) => (
              <li key={t.id} className="rounded-lg border border-slate-800 bg-slate-900/50 p-3.5">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-slate-100">{t.subject}</p>
                    <p className="text-[0.75rem] text-slate-500 mt-0.5">
                      {labelFor(t.category)} · {t.routed_to} · {formatDateTime(t.created_at)}
                    </p>
                  </div>
                  <TicketBadge status={t.status} />
                </div>
                <p className="text-[0.8125rem] text-slate-400 mt-2 whitespace-pre-wrap">{t.description}</p>
                {t.reply ? (
                  <div className="mt-3 rounded border border-emerald-500/20 bg-emerald-500/5 p-2.5">
                    <p className="text-[0.75rem] font-semibold text-emerald-300">
                      Reply from faculty · {formatDateTime(t.replied_at)}
                    </p>
                    <p className="text-[0.8125rem] text-slate-200 mt-1 whitespace-pre-wrap">{t.reply}</p>
                  </div>
                ) : (
                  <p className="mt-2 text-[0.8125rem] text-slate-500">{TICKET_STATUS.open.hint}</p>
                )}
                {t.status !== 'closed' && (
                  <button
                    type="button"
                    onClick={() => closeTicket(t.id)}
                    className="mt-2 text-[0.8125rem] text-slate-400 hover:text-slate-200 cursor-pointer"
                  >
                    Mark as resolved
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <HowToGuides />
    </main>
  );
}
