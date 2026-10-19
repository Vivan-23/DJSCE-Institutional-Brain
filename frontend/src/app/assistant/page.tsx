'use client';
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { apiFetch } from '@/lib/api';
import { Badge } from '@/components/ui/Badge';
import EmptyState from '@/components/ui/EmptyState';

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
      .catch(() => setError('Could not load faculty desk check-in. Please ensure backend is reachable.'));
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
      setError('Message failed to transmit to desk assistant.');
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

  return (
    <main className="p-4 sm:p-6 md:p-10 max-w-3xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-xl md:text-2xl font-semibold text-slate-100 tracking-[-0.02em]">
          Faculty Desk
        </h1>
        <p className="text-slate-400 text-[13px] mt-1">
          Follow-ups on your committee commitments, and an end-of-day check-in that keeps your tasks up to date.
        </p>
      </div>

      {/* Follow-ups */}
      <section className="space-y-3">
        <h2 className="text-[13px] font-medium text-slate-200">
          Follow-ups <span className="text-slate-500 font-normal">{followups.length}</span>
        </h2>
        {followups.length === 0 ? (
          <div className="glass-panel">
            <EmptyState icon="check" title="You're all caught up" body="No open commitments need a follow-up right now. Use the debrief below to log today's work." />
          </div>
        ) : (
          <ul className="glass-panel divide-y divide-white/[0.05] overflow-hidden">
            {followups.map((f) => (
              <li key={f.commitment_id} className="px-4 py-3.5 space-y-1.5">
                <p className="text-[13px] text-slate-100 font-medium">{f.message}</p>
                <p className="text-[12px] text-slate-400">
                  {f.description} · {STATUS_WORD[f.status] ?? f.status}
                </p>
                <div className="mt-2 flex gap-2">
                  <input
                    value={replyText[f.commitment_id] ?? ''}
                    onChange={(e) =>
                      setReplyText((prev) => ({ ...prev, [f.commitment_id]: e.target.value }))
                    }
                    onKeyDown={(e) => e.key === 'Enter' && sendReply(f.commitment_id)}
                    placeholder="Short status update…"
                    className="flex-1 bg-white/[0.03] border border-white/[0.09] rounded-md px-3 h-8 text-[13px] text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500"
                  />
                  <button
                    onClick={() => sendReply(f.commitment_id)}
                    disabled={replyingId === f.commitment_id || !(replyText[f.commitment_id] ?? '').trim()}
                    className="bg-blue-600 hover:bg-blue-500 text-white px-3 h-8 rounded-md text-[13px] font-medium transition-colors disabled:opacity-40 cursor-pointer"
                  >
                    {replyingId === f.commitment_id ? '…' : 'Update'}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* End-of-day check-in */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-[13px] font-medium text-slate-200">End-of-day check-in</h2>
          {checkin?.completed && (
            <Badge tone="success">Recorded for today</Badge>
          )}
        </div>

        <div className="glass-panel flex flex-col h-[360px] sm:h-[380px] rounded-lg overflow-hidden">
          <div ref={scrollRef} className="flex-1 min-h-0 overflow-y-auto p-4 sm:p-5 space-y-3.5">
            {(checkin?.conversation ?? []).map((turn, i) => (
              <div
                key={i}
                className={`flex ${turn.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[80%] px-3.5 py-2.5 rounded-xl text-[13px] leading-relaxed ${
                    turn.role === 'user'
                      ? 'bg-white/[0.06] border border-white/[0.06] text-slate-100'
                      : 'text-slate-200'
                  }`}
                >
                  {turn.content}
                </div>
              </div>
            ))}
            {sending && (
              <div className="flex justify-start">
                <div className="px-3.5 py-2 text-[13px] text-slate-500 flex items-center gap-1.5">
                  <span className="w-1 h-1 bg-slate-400 rounded-full animate-bounce" />
                  <span>Updating your tasks…</span>
                </div>
              </div>
            )}
          </div>

          {lastUpdates.length > 0 && (
            <div className="mx-3 mb-2 rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3 space-y-2" aria-label="Task updates">
              <p className="text-[12px] font-semibold text-emerald-300">
                Updated your tasks from this message
              </p>
              {lastUpdates.map((u) => (
                <div key={u.commitment_id} className="text-xs text-slate-200">
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate">{u.new ? 'New task: ' : ''}{u.description ?? u.summary}</span>
                    <span className="text-slate-400 shrink-0">
                      {typeof u.progress === 'number' ? `${u.progress}% · ` : ''}
                      {STATUS_WORD[u.status ?? ''] ?? u.status ?? ''}
                    </span>
                  </div>
                  {typeof u.progress === 'number' && (
                    <div className="h-1 mt-1 rounded bg-slate-800 overflow-hidden">
                      <div className="h-full bg-emerald-500" style={{ width: `${u.progress}%` }} />
                    </div>
                  )}
                  {(u.remaining || u.blocked_reason) && (
                    <p className="text-[12px] text-slate-400 mt-0.5">
                      {u.blocked_reason ? `Blocked: ${u.blocked_reason}` : `Left: ${u.remaining}`}
                    </p>
                  )}
                </div>
              ))}
              <a href="/commitments" className="inline-block text-[12px] text-blue-300 hover:underline">
                Not right? Correct it on My Work →
              </a>
            </div>
          )}

          {error && (
            <p role="alert" className="text-rose-400 text-xs px-4 pb-1">
              {error}
            </p>
          )}

          <div className="flex gap-2 p-2.5 border-t border-white/[0.06]">
            <input
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
              placeholder={checkin?.completed ? 'Check-in recorded for today' : 'What did you work on today?'}
              disabled={sending || checkin?.completed}
              className="flex-1 bg-white/[0.03] border border-white/[0.09] rounded-md px-3 h-9 text-[13px] text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 disabled:opacity-50"
            />
            <button
              onClick={sendMessage}
              disabled={sending || checkin?.completed || !message.trim()}
              className="bg-blue-600 hover:bg-blue-500 text-white px-4 h-9 rounded-md text-[13px] font-medium transition-colors disabled:opacity-40 cursor-pointer"
            >
              Send
            </button>
          </div>
        </div>

        {!checkin?.completed && (checkin?.conversation.length ?? 0) > 1 && (
          <button
            onClick={completeCheckin}
            className="text-xs text-slate-400 hover:text-emerald-400 transition-colors cursor-pointer"
          >
            Finish today&apos;s check-in →
          </button>
        )}
      </section>
    </main>
  );
}
