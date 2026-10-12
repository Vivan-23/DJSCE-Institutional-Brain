'use client';
import React, { useCallback, useEffect, useState, useSyncExternalStore } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { clearToken, getToken } from '@/lib/api';
import { useCompany } from '@/lib/useCompany';

const NAV = [
  { href: '/', label: 'Governance Overview' },
  { href: '/chat', label: 'Institutional Assistant' },
  { href: '/meetings', label: 'Meetings & Minutes' },
  { href: '/commitments', label: 'Action Commitments' },
  { href: '/relationships', label: 'Knowledge Graph' },
  { href: '/assistant', label: 'Faculty Desk (PA)' },
  { href: '/skills', label: 'Institutional Procedures' },
  { href: '/sources', label: 'Document Repositories' },
];

const subscribe = (cb: () => void) => {
  window.addEventListener('storage', cb);
  return () => window.removeEventListener('storage', cb);
};

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const company = useCompany();
  const [mobileOpen, setMobileOpen] = useState(false);
  const loggedIn = useSyncExternalStore(
    subscribe,
    useCallback(() => !!getToken(), []),
    () => false,
  );

  // Close mobile drawer on route change
  const [prevPathname, setPrevPathname] = useState(pathname);
  if (prevPathname !== pathname) {
    setPrevPathname(pathname);
    setMobileOpen(false);
  }

  // Close drawer on escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMobileOpen(false);
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  if (pathname === '/login') return null;

  const handleLogout = () => {
    clearToken();
    router.push('/login');
  };

  const navContent = (
    <>
      {/* Institutional Brand Header */}
      <div className="mb-6 pb-4 border-b border-slate-800/80">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-blue-600/15 border border-blue-500/40 flex items-center justify-center shrink-0 shadow-xs">
            <span className="text-blue-400 font-bold text-xs tracking-wider">{company.short_code}</span>
          </div>
          <div className="min-w-0">
            <h2 className="text-sm font-bold text-slate-100 tracking-tight leading-tight truncate">
              {company.name}
            </h2>
            <p className="text-[11px] text-slate-400 font-medium truncate mt-0.5">
              D. J. Sanghvi College of Engg.
            </p>
          </div>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 space-y-1 overflow-y-auto pr-1" aria-label="Main navigation">
        {NAV.map(({ href, label }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              onClick={() => setMobileOpen(false)}
              className={`flex items-center px-3.5 py-2.5 rounded-md text-xs font-medium transition-all duration-150 ${
                active
                  ? 'bg-blue-600/15 text-blue-400 border border-blue-500/30 shadow-xs'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
              }`}
              aria-current={active ? 'page' : undefined}
            >
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Institutional Prototype Notice & Session */}
      <div className="mt-auto pt-4 border-t border-slate-800/80 space-y-3 shrink-0">
        <div className="px-2.5 py-2 rounded bg-slate-900/60 border border-slate-800 text-[10px] text-slate-400 leading-relaxed">
          <span className="font-semibold text-slate-300">DEMO PROTOTYPE</span>
          <p className="mt-0.5 text-slate-400">Decision support &amp; governance intelligence testbed.</p>
        </div>

        {loggedIn ? (
          <div className="flex items-center justify-between pt-1">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-7 h-7 rounded bg-slate-800 border border-slate-700 flex items-center justify-center text-[10px] font-bold text-blue-400 shrink-0">
                DS
              </div>
              <div className="min-w-0">
                <p className="text-xs font-medium text-slate-200 truncate">Academic Session</p>
                <p className="text-[10px] text-slate-400 truncate">Authenticated</p>
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="text-[11px] text-slate-400 hover:text-rose-400 transition-colors px-1 py-0.5 cursor-pointer"
              aria-label="Log out"
            >
              Logout
            </button>
          </div>
        ) : (
          <Link
            href="/login"
            onClick={() => setMobileOpen(false)}
            className="block text-xs text-center py-2 rounded bg-blue-600/20 border border-blue-500/40 text-blue-400 hover:bg-blue-600/30 transition-colors font-medium"
          >
            Sign in to Workspace →
          </Link>
        )}
      </div>
    </>
  );

  return (
    <>
      {/* Mobile Top Header Bar (Shown only on screens < lg) */}
      <div className="lg:hidden bg-slate-950 border-b border-slate-800 px-4 py-3 flex items-center justify-between z-20 shrink-0">
        <div className="flex items-center gap-2.5 min-w-0">
          <button
            type="button"
            onClick={() => setMobileOpen((prev) => !prev)}
            aria-label={mobileOpen ? 'Close navigation' : 'Open navigation'}
            className="p-1.5 rounded-md bg-slate-900 text-slate-300 hover:text-white border border-slate-800 transition-colors cursor-pointer"
          >
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              xmlns="http://www.w3.org/2000/svg"
            >
              {mobileOpen ? (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              )}
            </svg>
          </button>
          <div className="flex items-center gap-2 min-w-0">
            <div className="w-7 h-7 rounded bg-blue-600/20 border border-blue-500/40 flex items-center justify-center shrink-0">
              <span className="text-blue-400 font-bold text-[10px]">{company.short_code}</span>
            </div>
            <span className="font-bold text-xs sm:text-sm text-slate-100 truncate">
              {company.name}
            </span>
          </div>
        </div>

        {loggedIn && (
          <button
            onClick={handleLogout}
            className="text-[11px] text-slate-400 hover:text-rose-400 transition-colors px-2 py-1"
          >
            Logout
          </button>
        )}
      </div>

      {/* Mobile Overlay & Slide-in Drawer */}
      {mobileOpen && (
        <div
          role="dialog"
          aria-modal="true"
          className="lg:hidden fixed inset-0 z-50 flex"
        >
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/70 backdrop-blur-xs transition-opacity"
            onClick={() => setMobileOpen(false)}
            aria-hidden="true"
          />

          {/* Drawer content */}
          <aside className="relative w-72 max-w-[85vw] h-full bg-slate-950 border-r border-slate-800 p-5 flex flex-col z-50 shadow-2xl">
            <div className="flex items-center justify-between mb-4 pb-2 border-b border-slate-800 lg:hidden">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Navigation Menu</span>
              <button
                type="button"
                onClick={() => setMobileOpen(false)}
                className="p-1 rounded text-slate-400 hover:text-white"
                aria-label="Close menu"
              >
                ✕
              </button>
            </div>
            {navContent}
          </aside>
        </div>
      )}

      {/* Desktop Persistent Sidebar (Fixed on lg and up) */}
      <aside className="hidden lg:flex w-64 h-full bg-slate-950 border-r border-slate-800 flex-col p-5 shrink-0 z-10">
        {navContent}
      </aside>
    </>
  );
}
