'use client';
import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { setToken, API_BASE } from '@/lib/api';

type Mode = 'login' | 'register';

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const fillDemo = () => {
    setEmail('demo@companybrain.ai');
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
    <div className="min-h-screen bg-gradient-to-br from-black to-gray-900 flex items-center justify-center p-4">
      <div className="glass-panel p-8 w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-primary/20 border border-primary flex items-center justify-center mx-auto mb-4">
            <span className="text-primary font-bold text-2xl">CB</span>
          </div>
          <h1 className="text-2xl font-bold text-white">Company Brain</h1>
          <p className="text-gray-400 text-sm mt-1">
            Organizational Intelligence System
          </p>
        </div>

        {/* Tab switcher */}
        <div className="flex mb-6 bg-gray-900/60 rounded-lg p-1">
          {(['login', 'register'] as Mode[]).map((m) => (
            <button
              key={m}
              onClick={() => { setMode(m); setError(''); }}
              className={`flex-1 py-2 rounded-md text-sm font-medium transition-colors ${
                mode === m
                  ? 'bg-primary text-white'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              {m === 'login' ? 'Sign In' : 'Register'}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {mode === 'register' && (
            <input
              type="text"
              placeholder="Full Name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              required
              aria-label="Full name"
              className="w-full bg-gray-900 border border-gray-700 rounded-md px-4 py-2.5 text-white placeholder-gray-500 focus:outline-none focus:border-primary transition-colors"
            />
          )}
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            aria-label="Email address"
            className="w-full bg-gray-900 border border-gray-700 rounded-md px-4 py-2.5 text-white placeholder-gray-500 focus:outline-none focus:border-primary transition-colors"
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            aria-label="Password"
            className="w-full bg-gray-900 border border-gray-700 rounded-md px-4 py-2.5 text-white placeholder-gray-500 focus:outline-none focus:border-primary transition-colors"
          />

          {error && (
            <p role="alert" className="text-danger text-sm">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-primary text-white py-2.5 rounded-md hover:bg-primary/80 transition-colors disabled:opacity-50 font-medium"
          >
            {loading
              ? 'Please wait…'
              : mode === 'login'
              ? 'Sign In'
              : 'Create Account'}
          </button>

          {mode === 'login' && (
            <button
              type="button"
              onClick={fillDemo}
              className="w-full bg-gray-800 text-gray-300 py-2.5 rounded-md hover:bg-gray-700 transition-colors text-sm border border-gray-700"
            >
              Use Demo Credentials
            </button>
          )}
        </form>

        {mode === 'login' && (
          <p className="text-center text-gray-600 text-xs mt-6">
            Demo account: <span className="text-gray-400">demo@companybrain.ai</span>{' '}
            /{' '}
            <span className="text-gray-400">demo123</span>
          </p>
        )}
      </div>
    </div>
  );
}
