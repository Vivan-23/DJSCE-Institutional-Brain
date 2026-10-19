'use client';
import React, { useRef, useState } from 'react';
import { apiFetch } from '@/lib/api';
import { Badge } from '@/components/ui/Badge';
import SourceList, { type Source } from '@/components/knowledge/SourceList';
import { isStaffRole, useMe } from '@/lib/roles';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
}

const WELCOME: Message = {
  role: 'assistant',
  content:
    'Welcome to the DJSCE Institutional Assistant. Ask questions about institutional documents, committee decisions, procedures, and assigned responsibilities grounded in indexed records.',
};

const SUGGESTED_QUERIES = [
  'What decisions were made in the latest Academic Council meeting?',
  'Which actions remain pending after the curriculum review?',
  'What procedure was documented for laboratory examination moderation?',
  'Which source supports the decision about the proposed elective?',
  'Summarize the responsibilities assigned during the IQAC review.',
];

const STUDENT_QUERIES = [
  'What courses are in Semester V of Computer Engineering?',
  'Which electives are offered in Semester VI?',
  'What are the Program Outcomes of Information Technology?',
  'Which companies recruit from the department?',
];

// LLM answers use **bold** markdown; render just that, everything else stays plain text.
function renderBold(text: string) {
  return text.split(/\*\*(.+?)\*\*/g).map((part, i) =>
    i % 2 ? <strong key={i} className="font-semibold text-slate-100">{part}</strong> : part,
  );
}

export default function ChatPage() {
  const me = useMe();
  const studentScope = me !== null && !isStaffRole(me.role);
  const [messages, setMessages] = useState<Message[]>([WELCOME]);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSend = async (textToSend?: string) => {
    const text = (textToSend ?? query).trim();
    if (!text || loading) return;

    const outgoing: Message[] = [...messages, { role: 'user', content: text }];
    setMessages(outgoing);
    setQuery('');
    setLoading(true);
    setError(null);

    try {
      const res = await apiFetch('/api/v1/chat/', {
        method: 'POST',
        body: JSON.stringify({ messages: outgoing.map(({ role, content }) => ({ role, content })) }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail ?? `HTTP ${res.status}`);
      }

      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: data.response, sources: data.sources ?? [] },
      ]);
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : 'Could not reach the institutional intelligence service.';
      setError(msg);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `Notice: Query could not be completed (${msg}). Verify that backend and vector stores are reachable.`,
        },
      ]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const fresh = messages.length <= 1 && !loading;

  return (
    <main className="px-4 sm:px-6 pt-6 pb-4 max-w-3xl mx-auto flex flex-col h-full min-h-[520px] w-full">
      {/* Header */}
      <div className="mb-4 shrink-0 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-semibold text-slate-100 tracking-[-0.02em]">Assistant</h1>
          <p className="text-[13px] text-slate-400 mt-0.5">
            Answers grounded in institutional documents, committee decisions and approved procedures, with sources.
          </p>
        </div>
        <span className="hidden sm:inline-flex"><Badge tone="accent">{studentScope ? 'Public knowledge only' : 'Cited answers'}</Badge></span>
      </div>

      {/* Conversation */}
      <div className="flex-1 min-h-[260px] overflow-y-auto -mx-2 px-2 space-y-6 pb-4">
        {messages.map((msg, i) =>
          msg.role === 'user' ? (
            <div key={i} className="flex justify-end">
              <div className="max-w-[85%] rounded-xl px-4 py-2.5 text-[13px] leading-relaxed bg-white/[0.06] border border-white/[0.06] text-slate-100 whitespace-pre-wrap">
                {msg.content}
              </div>
            </div>
          ) : (
            <div key={i} className="flex gap-3">
              <div className="w-6 h-6 mt-0.5 rounded-md bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center shrink-0" aria-hidden="true">
                <svg className="w-3.5 h-3.5 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z" />
                </svg>
              </div>
              <div className="min-w-0 flex-1 text-[14px] leading-relaxed text-slate-200">
                <p className="text-[12px] font-medium text-slate-400 mb-1">Assistant</p>
                <div className="whitespace-pre-wrap">{renderBold(msg.content)}</div>
                {msg.sources && <SourceList sources={msg.sources} />}
              </div>
            </div>
          ),
        )}

        {fresh && (
          <div className="grid sm:grid-cols-2 gap-2 pt-2">
            {(studentScope ? STUDENT_QUERIES : SUGGESTED_QUERIES).map((sq, i) => (
              <button
                key={i}
                onClick={() => handleSend(sq)}
                disabled={loading}
                className="text-left px-3.5 py-3 rounded-lg border border-white/[0.07] bg-white/[0.02] hover:bg-white/[0.05] hover:border-white/[0.12] text-[13px] text-slate-300 transition-colors cursor-pointer disabled:opacity-50"
              >
                {sq}
              </button>
            ))}
          </div>
        )}

        {loading && (
          <div className="flex gap-3 items-center text-[13px] text-slate-500">
            <span className="w-6 flex justify-center gap-0.5" aria-hidden="true">
              {[0, 1, 2].map((i) => (
                <span key={i} className="w-1 h-1 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: `${i * 150}ms` }} />
              ))}
            </span>
            Searching records…
          </div>
        )}
      </div>

      {error && (
        <p role="alert" className="text-rose-400 text-[12px] mb-2 px-1">
          {error}
        </p>
      )}

      {/* Composer */}
      <div className="shrink-0 flex items-center gap-2 rounded-xl border border-white/[0.09] bg-white/[0.03] p-1.5 pl-4 focus-within:border-blue-600 focus-within:shadow-[0_0_0_3px_rgba(94,106,210,0.2)] transition-colors">
        <label htmlFor="chat-input" className="sr-only">
          Ask a question
        </label>
        <input
          id="chat-input"
          ref={inputRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
          placeholder="Ask about decisions, procedures or commitments…"
          disabled={loading}
          className="flex-1 bg-transparent text-[14px] text-slate-100 placeholder-slate-500 !outline-none !border-0 !shadow-none disabled:opacity-50"
        />
        <button
          onClick={() => handleSend()}
          disabled={loading || !query.trim()}
          aria-label="Send question"
          className="bg-blue-600 hover:bg-blue-500 text-white h-8 px-4 rounded-lg text-[13px] font-medium transition-colors disabled:opacity-40 cursor-pointer shrink-0"
        >
          Send
        </button>
      </div>
      <p className="mt-2 text-center text-[11px] text-slate-600">Answers can be wrong. Check the cited sources.</p>
    </main>
  );
}
