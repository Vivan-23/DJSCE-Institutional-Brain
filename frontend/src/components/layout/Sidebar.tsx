'use client';
import React, { useCallback, useSyncExternalStore } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { clearToken, getToken } from '@/lib/api';
import { useCompany } from '@/lib/useCompany';

const NAV = [
  { href: '/', label: 'Active Feed' },
  { href: '/relationships', label: 'Graph Map' },
  { href: '/meetings', label: 'Meetings' },
  { href: '/commitments', label: 'Commitments' },
  { href: '/assistant', label: 'Your Assistant' },
  { href: '/skills', label: 'Skills' },
  { href: '/chat', label: 'RAG Chat' },
  { href: '/sources', label: 'Data Sources' },
];

// Subscribe to auth-token changes (other tabs fire 'storage'); re-reads on
// navigation too since usePathname re-renders the component.
const subscribe = (cb: () => void) => {
  window.addEventListener('storage', cb);
  return () => window.removeEventListener('storage', cb);
};

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const company = useCompany();
  const loggedIn = useSyncExternalStore(
    subscribe,
    useCallback(() => !!getToken(), []),
    () => false, // server snapshot: assume logged out to avoid hydration mismatch
  );

  // Don't render on the login page (full-page auth layout)
  if (pathname === '/login') return null;

  const handleLogout = () => {
    clearToken();
    router.push('/login');
  };

  return (
    <aside className="w-64 h-full bg-black border-r border-gray-800 flex flex-col p-6 shrink-0">
      {/* Brand */}
      <div className="flex items-center mb-10">
        <div className="w-8 h-8 rounded-lg bg-primary/20 border border-primary flex items-center justify-center mr-3">
          <span className="text-primary font-bold text-sm">{company.short_code}</span>
        </div>
        <h2 className="text-xl font-bold text-white tracking-wide">
          {company.name}
        </h2>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1" aria-label="Main navigation">
        {NAV.map(({ href, label }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center px-4 py-3 rounded-md text-sm transition-all duration-150 ${
                active
                  ? 'bg-primary/10 text-primary border border-primary/20'
                  : 'text-gray-400 hover:text-primary hover:bg-gray-900/50'
              }`}
              aria-current={active ? 'page' : undefined}
            >
              {label}
            </Link>
          );
        })}
      </nav>

      {/* User section */}
      <div className="mt-auto pt-6 border-t border-gray-800">
        {loggedIn ? (
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-primary to-blue-500 shrink-0" />
              <div>
                <p className="text-sm font-medium text-white">Workspace</p>
                <p className="text-xs text-gray-500">Active session</p>
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="text-xs text-gray-500 hover:text-danger transition-colors"
              aria-label="Log out"
            >
              Logout
            </button>
          </div>
        ) : (
          <Link
            href="/login"
            className="text-sm text-primary hover:underline"
          >
            Sign in →
          </Link>
        )}
      </div>
    </aside>
  );
}
