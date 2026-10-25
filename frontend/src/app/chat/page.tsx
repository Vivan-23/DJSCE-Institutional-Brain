'use client';
import React, { Suspense, useRef, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { apiFetch } from '@/lib/api';
import { renderBold } from '@/lib/renderBold';
import SourceList, { type Source } from '@/components/knowledge/SourceList';
import { isStaffRole, useMe } from '@/lib/roles';

/** One task change the assistant made, with what it was before so it can be undone. */
interface TaskUpdate {
  commitment_id: string;
  description?: string | null;
  status: string | null;
  progress?: number;
  remaining?: string | null;
  blocked_reason?: string | null;
  new?: boolean;
  before?: Record<string, unknown> | null;
  undone?: boolean;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  updates?: TaskUpdate[];
}

const STATUS_WORD: Record<string, string> = {
  open: 'not started', in_progress: 'in progress', blocked: 'stuck', review: 'done (waiting for confirmation)',
  done: 'completed', dropped: 'removed',
};

const STAFF_EXAMPLES = [
  'What are my classes tomorrow?',
  'Finished the C31 lab marks today.',
  'When is Term Test 2?',
  'What is the procedure for applying for leave?',
];

const STUDENT_EXAMPLES = [
  'What courses are in Semester V of Computer Engineering?',
  'Which electives are offered in Semester VI?',
  'When is Term Test 2?',
  'Which companies recruit from the department?',
];

function Chat() {
  const me = useMe();
  // Today links here with ?q=…; the text is pre-filled, never sent automatically.
  const initialQuery = useSearchParams().get('q') ?? '';
  const staff = isStaffRole(me?.role);
  const [messages, setMessages] = useState<Message[]>([]);
  const [query, setQuery] = useState(initialQuery);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const send = async (textToSend?: string) => {
    const text = (textToSend ?? query).trim();
    if (!text || loading) return;
    setMessages((prev) => [...prev, { role: 'user', content: text }]);
    setQuery('');
    setLoading(true);
    try {
      const res = await apiFetch('/api/v1/assistant/message', { method: 'POST', body: JSON.stringify({ text }) });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail ?? 'Something went wrong.');
      setMessages((prev) => [...prev, { role: 'assistant', content: data.reply, sources: data.sources ?? [], updates: data.updates ?? [] }]);
    } catch (err: unknown) {
      const why = err instanceof Error ? err.message : 'Something went wrong.';
      setMessages((prev) => [...prev, { role: 'assistant', content: `Sorry, that didn't work (${why}). Please try again.` }]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const undo = async (msgIndex: number, u: TaskUpdate) => {
    const res = await apiFetch('/api/v1/assistant/undo', {
      method: 'POST',
      body: JSON.stringify({ commitment_id: u.commitment_id, before: u.before ?? null, new: !!u.new }),
    });
    if (!res.ok) return;
    setMessages((prev) => prev.map((m, i) => i !== msgIndex ? m : {
      ...m, updates: m.updates?.map((x) => x.commitment_id === u.commitment_id ? { ...x, undone: true } : x),
    }));
  };

  const fresh = messages.length === 0 && !loading;

  return (
    <main className="px-4 sm:px-6 pt-6 pb-4 max-w-3xl mx-auto flex flex-col h-full min-h-[520px] w-full">
      <div className="mb-4 shrink-0">
        <h1 className="text-xl sm:text-2xl font-semibold text-slate-100 tracking-[-0.02em]">Assistant</h1>
        <p className="text-sm text-slate-400 mt-1">
          {staff
            ? 'Ask a question, check your classes, or tell me what you did today. I will update your tasks and show you what changed.'
            : 'Ask a question about the college. Answers come from public college information, with sources.'}
        </p>
      </div>

      <div className="flex-1 min-h-[260px] overflow-y-auto -mx-2 px-2 space-y-5 pb-4" aria-live="polite">
        {fresh && (
          <div className="space-y-2">
            <p className="text-sm text-slate-400">For example:</p>
            <div className="grid sm:grid-cols-2 gap-2">
              {(staff ? STAFF_EXAMPLES : STUDENT_EXAMPLES).map((q) => (
                <button key={q} onClick={() => setQuery(q)}
                  className="text-left px-4 py-3 rounded-lg border border-slate-700 hover:border-slate-500 text-sm text-slate-200 cursor-pointer">
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) =>
          msg.role === 'user' ? (
            <div key={i} className="flex justify-end">
              <div className="max-w-[85%] rounded-xl px-4 py-2.5 text-base leading-relaxed bg-blue-600/15 border border-blue-500/20 text-slate-100 whitespace-pre-wrap">
                {msg.content}
              </div>
            </div>
          ) : (
            <div key={i} className="space-y-3">
              <div className="text-base leading-relaxed text-slate-200 whitespace-pre-wrap">{renderBold(msg.content)}</div>
              {(msg.updates?.length ?? 0) > 0 && (
                <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3 space-y-2" aria-label="Task changes">
                  <p className="text-sm font-semibold text-emerald-300">I changed these tasks</p>
                  {msg.updates!.map((u) => (
                    <div key={u.commitment_id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
                      <span className={`min-w-0 ${u.undone ? 'line-through text-slate-500' : 'text-slate-100'}`}>
                        {u.new ? 'New task: ' : ''}{u.description ?? 'Task'}
                        {!u.new && u.status && <span className="text-slate-400"> → {STATUS_WORD[u.status] ?? u.status}{typeof u.progress === 'number' ? `, ${u.progress}%` : ''}</span>}
                      </span>
                      {u.undone ? (
                        <span className="text-[0.8125rem] text-slate-500">Undone</span>
                      ) : (
                        <button onClick={() => undo(i, u)}
                          className="px-3 h-8 rounded-md border border-slate-600 text-[0.8125rem] text-slate-200 hover:border-rose-400 hover:text-rose-300 cursor-pointer">
                          Undo
                        </button>
                      )}
                    </div>
                  ))}
                  <Link href="/commitments?view=tasks" className="inline-block text-[0.8125rem] text-blue-300 hover:underline">See all my work →</Link>
                </div>
              )}
              {msg.sources && msg.sources.length > 0 && <SourceList sources={msg.sources} />}
            </div>
          ),
        )}

        {loading && <p className="text-sm text-slate-400">Working on it…</p>}
      </div>

      <form className="shrink-0 space-y-2" onSubmit={(e) => { e.preventDefault(); send(); }}>
        <label htmlFor="chat-input" className="sr-only">Type a message</label>
        <div className="flex items-end gap-2">
          <textarea
            id="chat-input"
            ref={inputRef}
            rows={2}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }}
            placeholder={staff ? 'Ask something, or tell me what you did today…' : 'Ask a question…'}
            disabled={loading}
            className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3.5 py-2.5 text-base text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 disabled:opacity-50 resize-none"
          />
          <button type="submit" disabled={loading || !query.trim()}
            className="h-12 px-5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-base font-semibold disabled:opacity-40 cursor-pointer shrink-0">
            Send
          </button>
        </div>
        <p className="text-center text-[0.75rem] text-slate-500">Answers can be wrong. Check the sources shown under an answer.</p>
      </form>
    </main>
  );
}

export default function ChatPage() {
  return (
    <Suspense fallback={<main className="p-10 text-sm text-slate-400">Loading…</main>}>
      <Chat />
    </Suspense>
  );
}
