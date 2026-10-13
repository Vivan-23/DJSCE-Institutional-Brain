'use client';
import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { setToken, API_BASE } from '@/lib/api';
import { useCompany } from '@/lib/useCompany';

type Mode = 'login' | 'register';

export default function LoginPage() {
  const router = useRouter();
  const company = useCompany();
  const [mode, setMode] = useState<Mode>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const fillDemo = () => {
    setEmail('demo@example.com');
    setPassword('demo123');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    const endpoint =
      mode === 'login' ? '/api/v1/auth/login' : '/api/v1/auth/register';
    const body =
      mode === 'login'
        ? { email, password }
        : { email, password, full_name: fullName };

    try {
      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail ?? 'Authentication failed');
      }
      setToken(data.access_token);
      router.push('/');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 flex flex-col items-center justify-center p-4">
      <div className="glass-panel p-8 w-full max-w-md border border-slate-800 shadow-xl space-y-6">
        {/* Institutional Logo & Identity */}
        <div className="text-center">
          <div className="w-14 h-14 rounded-xl bg-blue-600/15 border border-blue-500/40 flex items-center justify-center mx-auto mb-3 shadow-xs">
            <span className="text-blue-400 font-bold text-xl tracking-wider">{company.short_code}</span>
          </div>
          <h1 className="text-xl font-bold text-slate-100 tracking-tight">{company.name}</h1>
          <p className="text-slate-400 text-xs mt-1">
            Institutional Knowledge, Governance Intelligence &amp; Decision Support
          </p>
          <div className="mt-2.5 inline-block px-2.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-[10px] text-amber-400 font-medium">
            DEMONSTRATION PROTOTYPE · NOT AN OFFICIAL COLLEGE SYSTEM
          </div>
        </div>

        {/* Tab switcher */}
        <div className="flex bg-slate-900 rounded-lg p-1 border border-slate-800">
          {(['login', 'register'] as Mode[]).map((m) => (
            <button
              key={m}
              onClick={() => { setMode(m); setError(''); }}
              className={`flex-1 py-1.5 rounded-md text-xs font-semibold transition-colors cursor-pointer ${
                mode === m
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {m === 'login' ? 'Sign In' : 'Register Account'}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} className="space-y-3.5">
          {mode === 'register' && (
            <input
              type="text"
              placeholder="Full Name (e.g. Prof. Academic Lead)"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              required
              aria-label="Full name"
              className="w-full bg-slate-900 border border-slate-700/80 rounded-md px-3.5 py-2 text-xs sm:text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
            />
          )}
          <input
            type="email"
            placeholder="Academic Email Address"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            aria-label="Email address"
            className="w-full bg-slate-900 border border-slate-700/80 rounded-md px-3.5 py-2 text-xs sm:text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            aria-label="Password"
            className="w-full bg-slate-900 border border-slate-700/80 rounded-md px-3.5 py-2 text-xs sm:text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
          />

          {error && (
            <p role="alert" className="text-rose-400 text-xs">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 text-white py-2.5 rounded-md hover:bg-blue-500 transition-colors disabled:opacity-50 font-semibold text-xs sm:text-sm cursor-pointer shadow-xs"
          >
            {loading
              ? 'Authenticating…'
              : mode === 'login'
              ? 'Access Institutional Workspace'
              : 'Register New Academic Account'}
          </button>

          {mode === 'login' && (
            <button
              type="button"
              onClick={fillDemo}
              className="w-full bg-slate-800/80 text-slate-300 py-2 rounded-md hover:bg-slate-700/80 transition-colors text-xs border border-slate-700 cursor-pointer"
            >
              Fill Demo Evaluation Credentials
            </button>
          )}
        </form>

        {mode === 'login' && (
          <p className="text-center text-slate-500 text-[11px]">
            Demo credentials: <span className="text-slate-300 font-mono">demo@example.com</span> /{' '}
            <span className="text-slate-300 font-mono">demo123</span>
          </p>
        )}
      </div>
    </div>
  );
}
