'use client';
import React, { useRef, useState } from 'react';
import { apiFetch } from '@/lib/api';
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

  return (
    <main className="p-4 sm:p-6 md:p-8 max-w-4xl mx-auto flex flex-col h-full min-h-[520px] w-full">
      {/* Header */}
      <div className="mb-3 shrink-0">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl sm:text-2xl font-semibold text-slate-100 tracking-[-0.02em]">
              Institutional Knowledge Assistant
            </h1>
            <p className="text-xs sm:text-sm text-slate-400 mt-0.5">
              Ask questions about institutional documents, committee decisions, procedures and assigned responsibilities.
            </p>
          </div>
          <span className="hidden sm:inline-block px-2.5 py-1 rounded text-[12px] font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/30">
            {studentScope ? 'Public knowledge only' : 'RAG Grounded'}
          </span>
        </div>
      </div>

      {/* Suggested prompts strip */}
      <div className="mb-3 shrink-0">
        <p className="text-[12px] font-medium text-slate-400 mb-1.5">
          Suggested Institutional Inquiries
        </p>
        <div className="flex flex-wrap gap-1.5">
          {(studentScope ? STUDENT_QUERIES : SUGGESTED_QUERIES).map((sq, i) => (
            <button
              key={i}
              onClick={() => handleSend(sq)}
              disabled={loading}
              className="px-2.5 py-1 rounded bg-slate-900/90 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-800 text-xs transition-colors text-left cursor-pointer disabled:opacity-50"
            >
              {sq}
            </button>
          ))}
        </div>
      </div>

      {/* Messages Scroll Area with custom dark scrollbar */}
      <div className="glass-panel flex-1 min-h-[260px] overflow-y-auto p-4 sm:p-6 space-y-4 mb-3">
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[90%] sm:max-w-[82%] rounded-lg px-4 py-3 text-xs sm:text-sm leading-relaxed ${
                msg.role === 'user'
                  ? 'bg-blue-600/20 border border-blue-500/40 text-slate-100'
                  : 'bg-slate-900/90 border border-slate-800 text-slate-200'
              }`}
            >
              {msg.role === 'assistant' && (
                <div className="flex items-center gap-1.5 mb-1.5 text-[11px] font-semibold text-blue-400">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-400 inline-block" />
                  Institutional Assistant
                </div>
              )}
              <div className="whitespace-pre-wrap">{msg.content}</div>
              {msg.role === 'assistant' && msg.sources && <SourceList sources={msg.sources} />}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-slate-900/80 border border-slate-800 px-4 py-2.5 rounded-lg flex items-center gap-2 text-xs text-slate-400">
              <span className="flex gap-1">
                {[0, 1, 2].map((i) => (
                  <span
                    key={i}
                    className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce"
                    style={{ animationDelay: `${i * 150}ms` }}
                  />
                ))}
              </span>
              <span>Consulting institutional vector index and knowledge graph…</span>
            </div>
          </div>
        )}
      </div>

      {/* Error alert */}
      {error && (
        <p role="alert" className="text-rose-400 text-xs mb-2 px-1">
          {error}
        </p>
      )}

      {/* Input row */}
      <div className="shrink-0 flex gap-2">
        <label htmlFor="chat-input" className="sr-only">
          Query Institutional Knowledge
        </label>
        <input
          id="chat-input"
          ref={inputRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
          placeholder="Ask about Academic Council decisions, laboratory SOPs, or committee commitments…"
          disabled={loading}
          className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-xs sm:text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors disabled:opacity-50"
        />
        <button
          onClick={() => handleSend()}
          disabled={loading || !query.trim()}
          aria-label="Send query"
          className="bg-blue-600 hover:bg-blue-500 text-white px-5 py-2.5 rounded-lg text-xs sm:text-sm font-semibold transition-colors disabled:opacity-40 cursor-pointer shrink-0"
        >
          Send
        </button>
      </div>
    </main>
  );
}
