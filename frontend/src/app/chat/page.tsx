'use client';
import React, { useRef, useState } from 'react';
import { apiFetch } from '@/lib/api';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

const WELCOME: Message = {
  role: 'assistant',
  content:
    'Hello! I am Company Brain. Ask me anything about project dependencies, blockers, team activity, or organizational relationships.',
};

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([WELCOME]);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSend = async () => {
    const text = query.trim();
    if (!text || loading) return;

    const outgoing: Message[] = [...messages, { role: 'user', content: text }];
    setMessages(outgoing);
    setQuery('');
    setLoading(true);
    setError(null);

    try {
      const res = await apiFetch('/api/v1/chat/', {
        method: 'POST',
        body: JSON.stringify({ messages: outgoing }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail ?? `HTTP ${res.status}`);
      }

      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: data.response },
      ]);
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : 'Could not reach Company Brain.';
      setError(msg);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `Sorry, I ran into an issue: ${msg}`,
        },
      ]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  return (
    <main className="min-h-screen p-6 flex flex-col items-center justify-center">
      <div className="w-full max-w-3xl flex flex-col" style={{ height: '80vh' }}>
        <h1 className="text-2xl font-bold text-white mb-4">RAG Chat</h1>

        {/* Messages */}
        <div className="glass-panel flex-1 overflow-y-auto p-5 space-y-4 mb-4">
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] px-4 py-3 rounded-xl text-sm leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-primary/20 border border-primary/30 text-white'
                    : 'bg-gray-800/60 border border-gray-700 text-gray-200'
                }`}
              >
                {msg.content}
              </div>
            </div>
          ))}

          {loading && (
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

        {/* Error banner */}
        {error && (
          <p role="alert" className="text-danger text-xs mb-2 px-1">
            {error}
          </p>
        )}

        {/* Input row */}
        <div className="flex gap-2">
          <label htmlFor="chat-input" className="sr-only">
            Ask Company Brain
          </label>
          <input
            id="chat-input"
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
            placeholder="Ask about project risks, blockers, team activity…"
            disabled={loading}
            className="flex-1 bg-gray-900 border border-gray-700 rounded-lg px-4 py-2.5 text-white placeholder-gray-500 focus:outline-none focus:border-primary transition-colors disabled:opacity-50"
          />
          <button
            onClick={handleSend}
            disabled={loading || !query.trim()}
            aria-label="Send message"
            className="bg-primary text-white px-5 py-2.5 rounded-lg hover:bg-primary/80 transition-colors disabled:opacity-40 font-medium"
          >
            Send
          </button>
        </div>
      </div>
    </main>
  );
}
