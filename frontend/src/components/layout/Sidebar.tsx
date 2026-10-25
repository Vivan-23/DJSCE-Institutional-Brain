'use client';
import React, { useCallback, useEffect, useState, useSyncExternalStore } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { apiFetch, clearToken, getToken } from '@/lib/api';
import { useInstitution } from '@/lib/useInstitution';
import ThemeToggle from './ThemeToggle';
import InstitutionMark from './InstitutionMark';
import { clearMe, isCoordinatorRole, isStaffRole, ROLE_LABEL, useMe } from '@/lib/roles';

// `staff: true` items are hidden from students; `coordinator: true` items need Committee
// Coordinator or above; `roles` lists the exact roles that see an item (no inheritance by
// higher ranks, e.g. the Help Desk is for students and faculty only); `hideFor` keeps the faculty menu
// short (rarely used items stay reachable by URL). Cosmetic only: the backend refuses these requests anyway.
type NavItem = {
  href: string; label: string; icon: string; staff: boolean; coordinator?: boolean; admin?: boolean; roles?: string[]; hideFor?: string[];
};

// 24x24 stroke icon paths (lucide-style).
const ICON = {
  home: 'M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z',
  check: 'M9 11l3 3 8-8M20 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11',
  coffee: 'M17 8h1a4 4 0 0 1 0 8h-1M3 8h14v9a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4zM6 2v3M10 2v3M14 2v3',
  lifebuoy: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4.9 4.9l4.3 4.3M14.8 14.8l4.3 4.3M14.8 9.2l4.3-4.3M4.9 19.1l4.3-4.3',
  inbox: 'M22 12h-6l-2 3h-4l-2-3H2M5.5 5h13L22 12v6a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-6z',
  sparkle: 'M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9zM19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z',
  users: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8',
  book: 'M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5zM4 19.5A2.5 2.5 0 0 0 6.5 22H20v-5',
  file: 'M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zM14 3v5h5M9 13h6M9 17h6',
  graph: 'M6 7a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM18 9a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM12 21a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM7.5 6.2l9 1.6M7 6.8l4.2 10.4M17.2 8.8l-4.4 8.4',
  bell: 'M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 0 1-3.4 0',
  calendar: 'M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zM16 2v4M8 2v4M3 10h18',
  chart: 'M3 3v18h18M8 17V11M13 17V7M18 17v-4',
  shield: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z',
};

const NAV_GROUPS: { title?: string; items: NavItem[] }[] = [
  {
    items: [
      { href: '/', label: 'Today', icon: ICON.home, staff: true },
      { href: '/commitments', label: 'My Work', icon: ICON.check, staff: true },
      { href: '/assistant', label: 'End-of-day Check-in', icon: ICON.coffee, staff: true },
    ],
  },
  {
    title: 'Support',
    items: [
      { href: '/helpdesk', label: 'Help Desk', icon: ICON.lifebuoy, staff: false, roles: ['student', 'employee'], hideFor: ['employee'] },
      { href: '/tickets', label: 'Ticket Queue', icon: ICON.inbox, staff: true, roles: ['employee', 'admin'], hideFor: ['employee'] },
      { href: '/chat', label: 'Ask', icon: ICON.sparkle, staff: false },
    ],
  },
  {
    title: 'Knowledge',
    items: [
      { href: '/meetings', label: 'Meetings', icon: ICON.users, staff: true },
      { href: '/skills', label: 'Procedures', icon: ICON.book, staff: true, hideFor: ['employee'] },
      { href: '/sources', label: 'Documents', icon: ICON.file, staff: true },
      { href: '/relationships', label: 'Knowledge Graph', icon: ICON.graph, staff: true, hideFor: ['employee'] },
    ],
  },
  {
    title: 'Campus',
    items: [
      { href: '/notices', label: 'Notices', icon: ICON.bell, staff: false },
      { href: '/calendar', label: 'Calendar', icon: ICON.calendar, staff: false },
    ],
  },
  {
    title: 'Admin',
    items: [
      { href: '/timetables', label: 'Timetables', icon: ICON.calendar, staff: true, coordinator: true },
      { href: '/analytics', label: 'Analytics', icon: ICON.chart, staff: true, coordinator: true },
      { href: '/admin/users', label: 'Users', icon: ICON.shield, staff: true, coordinator: true, admin: true },
    ],
  },
];

function NavIcon({ d }: { d: string }) {
  return (
    <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={d} />
    </svg>
  );
}

const subscribe = (cb: () => void) => {
  window.addEventListener('storage', cb);
  return () => window.removeEventListener('storage', cb);
};

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const institution = useInstitution();
  const [mobileOpen, setMobileOpen] = useState(false);
  const loggedIn = useSyncExternalStore(
    subscribe,
    useCallback(() => !!getToken(), []),
    () => false,
  );
  const me = useMe(loggedIn);
  const staff = isStaffRole(me?.role);
  const coordinator = isCoordinatorRole(me?.role);
  const groups = NAV_GROUPS.map((g) => ({
    ...g,
    items: g.items.filter(
      (item) => (!item.staff || staff) && (!item.coordinator || coordinator) && (!item.admin || me?.role === 'admin') &&
        (!item.roles || (!!me && item.roles.includes(me.role))) && !(me && item.hideFor?.includes(me.role)),
    ),
  })).filter((g) => g.items.length > 0);
  // Faculty get one short list; section headings only help with the longer coordinator/admin menu.
  const navGroups = me?.role === 'employee' ? [{ items: groups.flatMap((g) => g.items) }] : groups;
  const initials = (me?.full_name || me?.email || '?')
    .split(/[\s@.]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase())
    .join('');

  // Unread notices badge: refreshed on navigation and when the Notices page marks one read.
  const [unread, setUnread] = useState(0);
  useEffect(() => {
    if (!loggedIn) return;
    const refresh = () =>
      apiFetch('/api/v1/notices/unread-count')
        .then((res) => (res.ok ? res.json() : { unread: 0 }))
        .then((d: { unread: number }) => setUnread(d.unread))
        .catch(() => {});
    refresh();
    window.addEventListener('notices-changed', refresh);
    return () => window.removeEventListener('notices-changed', refresh);
  }, [loggedIn, pathname]);

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
    clearMe();
    router.push('/login');
  };

  const navContent = (
    <>
      {/* Workspace header */}
      <div className="flex items-center gap-2.5 px-2 pb-4">
        <InstitutionMark institution={institution} size="sm" />
        <div className="min-w-0">
          <h2 className="text-[0.8125rem] font-medium text-slate-100 leading-tight truncate">{institution.name}</h2>
          <p className="text-[0.6875rem] text-slate-500 truncate">{institution.full_name}</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto -mx-1 px-1 space-y-4" aria-label="Main navigation">
        {navGroups.map((group, i) => (
          <div key={group.title ?? i}>
            {group.title && (
              <p className="px-2 pb-1 text-[0.6875rem] font-medium text-slate-500">{group.title}</p>
            )}
            <div className="space-y-px">
              {group.items.map(({ href, label, icon }) => {
                const active = pathname === href;
                return (
                  <Link
                    key={href}
                    href={href}
                    onClick={() => setMobileOpen(false)}
                    className={`flex items-center gap-2.5 px-2 h-7 rounded-md text-[0.8125rem] transition-colors duration-100 ${
                      active
                        ? 'bg-white/[0.07] text-slate-100'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]'
                    }`}
                    aria-current={active ? 'page' : undefined}
                  >
                    <span className={active ? 'text-slate-200' : 'text-slate-500'}><NavIcon d={icon} /></span>
                    <span className="truncate">{label}</span>
                    {href === '/notices' && unread > 0 && (
                      <span className="ml-auto text-[0.6875rem] min-w-5 text-center px-1.5 rounded-full bg-blue-600 text-white leading-[18px]" aria-label={`${unread} unread`}>
                        {unread}
                      </span>
                    )}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Session */}
      <div className="mt-auto pt-3 shrink-0 space-y-2">
        <div className="px-2"><ThemeToggle /></div>
        {loggedIn ? (
          <div className="flex items-center justify-between gap-2 px-2 py-1.5 rounded-md hover:bg-white/[0.04] transition-colors">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-6 h-6 rounded-full bg-slate-700 flex items-center justify-center text-[0.625rem] font-semibold text-slate-200 shrink-0">
                {initials}
              </div>
              <div className="min-w-0">
                <p className="text-[0.8125rem] text-slate-200 truncate leading-tight">{me?.full_name || me?.email || 'Signed in'}</p>
                <p className="text-[0.6875rem] text-slate-500 truncate">{me ? ROLE_LABEL[me.role] ?? me.role : '…'}</p>
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="text-[0.75rem] text-slate-500 hover:text-slate-200 transition-colors px-1 py-0.5 cursor-pointer whitespace-nowrap shrink-0"
              aria-label="Log out"
            >
              Log out
            </button>
          </div>
        ) : (
          <Link
            href="/login"
            onClick={() => setMobileOpen(false)}
            className="block text-[0.8125rem] text-center h-8 leading-8 rounded-md bg-blue-600 text-white hover:bg-blue-500 transition-colors font-medium"
          >
            Sign in
          </Link>
        )}
      </div>
    </>
  );

  return (
    <>
      {/* Mobile Top Header Bar (Shown only on screens < lg) */}
      <div className="lg:hidden bg-slate-950 border-b border-slate-800 px-4 py-2.5 flex items-center justify-between z-20 shrink-0">
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
            <InstitutionMark institution={institution} size="sm" />
            <span className="font-medium text-[0.8125rem] text-slate-100 truncate">
              {institution.name}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-1">
        <ThemeToggle compact />
        {loggedIn && (
          <button
            onClick={handleLogout}
            className="text-[0.75rem] text-slate-500 hover:text-slate-200 transition-colors px-2 py-1"
          >
            Log out
          </button>
        )}
        </div>
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
          <aside className="relative w-72 max-w-[85vw] h-full bg-slate-950 border-r border-slate-800 px-3 py-4 flex flex-col z-50 shadow-2xl">
            <div className="flex items-center justify-between mb-4 pb-2 border-b border-slate-800 lg:hidden">
              <span className="text-[0.75rem] font-medium text-slate-500">Menu</span>
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
      <aside className="hidden lg:flex w-60 h-full bg-slate-950 flex-col pl-3 pr-1 py-4 shrink-0 z-10">
        {navContent}
      </aside>
    </>
  );
}
