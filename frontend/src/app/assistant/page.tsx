'use client';
import Link from 'next/link';
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { apiFetch } from '@/lib/api';
import { Badge } from '@/components/ui/Badge';

interface Followup {
  commitment_id: string;
  description: string;
  status: string;
  due_date: string | null;
  message: string;
}

interface Turn {
  role: 'assistant' | 'user';
  content: string;
}

/** What a check-in message changed, as returned by POST /pa/checkin/message. */
interface AppliedUpdate {
  commitment_id: string;
  description?: string;
  status: string | null;
  progress?: number;
  remaining?: string | null;
  blocked_reason?: string | null;
  summary: string | null;
  new?: boolean;
}

const STATUS_WORD: Record<string, string> = {
  open: 'not started', in_progress: 'in progress', blocked: 'blocked', review: 'done, awaiting confirmation',
  done: 'completed', dropped: 'dropped',
};

interface CheckinState {
  id: string;
  date: string;
  completed: boolean;
  conversation: Turn[];
  extracted_updates: { commitment_id: string; status: string | null; summary: string | null; new?: boolean }[];
}

export default function AssistantPage() {
  const [followups, setFollowups] = useState<Followup[]>([]);
  const [replyText, setReplyText] = useState<Record<string, string>>({});
  const [replyingId, setReplyingId] = useState<string | null>(null);

  const [checkin, setCheckin] = useState<CheckinState | null>(null);
  const [message, setMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [lastUpdates, setLastUpdates] = useState<AppliedUpdate[]>([]);

  const scrollRef = useRef<HTMLDivElement>(null);

  const loadFollowups = useCallback(() => {
    apiFetch('/api/v1/pa/followups')
      .then((r) => (r.ok ? r.json() : []))
      .then((data: Followup[]) => setFollowups(data))
      .catch(() => setFollowups([]));
  }, []);

  const loadCheckin = useCallback(() => {
    apiFetch('/api/v1/pa/checkin')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data: CheckinState) => setCheckin(data))
      .catch(() => setError("Could not load today's check-in. Please refresh the page."));
  }, []);

  useEffect(() => {
    loadFollowups();
    loadCheckin();
  }, [loadFollowups, loadCheckin]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [checkin?.conversation.length]);

  const sendMessage = async () => {
    const text = message.trim();
    if (!text || sending || checkin?.completed) return;
    setSending(true);
    setError('');
    setCheckin((prev) =>
      prev ? { ...prev, conversation: [...prev.conversation, { role: 'user', content: text }] } : prev,
    );
    setMessage('');
    try {
      const res = await apiFetch('/api/v1/pa/checkin/message', {
        method: 'POST',
        body: JSON.stringify({ text }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setCheckin((prev) =>
        prev
          ? { ...prev, conversation: [...prev.conversation, { role: 'assistant', content: data.reply }] }
          : prev,
      );
      setLastUpdates((data.updates as AppliedUpdate[]) ?? []);
      loadFollowups();
    } catch {
      setError('Your update could not be saved. Please try again.');
    } finally {
      setSending(false);
    }
  };

  const completeCheckin = async () => {
    const res = await apiFetch('/api/v1/pa/checkin/complete', { method: 'POST' });
    if (res.ok) setCheckin(await res.json());
  };

  const sendReply = async (commitmentId: string) => {
    const text = (replyText[commitmentId] ?? '').trim();
    if (!text) return;
    setReplyingId(commitmentId);
    try {
      const res = await apiFetch(`/api/v1/pa/followups/${commitmentId}/reply`, {
        method: 'POST',
        body: JSON.stringify({ text }),
      });
      if (res.ok) {
        setReplyText((prev) => ({ ...prev, [commitmentId]: '' }));
        loadFollowups();
      }
    } finally {
      setReplyingId(null);
    }
  };

  // The opening assistant greeting is always there; the conversation is worth showing once the person has written.
  const turns = checkin?.conversation ?? [];
  const started = turns.some((t) => t.role === 'user');
  const STARTERS = ['Finished ', 'Still working on ', 'Stuck on '];

  return (
    <main className="p-4 sm:p-6 md:p-10 max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl md:text-2xl font-semibold text-slate-100 tracking-[-0.02em]">
          End-of-day Check-in
        </h1>
        <p className="text-slate-400 text-sm mt-1">
          Write a line or two about what you did today. Your task list on{' '}
          <Link href="/commitments" className="text-blue-400 hover:text-blue-300 underline underline-offset-2">My Work</Link>{' '}
          updates itself.
        </p>
      </div>

      {/* Today's check-in: the one thing to do on this page */}
      <section className="glass-panel p-4 sm:p-5 space-y-4" aria-label="Today's check-in">
        {checkin?.completed && <Badge tone="success">Recorded for today. Thank you.</Badge>}

        {started && (
          <div ref={scrollRef} className="max-h-[24rem] overflow-y-auto space-y-3" aria-live="polite">
            {turns.map((turn, i) => (
              <div key={i} className={`flex ${turn.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`max-w-[85%] px-3.5 py-2.5 rounded-xl text-sm leading-relaxed ${
                    turn.role === 'user' ? 'bg-blue-600/15 border border-blue-500/20 text-slate-100' : 'bg-white/[0.04] text-slate-200'
                  }`}
                >
                  {turn.content}
                </div>
              </div>
            ))}
            {sending && <p className="text-sm text-slate-400">Updating your tasks…</p>}
          </div>
        )}

        {lastUpdates.length > 0 && (
          <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3 space-y-2" aria-label="Task updates">
            <p className="text-sm font-semibold text-emerald-300">Your tasks were updated</p>
            {lastUpdates.map((u) => (
              <div key={u.commitment_id} className="text-sm text-slate-200">
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate">{u.new ? 'New task: ' : ''}{u.description ?? u.summary}</span>
                  <span className="text-slate-400 shrink-0">
                    {typeof u.progress === 'number' ? `${u.progress}% · ` : ''}
                    {STATUS_WORD[u.status ?? ''] ?? u.status ?? ''}
                  </span>
                </div>
                {(u.remaining || u.blocked_reason) && (
                  <p className="text-[0.8125rem] text-slate-400 mt-0.5">
                    {u.blocked_reason ? `Stuck: ${u.blocked_reason}` : `Left: ${u.remaining}`}
                  </p>
                )}
              </div>
            ))}
            <Link href="/commitments" className="inline-block text-[0.8125rem] text-blue-300 hover:underline">
              Not right? Correct it on My Work →
            </Link>
          </div>
        )}

        {!checkin?.completed && (
          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              sendMessage();
            }}
          >
            <label htmlFor="checkin-text" className="block text-base font-medium text-slate-100">
              {started ? 'Anything else?' : 'What did you do today?'}
            </label>
            {!message && (
              <div className="flex flex-wrap gap-2">
                {STARTERS.map((s) => (
                  <button key={s} type="button" onClick={() => setMessage(s)}
                    className="px-3 h-9 rounded-full border border-slate-700 text-sm text-slate-300 hover:text-slate-100 hover:border-slate-500 cursor-pointer">
                    {s.trim()}…
                  </button>
                ))}
              </div>
            )}
            <textarea
              id="checkin-text"
              rows={3}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  sendMessage();
                }
              }}
              placeholder="e.g. Finished the ML lab marks for C31. Still working on the BIA question paper."
              disabled={sending}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3.5 py-2.5 text-base text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 disabled:opacity-50"
            />
            {error && <p role="alert" className="text-rose-400 text-sm">{error}</p>}
            <div className="flex flex-wrap items-center gap-3">
              <button type="submit" disabled={sending || !message.trim()}
                className="px-5 h-11 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-base font-semibold disabled:opacity-40 cursor-pointer">
                {sending ? 'Saving…' : "Save today's update"}
              </button>
              {started && (
                <button type="button" onClick={completeCheckin}
                  className="px-5 h-11 rounded-lg border border-slate-600 text-base text-slate-200 hover:border-emerald-500 hover:text-emerald-300 cursor-pointer">
                  I&apos;m done for today
                </button>
              )}
            </div>
          </form>
        )}
      </section>

      {/* Follow-ups: only when something is actually waiting */}
      {followups.length > 0 && (
        <section className="space-y-3" aria-label="Tasks waiting for your update">
          <h2 className="text-base font-semibold text-slate-100">Tasks waiting for your update ({followups.length})</h2>
          <ul className="glass-panel divide-y divide-white/[0.05] overflow-hidden">
            {followups.map((f) => (
              <li key={f.commitment_id} className="px-4 py-3.5 space-y-1.5">
                <p className="text-sm text-slate-100 font-medium">{f.message}</p>
                <p className="text-[0.8125rem] text-slate-400">
                  {f.description} · {STATUS_WORD[f.status] ?? f.status}
                </p>
                <div className="mt-2 flex gap-2">
                  <label htmlFor={`fu-${f.commitment_id}`} className="sr-only">Update for {f.description}</label>
                  <input
                    id={`fu-${f.commitment_id}`}
                    value={replyText[f.commitment_id] ?? ''}
                    onChange={(e) => setReplyText((prev) => ({ ...prev, [f.commitment_id]: e.target.value }))}
                    onKeyDown={(e) => e.key === 'Enter' && sendReply(f.commitment_id)}
                    placeholder="e.g. Half done, will finish Friday"
                    className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 h-10 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500"
                  />
                  <button
                    onClick={() => sendReply(f.commitment_id)}
                    disabled={replyingId === f.commitment_id || !(replyText[f.commitment_id] ?? '').trim()}
                    className="bg-blue-600 hover:bg-blue-500 text-white px-4 h-10 rounded-lg text-sm font-semibold disabled:opacity-40 cursor-pointer"
                  >
                    {replyingId === f.commitment_id ? 'Saving…' : 'Update'}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
