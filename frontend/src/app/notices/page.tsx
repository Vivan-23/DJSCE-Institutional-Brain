'use client';
import React, { useCallback, useEffect, useState } from 'react';
import { apiFetch } from '@/lib/api';
import { formatDateTime } from '@/lib/format';
import { isCoordinatorRole, isStaffRole, ROLE_LABEL, type Role, useMe } from '@/lib/roles';
import { useInstitution } from '@/lib/useInstitution';

interface AudienceSpec {
  roles: string[];
  departments: string[];
  years: number[];
  semesters: number[];
  divisions: string[];
}

interface NoticeItem {
  id: string;
  title: string;
  body: string;
  priority: 'normal' | 'urgent';
  audience: AudienceSpec;
  created_at: string;
  expires_at: string | null;
  sender: string | null;
  read?: boolean;
  recipients?: number;
}

const YEARS = [
  { n: 1, label: 'FE (1st)' },
  { n: 2, label: 'SE (2nd)' },
  { n: 3, label: 'TE (3rd)' },
  { n: 4, label: 'BE (4th)' },
];

function describe(a: AudienceSpec): string {
  const parts = [
    a.roles.map((r) => ROLE_LABEL[r as Role] ?? r).join(' / '),
    a.departments.length ? a.departments.join(', ') : 'all departments',
  ];
  if (a.years.length) parts.push(`year ${a.years.join(', ')}`);
  if (a.semesters.length) parts.push(`semester ${a.semesters.join(', ')}`);
  if (a.divisions.length) parts.push(`division ${a.divisions.join(', ')}`);
  return parts.join(' · ');
}

const chip = (on: boolean) =>
  `px-2 py-0.5 rounded border text-[12px] cursor-pointer ${
    on ? 'bg-blue-600/20 border-blue-500/50 text-blue-200' : 'border-slate-700 text-slate-400 hover:text-slate-200'
  }`;

function toggle<T>(list: T[], v: T): T[] {
  return list.includes(v) ? list.filter((x) => x !== v) : [...list, v];
}

export default function NoticesPage() {
  const me = useMe();
  const staff = isStaffRole(me?.role);
  const anyDept = isCoordinatorRole(me?.role);
  const { departments } = useInstitution();
  const [tab, setTab] = useState<'inbox' | 'compose' | 'sent'>('inbox');
  const [inbox, setInbox] = useState<NoticeItem[]>([]);
  const [sent, setSent] = useState<NoticeItem[]>([]);
  const [openId, setOpenId] = useState<string | null>(null);
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [priority, setPriority] = useState<'normal' | 'urgent'>('normal');
  const [expires, setExpires] = useState('');
  const [aud, setAud] = useState<AudienceSpec>({ roles: ['student'], departments: [], years: [], semesters: [], divisions: [] });
  const [divisionText, setDivisionText] = useState('');
  const [reach, setReach] = useState<number | null>(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const loadInbox = useCallback(() => {
    apiFetch('/api/v1/notices/mine')
      .then((r) => (r.ok ? r.json() : []))
      .then(setInbox)
      .catch(() => {});
  }, []);
  const loadSent = useCallback(() => {
    apiFetch('/api/v1/notices/sent')
      .then((r) => (r.ok ? r.json() : []))
      .then(setSent)
      .catch(() => {});
  }, []);

  useEffect(() => {
    loadInbox();
  }, [loadInbox]);

  useEffect(() => {
    if (tab === 'sent') loadSent();
  }, [tab, loadSent]);

  const audience = useCallback(
    (): AudienceSpec => ({
      ...aud,
      divisions: divisionText.split(/[\s,]+/).filter(Boolean),
    }),
    [aud, divisionText],
  );

  // Live "this will reach N people" while composing.
  useEffect(() => {
    if (tab !== 'compose' || !staff) return;
    const t = setTimeout(() => {
      apiFetch('/api/v1/notices/preview', { method: 'POST', body: JSON.stringify(audience()) })
        .then(async (r) => {
          const d = await r.json();
          if (!r.ok) throw new Error(d.detail ?? `HTTP ${r.status}`);
          setReach(d.count);
          setError('');
        })
        .catch((e: Error) => {
          setReach(null);
          setError(e.message);
        });
    }, 300);
    return () => clearTimeout(t);
  }, [tab, staff, audience]);

  const open = (n: NoticeItem) => {
    setOpenId(openId === n.id ? null : n.id);
    if (!n.read) {
      apiFetch(`/api/v1/notices/${n.id}/read`, { method: 'POST' }).then(() => {
        setInbox((prev) => prev.map((x) => (x.id === n.id ? { ...x, read: true } : x)));
        window.dispatchEvent(new Event('notices-changed'));
      });
    }
  };

  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    const res = await apiFetch('/api/v1/notices', {
      method: 'POST',
      body: JSON.stringify({
        title, body, priority, audience: audience(),
        expires_at: expires ? new Date(`${expires}T23:59:00`).toISOString() : null,
      }),
    });
    const d = await res.json();
    if (!res.ok) {
      setError(d.detail ?? `Send failed (HTTP ${res.status})`);
      return;
    }
    setMessage(`Sent to ${d.recipients} ${d.recipients === 1 ? 'person' : 'people'}.`);
    setTitle('');
    setBody('');
    setExpires('');
    setPriority('normal');
    loadInbox();
  };

  const tabs = staff ? (['inbox', 'compose', 'sent'] as const) : (['inbox'] as const);

  return (
    <main className="p-4 sm:p-6 md:p-10 max-w-5xl mx-auto space-y-5">
      <div>
        <h1 className="text-xl md:text-2xl font-semibold text-slate-100 tracking-[-0.02em]">Notices</h1>
        <p className="text-slate-400 text-xs sm:text-sm mt-1">
          {staff
            ? 'Read notices addressed to you, or send one to students filtered by department, year, semester and division.'
            : 'Notices from your department and the institution, newest and most urgent first.'}
        </p>
      </div>

      {tabs.length > 1 && (
        <div className="flex gap-1.5" role="tablist" aria-label="Notices">
          {tabs.map((t) => (
            <button key={t} role="tab" aria-selected={tab === t} onClick={() => { setTab(t); setMessage(''); }}
              className={`px-3 py-1.5 rounded text-xs font-medium border cursor-pointer ${
                tab === t ? 'bg-blue-600/15 text-blue-300 border-blue-500/40' : 'text-slate-400 border-slate-800 hover:text-slate-200'
              }`}>
              {t === 'inbox' ? 'Inbox' : t === 'compose' ? 'Send a notice' : 'Sent'}
            </button>
          ))}
        </div>
      )}

      {message && <p role="status" className="text-emerald-300 text-xs">{message}</p>}

      {tab === 'inbox' && (
        <ul className="space-y-2" aria-label="Inbox">
          {inbox.length === 0 && <li className="text-xs text-slate-500">No notices for you right now.</li>}
          {inbox.map((n) => (
            <li key={n.id}>
              <button type="button" onClick={() => open(n)} aria-expanded={openId === n.id}
                className={`w-full text-left glass-panel p-3 border cursor-pointer ${
                  n.priority === 'urgent' ? 'border-rose-500/40' : n.read ? 'border-transparent' : 'border-blue-500/30'
                }`}>
                <div className="flex items-start justify-between gap-2">
                  <p className={`text-sm ${n.read ? 'text-slate-300' : 'text-slate-100 font-semibold'}`}>
                    {!n.read && <span className="inline-block w-2 h-2 rounded-full bg-blue-400 mr-2" aria-label="Unread" />}
                    {n.title}
                  </p>
                  {n.priority === 'urgent' && (
                    <span className="text-[11px] px-2 py-0.5 rounded border border-rose-500/40 text-rose-300">Urgent</span>
                  )}
                </div>
                <p className="text-[12px] text-slate-500 mt-0.5">
                  {n.sender ?? 'Unknown'} · {formatDateTime(n.created_at)}
                  {n.expires_at ? ` · until ${formatDateTime(n.expires_at)}` : ''}
                </p>
                {openId === n.id && <p className="mt-2 text-xs sm:text-sm text-slate-200 whitespace-pre-wrap">{n.body}</p>}
              </button>
            </li>
          ))}
        </ul>
      )}

      {tab === 'compose' && staff && (
        <form onSubmit={send} className="glass-panel p-4 space-y-4" aria-label="Send a notice">
          <input required value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title" maxLength={200}
            aria-label="Title"
            className="w-full bg-slate-900 border border-slate-700/80 rounded px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-blue-500" />
          <textarea required value={body} onChange={(e) => setBody(e.target.value)} rows={6} placeholder="Message"
            aria-label="Message"
            className="w-full bg-slate-900 border border-slate-700/80 rounded px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-blue-500" />

          <fieldset className="space-y-2">
            <legend className="text-[12px] text-slate-400 font-semibold mb-1">Who receives it</legend>
            <div className="flex flex-wrap gap-1.5 items-center">
              <span className="text-[12px] text-slate-400 w-24">Recipients</span>
              {(['student', 'employee'] as Role[]).map((r) => (
                <button type="button" key={r} className={chip(aud.roles.includes(r))}
                  onClick={() => setAud({ ...aud, roles: toggle(aud.roles, r).length ? toggle(aud.roles, r) : aud.roles })}>
                  {r === 'student' ? 'Students' : 'Faculty'}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap gap-1.5 items-center">
              <span className="text-[12px] text-slate-400 w-24">Department</span>
              {anyDept ? (
                departments.map((d) => (
                  <button type="button" key={d.code} title={d.name} className={chip(aud.departments.includes(d.code))}
                    onClick={() => setAud({ ...aud, departments: toggle(aud.departments, d.code) })}>
                    {d.code}
                  </button>
                ))
              ) : (
                <span className="text-[12px] text-slate-300">{me?.department ?? '—'} (faculty send to their own department)</span>
              )}
              {anyDept && aud.departments.length === 0 && <span className="text-[12px] text-slate-500">none selected = all</span>}
            </div>
            <div className="flex flex-wrap gap-1.5 items-center">
              <span className="text-[12px] text-slate-400 w-24">Year</span>
              {YEARS.map((y) => (
                <button type="button" key={y.n} className={chip(aud.years.includes(y.n))}
                  onClick={() => setAud({ ...aud, years: toggle(aud.years, y.n) })}>
                  {y.label}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap gap-1.5 items-center">
              <span className="text-[12px] text-slate-400 w-24">Semester</span>
              {[1, 2, 3, 4, 5, 6, 7, 8].map((s) => (
                <button type="button" key={s} className={chip(aud.semesters.includes(s))}
                  onClick={() => setAud({ ...aud, semesters: toggle(aud.semesters, s) })}>
                  {s}
                </button>
              ))}
            </div>
            <label className="flex flex-wrap gap-1.5 items-center text-[12px] text-slate-400">
              <span className="w-24">Division</span>
              <input value={divisionText} onChange={(e) => setDivisionText(e.target.value)} placeholder="e.g. A, B (blank = all)"
                className="bg-slate-900 border border-slate-700/80 rounded px-2 py-1 text-xs text-slate-100 focus:outline-none focus:border-blue-500" />
            </label>
          </fieldset>

          <div className="flex flex-wrap gap-3 items-center text-xs text-slate-300">
            <label className="flex items-center gap-1.5">
              <input type="checkbox" checked={priority === 'urgent'} onChange={(e) => setPriority(e.target.checked ? 'urgent' : 'normal')} />
              Urgent
            </label>
            <label className="flex items-center gap-1.5">
              Show until
              <input type="date" value={expires} onChange={(e) => setExpires(e.target.value)}
                className="bg-slate-900 border border-slate-700/80 rounded px-2 py-1 text-xs text-slate-100" />
            </label>
            <span className={`ml-auto ${reach === 0 ? 'text-rose-300' : 'text-slate-300'}`}>
              {reach === null ? '' : `This will reach ${reach} ${reach === 1 ? 'person' : 'people'}`}
            </span>
          </div>
          {error && <p role="alert" className="text-rose-400 text-xs">{error}</p>}
          <button type="submit" disabled={!reach}
            className="px-4 py-2 rounded bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold cursor-pointer disabled:opacity-40">
            Send notice
          </button>
        </form>
      )}

      {tab === 'sent' && staff && (
        <ul className="space-y-2" aria-label="Sent notices">
          {sent.length === 0 && <li className="text-xs text-slate-500">Nothing sent yet.</li>}
          {sent.map((n) => (
            <li key={n.id} className="glass-panel p-3">
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm text-slate-100 font-medium">{n.title}</p>
                <span className="text-[12px] text-slate-300 whitespace-nowrap">
                  {n.read} of {n.recipients} read
                </span>
              </div>
              <p className="text-[12px] text-slate-500 mt-0.5">
                {describe(n.audience)} · {n.sender} · {formatDateTime(n.created_at)}
                {n.priority === 'urgent' ? ' · urgent' : ''}
              </p>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
