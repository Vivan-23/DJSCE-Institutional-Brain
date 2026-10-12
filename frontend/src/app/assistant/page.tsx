'use client';
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { apiFetch } from '@/lib/api';

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
    <main className="p-6 md:p-10 max-w-3xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl md:text-3xl font-bold text-slate-100 tracking-tight">
          Faculty Desk &amp; Daily Debrief
        </h1>
        <p className="text-slate-400 text-xs sm:text-sm mt-1">
          Proactive follow-ups on committee responsibilities, statutory deliverables, and evening conversational check-in.
        </p>
      </div>

      {/* Follow-ups */}
      <section className="space-y-3">
        <h2 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
          Pending Follow-ups &amp; Inquiries ({followups.length})
        </h2>
        {followups.length === 0 ? (
          <div className="glass-panel p-5 text-xs text-slate-400">
            You are fully caught up — no open institutional commitments require follow-up at this time.
          </div>
        ) : (
          <ul className="space-y-3">
            {followups.map((f) => (
              <li key={f.commitment_id} className="glass-panel p-4 space-y-2">
                <p className="text-xs sm:text-sm text-slate-200 font-medium">{f.message}</p>
                <p className="text-[11px] text-slate-400">
                  Regarding deliverable: <strong className="text-slate-300">{f.description}</strong> · Status: {f.status}
                </p>
                <div className="mt-2 flex gap-2">
                  <input
                    value={replyText[f.commitment_id] ?? ''}
                    onChange={(e) =>
                      setReplyText((prev) => ({ ...prev, [f.commitment_id]: e.target.value }))
                    }
                    onKeyDown={(e) => e.key === 'Enter' && sendReply(f.commitment_id)}
                    placeholder="Provide brief status update in plain language…"
                    className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500"
                  />
                  <button
                    onClick={() => sendReply(f.commitment_id)}
                    disabled={replyingId === f.commitment_id || !(replyText[f.commitment_id] ?? '').trim()}
                    className="bg-blue-600 hover:bg-blue-500 text-white px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors disabled:opacity-40 cursor-pointer"
                  >
                    {replyingId === f.commitment_id ? '…' : 'Submit Update'}
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
          <h2 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
            Faculty End-of-Day Conversational Debrief
          </h2>
          {checkin?.completed && (
            <span className="text-[11px] px-2 py-0.5 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 font-semibold">
              Today&apos;s Debrief Recorded
            </span>
          )}
        </div>

        <div className="glass-panel flex flex-col h-[380px] sm:h-[460px] md:h-[520px] rounded-lg overflow-hidden">
          <div ref={scrollRef} className="flex-1 min-h-0 overflow-y-auto p-4 sm:p-5 space-y-3.5">
            {(checkin?.conversation ?? []).map((turn, i) => (
              <div
                key={i}
                className={`flex ${turn.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[80%] px-3.5 py-2.5 rounded-lg text-xs leading-relaxed ${
                    turn.role === 'user'
                      ? 'bg-blue-600/20 border border-blue-500/40 text-slate-100'
                      : 'bg-slate-900/90 border border-slate-800 text-slate-200'
                  }`}
                >
                  {turn.content}
                </div>
              </div>
            ))}
            {sending && (
              <div className="flex justify-start">
                <div className="bg-slate-900/80 border border-slate-800 px-3 py-2 rounded-lg text-xs text-slate-400 flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" />
                  <span>Synthesizing progress updates…</span>
                </div>
              </div>
            )}
          </div>

          {error && (
            <p role="alert" className="text-rose-400 text-xs px-4 pb-1">
              {error}
            </p>
          )}

          <div className="flex gap-2 p-3 border-t border-slate-800 bg-slate-950/60">
            <input
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
              placeholder={checkin?.completed ? 'Daily debrief completed' : 'Mention lectures conducted, lab experiments evaluated, or committee prep done…'}
              disabled={sending || checkin?.completed}
              className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 disabled:opacity-50"
            />
            <button
              onClick={sendMessage}
              disabled={sending || checkin?.completed || !message.trim()}
              className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg text-xs font-semibold transition-colors disabled:opacity-40 cursor-pointer"
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
            Mark today&apos;s debrief as complete →
          </button>
        )}
      </section>
    </main>
  );
}
