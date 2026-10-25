'use client';
import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { apiFetch } from '@/lib/api';
import { isStaffRole, loginPasswordForFirstLogin, markPasswordChanged, useMe } from '@/lib/roles';

const MIN = 8;
const field =
  'w-full bg-slate-900 border border-slate-700 rounded-lg px-3.5 h-12 text-base text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500';

/** First login (temporary password → your own) and the everyday "Change password". */
export default function PasswordPage() {
  const router = useRouter();
  const me = useMe();
  const firstLogin = !!me?.must_change_password;
  // The temporary password typed on the login page, if we still have it in memory.
  const [given] = useState(() => loginPasswordForFirstLogin());
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [again, setAgain] = useState('');
  const [show, setShow] = useState(false);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const name = (me?.full_name || '').trim();
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (next.length < MIN) return setError(`Please use at least ${MIN} characters.`);
    if (next !== again) return setError('The two new passwords are not the same. Please type them again.');
    setSaving(true);
    try {
      const res = await apiFetch('/api/v1/auth/change-password', {
        method: 'POST',
        body: JSON.stringify({ current_password: given ?? current, new_password: next }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail ?? 'Your password could not be changed. Please try again.');
      }
      markPasswordChanged();
      router.replace(isStaffRole(me?.role) ? '/' : '/helpdesk');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Your password could not be changed. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <main className="p-4 sm:p-6 md:p-10 max-w-md mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-100 tracking-[-0.02em]">
          {firstLogin ? `Welcome${name ? `, ${name}` : ''}` : 'Change your password'}
        </h1>
        <p className="text-slate-400 text-base mt-2">
          {firstLogin
            ? 'Before you start, please choose your own password. You will use it every time you sign in.'
            : 'Choose a new password for signing in.'}
        </p>
      </div>

      <form onSubmit={submit} className="glass-panel p-5 sm:p-6 space-y-4">
        {!given && (
          <label className="block space-y-1.5">
            <span className="block text-sm font-medium text-slate-200">
              {firstLogin ? 'The password you were given' : 'Your current password'}
            </span>
            <input type={show ? 'text' : 'password'} autoComplete="current-password" required value={current}
              onChange={(e) => setCurrent(e.target.value)} className={field} />
          </label>
        )}
        <label className="block space-y-1.5">
          <span className="block text-sm font-medium text-slate-200">New password</span>
          <input type={show ? 'text' : 'password'} autoComplete="new-password" required value={next}
            onChange={(e) => setNext(e.target.value)} className={field} />
          <span className="block text-[0.8125rem] text-slate-400">At least {MIN} characters.</span>
        </label>
        <label className="block space-y-1.5">
          <span className="block text-sm font-medium text-slate-200">Type the new password again</span>
          <input type={show ? 'text' : 'password'} autoComplete="new-password" required value={again}
            onChange={(e) => setAgain(e.target.value)} className={field} />
        </label>
        <label className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
          <input type="checkbox" checked={show} onChange={(e) => setShow(e.target.checked)} className="w-4 h-4" />
          Show passwords
        </label>
        {error && <p role="alert" className="text-rose-400 text-sm">{error}</p>}
        <button type="submit" disabled={saving}
          className="w-full h-12 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-base font-semibold disabled:opacity-40 cursor-pointer">
          {saving ? 'Saving…' : firstLogin ? 'Save and continue' : 'Save new password'}
        </button>
        {!firstLogin && (
          <button type="button" onClick={() => router.back()} className="w-full h-11 text-sm text-slate-400 hover:text-slate-200 cursor-pointer">
            Cancel
          </button>
        )}
      </form>
    </main>
  );
}
