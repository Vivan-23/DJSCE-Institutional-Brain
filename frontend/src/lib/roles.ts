'use client';
import { useEffect, useState } from 'react';
import { apiFetch, getToken } from '@/lib/api';

/** Backend role ids (auth.py) → DJSCE display names. Display only; permissions live in the backend. */
export type Role = 'student' | 'employee' | 'manager' | 'admin';

export const ROLE_LABEL: Record<Role, string> = {
  student: 'Student',
  employee: 'Faculty',
  manager: 'Committee Coordinator',
  admin: 'System Administrator',
};

export function isStaffRole(role: string | undefined | null): boolean {
  return role === 'employee' || role === 'manager' || role === 'admin';
}

export interface Me {
  id: string;
  email: string;
  full_name: string | null;
  role: Role;
}

let cached: { token: string; me: Me } | null = null;

/**
 * The signed-in user, or null while loading / signed out. Pass the caller's
 * logged-in flag so the hook refetches after a client-side login; results are
 * cached per token so a different user never sees a stale role.
 */
export function useMe(loggedIn = true): Me | null {
  const token = loggedIn ? getToken() : null;
  const [state, setState] = useState<{ token: string; me: Me } | null>(cached);

  useEffect(() => {
    if (!token || cached?.token === token) return;
    apiFetch('/api/v1/auth/me')
      .then((r) => (r.ok ? r.json() : null))
      .then((d: Me | null) => {
        if (!d) return;
        cached = { token, me: d };
        setState(cached);
      })
      .catch(() => {});
  }, [token]);

  if (!token) return null;
  if (state?.token === token) return state.me;
  return cached?.token === token ? cached.me : null;
}

/** Call on logout so the next sign-in doesn't see the previous user's role. */
export function clearMe(): void {
  cached = null;
}
