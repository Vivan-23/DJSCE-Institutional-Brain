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
      .catch(() => setError('Could not load your check-in. Is the backend running?'));
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
    // Optimistically show the user's turn.
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
      setError('Message failed to send.');
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
    <main className="min-h-screen p-8 md:p-12">
      <div className="max-w-3xl mx-auto">
        <h1 className="text-3xl font-bold mb-2 text-white">Your Assistant</h1>
        <p className="text-gray-400 mb-8">
          Your personal PA tracks the commitments you make and helps you wrap up the
          day — just talk, no forms.
        </p>

        {/* Follow-ups */}
        <section className="mb-10">
          <h2 className="text-lg font-semibold text-white mb-3">Follow-ups</h2>
          {followups.length === 0 ? (
            <div className="glass-panel p-5 text-sm text-gray-500">
              You&apos;re all caught up — no open commitments need a nudge right now.
            </div>
          ) : (
            <ul className="space-y-3">
              {followups.map((f) => (
                <li key={f.commitment_id} className="glass-panel p-4">
                  <p className="text-sm text-gray-200">{f.message}</p>
                  <p className="text-xs text-gray-500 mt-1">
                    Re: {f.description} · {f.status}
                  </p>
                  <div className="mt-3 flex gap-2">
                    <input
                      value={replyText[f.commitment_id] ?? ''}
                      onChange={(e) =>
                        setReplyText((prev) => ({ ...prev, [f.commitment_id]: e.target.value }))
                      }
                      onKeyDown={(e) => e.key === 'Enter' && sendReply(f.commitment_id)}
                      placeholder="Reply in your own words…"
                      className="flex-1 bg-black/40 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-primary/60"
                    />
                    <button
                      onClick={() => sendReply(f.commitment_id)}
                      disabled={replyingId === f.commitment_id || !(replyText[f.commitment_id] ?? '').trim()}
                      className="bg-primary text-white px-4 py-2 rounded-lg text-sm hover:bg-primary/80 transition-colors disabled:opacity-40"
                    >
                      {replyingId === f.commitment_id ? '…' : 'Reply'}
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* End-of-day check-in */}
        <section>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-semibold text-white">End-of-day check-in</h2>
            {checkin?.completed && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
                Completed
              </span>
            )}
          </div>

          <div className="glass-panel flex flex-col" style={{ height: '60vh' }}>
            <div ref={scrollRef} className="flex-1 overflow-y-auto p-5 space-y-4">
              {(checkin?.conversation ?? []).map((turn, i) => (
                <div
                  key={i}
                  className={`flex ${turn.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[80%] px-4 py-3 rounded-xl text-sm leading-relaxed ${
                      turn.role === 'user'
                        ? 'bg-primary/20 border border-primary/30 text-white'
                        : 'bg-gray-800/60 border border-gray-700 text-gray-200'
                    }`}
                  >
                    {turn.content}
                  </div>
                </div>
              ))}
              {sending && (
                <div className="flex justify-start">
                  <div className="bg-gray-800/60 border border-gray-700 px-4 py-3 rounded-xl">
                    <span className="flex gap-1">
                      {[0, 1, 2].map((i) => (
                        <span
                          key={i}
                          className="w-2 h-2 bg-gray-500 rounded-full animate-bounce"
                          style={{ animationDelay: `${i * 150}ms` }}
                        />
                      ))}
                    </span>
                  </div>
                </div>
              )}
            </div>

            {error && (
              <p role="alert" className="text-danger text-xs px-5 pb-2">
                {error}
              </p>
            )}

            <div className="flex gap-2 p-4 border-t border-gray-800">
              <input
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
                placeholder={checkin?.completed ? 'Check-in complete' : 'Tell me what you worked on today…'}
                disabled={sending || checkin?.completed}
                className="flex-1 bg-gray-900 border border-gray-700 rounded-lg px-4 py-2.5 text-white placeholder-gray-500 focus:outline-none focus:border-primary transition-colors disabled:opacity-50"
              />
              <button
                onClick={sendMessage}
                disabled={sending || checkin?.completed || !message.trim()}
                className="bg-primary text-white px-5 py-2.5 rounded-lg hover:bg-primary/80 transition-colors disabled:opacity-40 font-medium"
              >
                Send
              </button>
            </div>
          </div>

          {!checkin?.completed && (checkin?.conversation.length ?? 0) > 1 && (
            <button
              onClick={completeCheckin}
              className="mt-3 text-sm text-gray-400 hover:text-emerald-400 transition-colors"
            >
              Mark check-in complete →
            </button>
          )}
        </section>
      </div>
    </main>
  );
}
