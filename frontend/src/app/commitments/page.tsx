'use client';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { apiFetch } from '@/lib/api';
import { formatDate, formatDateTime } from '@/lib/format';
import { isCoordinatorRole, useMe } from '@/lib/roles';

type Status = 'open' | 'in_progress' | 'blocked' | 'review' | 'done' | 'dropped';

interface Task {
  id: string;
  description: string;
  assignee: string | null;
  status: Status;
  progress: number;
  remaining: string | null;
  blocked_reason: string | null;
  due_date: string | null;
  source_meeting_id: string | null;
  source_meeting: string | null;
  assigned_by: string | null;
  department: string;
  confidence: number;
  last_followup_at: string | null;
  marked_done_at: string | null;
  confirmed_at: string | null;
  confirmed_by: string | null;
  created_at: string;
  can_update?: boolean;
  can_manage?: boolean;
}

interface Summary {
  open: number;
  overdue: number;
  due_this_week: number;
  blocked: number;
  awaiting_confirmation: number;
  completed: number;
  average_progress: number | null;
}

interface TimelineEntry {
  at: string;
  source: string;
  actor: string | null;
  text: string;
  summary: string | null;
  status: Status | null;
  progress: number | null;
}

interface Detail extends Task {
  source_line: { text: string; speaker: string | null } | null;
  timeline: TimelineEntry[];
}

interface TeamGroup {
  owner: string;
  summary: Summary;
  items: Task[];
}

const STATUS: Record<Status, { label: string; style: string }> = {
  open: { label: 'Not started', style: 'border-slate-600 text-slate-300' },
  in_progress: { label: 'In progress', style: 'border-blue-500/40 text-blue-300' },
  blocked: { label: 'Blocked', style: 'border-rose-500/40 text-rose-300' },
  review: { label: 'Done · awaiting confirmation', style: 'border-amber-500/40 text-amber-300' },
  done: { label: 'Completed', style: 'border-emerald-500/40 text-emerald-300' },
  dropped: { label: 'Dropped', style: 'border-slate-700 text-slate-500' },
};
const SOURCE_LABEL: Record<string, string> = {
  checkin: 'End-of-day check-in', followup: 'Follow-up reply', owner: 'Owner', coordinator: 'Coordinator', note: 'Note',
};
const OPEN: Status[] = ['open', 'in_progress', 'blocked'];

function daysLeft(t: Task): number | null {
  if (!t.due_date) return null;
  const ms = new Date(t.due_date).getTime() - Date.now();
  return Math.ceil(ms / 86_400_000);
}

function dueText(t: Task): { text: string; overdue: boolean } {
  const d = daysLeft(t);
  if (d === null) return { text: 'No due date', overdue: false };
  if (!OPEN.includes(t.status)) return { text: `Due ${formatDate(t.due_date)}`, overdue: false };
  if (d < 0) return { text: `${-d} day${d === -1 ? '' : 's'} overdue`, overdue: true };
  if (d === 0) return { text: 'Due today', overdue: true };
  return { text: `${d} day${d === 1 ? '' : 's'} left · ${formatDate(t.due_date)}`, overdue: false };
}

function Bar({ value }: { value: number }) {
  return (
    <div className="h-1.5 rounded bg-slate-800 overflow-hidden" aria-label={`${value}% done`}>
      <div className={`h-full ${value >= 100 ? 'bg-emerald-500' : 'bg-blue-500'}`} style={{ width: `${value}%` }} />
    </div>
  );
}

function TaskCard({ t, onOpen, showOwner }: { t: Task; onOpen: (id: string) => void; showOwner?: boolean }) {
  const due = dueText(t);
  return (
    <li>
      <button type="button" onClick={() => onOpen(t.id)}
        className={`w-full text-left glass-panel p-3.5 border cursor-pointer hover:border-blue-500/40 ${
          due.overdue ? 'border-rose-500/40' : 'border-transparent'}`}>
        <div className="flex items-start justify-between gap-3">
          <p className="text-sm font-medium text-slate-100">{t.description}</p>
          <span className={`text-[10px] px-2 py-0.5 rounded border whitespace-nowrap ${STATUS[t.status].style}`}>
            {STATUS[t.status].label}
          </span>
        </div>
        <div className="mt-2 flex items-center gap-3">
          <div className="flex-1"><Bar value={t.progress} /></div>
          <span className="text-[11px] text-slate-300 w-9 text-right">{t.progress}%</span>
        </div>
        {(t.remaining || t.blocked_reason) && (
          <p className={`mt-1 text-[11px] ${t.blocked_reason ? 'text-rose-300' : 'text-slate-400'}`}>
            {t.blocked_reason ? `Blocked: ${t.blocked_reason}` : `Left: ${t.remaining}`}
          </p>
        )}
        <p className="mt-1.5 text-[11px] text-slate-500">
          <span className={due.overdue ? 'text-rose-300' : ''}>{due.text}</span>
          {showOwner && t.assignee ? ` · ${t.assignee}` : ''}
          {t.assigned_by ? ` · assigned by ${t.assigned_by}` : ''}
          {t.source_meeting ? ` · from “${t.source_meeting}”` : ''}
        </p>
      </button>
    </li>
  );
}

function Section({ title, items, onOpen, showOwner, empty }: {
  title: string; items: Task[]; onOpen: (id: string) => void; showOwner?: boolean; empty?: string;
}) {
  if (!items.length && !empty) return null;
  return (
    <section className="space-y-2">
      <h2 className="text-[11px] uppercase tracking-wider font-semibold text-slate-400">
        {title} <span className="text-slate-600">({items.length})</span>
      </h2>
      {items.length ? (
        <ul className="space-y-2">{items.map((t) => <TaskCard key={t.id} t={t} onOpen={onOpen} showOwner={showOwner} />)}</ul>
      ) : (
        <p className="text-xs text-slate-500">{empty}</p>
      )}
    </section>
  );
}

function DetailPanel({ id, onClose, onChanged }: { id: string; onClose: () => void; onChanged: () => void }) {
  const [d, setD] = useState<Detail | null>(null);
  const [progress, setProgress] = useState(0);
  const [remaining, setRemaining] = useState('');
  const [note, setNote] = useState('');
  const [blocker, setBlocker] = useState('');
  const [comment, setComment] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(() => {
    apiFetch(`/api/v1/commitments/${id}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((x: Detail) => {
        setD(x);
        setProgress(x.progress);
        setRemaining(x.remaining ?? '');
      })
      .catch((e: Error) => setError(e.message));
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const act = async (path: string, body?: object) => {
    const res = await apiFetch(`/api/v1/commitments/${id}${path}`, { method: 'POST', body: JSON.stringify(body ?? {}) });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      setError(data.detail ?? `HTTP ${res.status}`);
      return;
    }
    setError('');
    setNote('');
    setBlocker('');
    setComment('');
    load();
    onChanged();
  };

  if (!d) {
    return (
      <aside className="glass-panel p-4 text-xs text-slate-400">{error || 'Loading task…'}</aside>
    );
  }
  const open = OPEN.includes(d.status);
  return (
    <aside className="glass-panel p-4 space-y-4 text-xs" aria-label="Task detail">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-slate-100">{d.description}</p>
          <p className="text-slate-400 mt-0.5">
            {d.assignee ?? 'Unassigned'} · {STATUS[d.status].label} · {d.progress}% · {dueText(d).text}
          </p>
        </div>
        <button type="button" onClick={onClose} className="text-slate-400 hover:text-slate-200 cursor-pointer" aria-label="Close">✕</button>
      </div>

      <dl className="grid grid-cols-[7rem_1fr] gap-x-3 gap-y-1 text-slate-300">
        <dt className="text-slate-500">Assigned by</dt><dd>{d.assigned_by ?? 'Recorded from a meeting'}</dd>
        <dt className="text-slate-500">Source</dt>
        <dd>{d.source_meeting ? <a href="/meetings" className="text-blue-300 hover:underline">{d.source_meeting}</a> : 'Assigned directly'}</dd>
        <dt className="text-slate-500">Department</dt><dd>{d.department === 'all' ? 'Institution-wide' : d.department}</dd>
        <dt className="text-slate-500">Created</dt><dd>{formatDateTime(d.created_at)}</dd>
        {d.confirmed_by && (<><dt className="text-slate-500">Confirmed</dt><dd>{d.confirmed_by} · {formatDateTime(d.confirmed_at)}</dd></>)}
      </dl>

      {d.source_line && (
        <blockquote className="border-l-2 border-slate-600 pl-3 text-slate-300">
          <p className="text-[10px] uppercase tracking-wider text-slate-500 mb-0.5">Most likely source line</p>
          {d.source_line.speaker ? <span className="text-slate-400">{d.source_line.speaker}: </span> : null}
          {d.source_line.text}
        </blockquote>
      )}

      {error && <p role="alert" className="text-rose-400">{error}</p>}

      {d.can_update && open && (
        <section className="space-y-2 border-t border-slate-800 pt-3" aria-label="Update progress">
          <p className="text-[11px] uppercase tracking-wider font-semibold text-slate-400">Update your progress</p>
          <label className="flex items-center gap-2">
            <input type="range" min={0} max={100} step={5} value={progress} onChange={(e) => setProgress(Number(e.target.value))}
              className="flex-1" aria-label="Progress percent" />
            <span className="w-10 text-right text-slate-200">{progress}%</span>
          </label>
          <input value={remaining} onChange={(e) => setRemaining(e.target.value)} placeholder="What is left? (e.g. 2 sets)"
            className="w-full bg-slate-900 border border-slate-700/80 rounded px-2 py-1.5 text-slate-100" aria-label="What is left" />
          <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} placeholder="Note or proof (link, what you did)"
            className="w-full bg-slate-900 border border-slate-700/80 rounded px-2 py-1.5 text-slate-100" aria-label="Note" />
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={() => act('/progress', { progress, remaining, note: note || undefined })}
              className="px-3 py-1 rounded bg-blue-600 hover:bg-blue-500 text-white cursor-pointer">Save progress</button>
            <button type="button" onClick={() => act('/done')}
              className="px-3 py-1 rounded border border-emerald-500/50 text-emerald-300 hover:bg-emerald-500/10 cursor-pointer">Mark done</button>
          </div>
          <div className="flex gap-2">
            <input value={blocker} onChange={(e) => setBlocker(e.target.value)} placeholder="Blocked by… (tells the coordinator)"
              className="flex-1 bg-slate-900 border border-slate-700/80 rounded px-2 py-1.5 text-slate-100" aria-label="Blocked by" />
            <button type="button" disabled={!blocker.trim()} onClick={() => act('/progress', { status: 'blocked', blocked_reason: blocker })}
              className="px-3 py-1 rounded border border-rose-500/50 text-rose-300 disabled:opacity-40 cursor-pointer">Mark blocked</button>
          </div>
        </section>
      )}

      {d.can_manage && d.status === 'review' && (
        <section className="space-y-2 border-t border-slate-800 pt-3" aria-label="Confirm">
          <p className="text-[11px] uppercase tracking-wider font-semibold text-amber-300">The owner marked this done</p>
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={() => act('/confirm')}
              className="px-3 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-white cursor-pointer">Confirm completed</button>
          </div>
          <div className="flex gap-2">
            <input value={comment} onChange={(e) => setComment(e.target.value)} placeholder="What still needs doing?"
              className="flex-1 bg-slate-900 border border-slate-700/80 rounded px-2 py-1.5 text-slate-100" aria-label="Send back comment" />
            <button type="button" disabled={!comment.trim()} onClick={() => act('/send-back', { comment })}
              className="px-3 py-1 rounded border border-amber-500/50 text-amber-300 disabled:opacity-40 cursor-pointer">Send back</button>
          </div>
        </section>
      )}

      <section className="space-y-2 border-t border-slate-800 pt-3" aria-label="Timeline">
        <p className="text-[11px] uppercase tracking-wider font-semibold text-slate-400">Timeline</p>
        {d.timeline.length === 0 && <p className="text-slate-500">No updates yet.</p>}
        <ol className="space-y-2">
          {[...d.timeline].reverse().map((e, i) => (
            <li key={i} className="border-l-2 border-slate-700 pl-3">
              <p className="text-slate-200">{e.summary ?? e.text}</p>
              {e.summary && e.text !== e.summary && <p className="text-slate-500 italic">“{e.text}”</p>}
              <p className="text-[10px] text-slate-500">
                {formatDateTime(e.at)} · {SOURCE_LABEL[e.source] ?? e.source}{e.actor ? ` (${e.actor})` : ''}
                {e.progress !== null ? ` · ${e.progress}%` : ''}
                {e.status ? ` · ${STATUS[e.status]?.label ?? e.status}` : ''}
              </p>
            </li>
          ))}
        </ol>
      </section>
    </aside>
  );
}

function NewTaskForm({ onCreated }: { onCreated: () => void }) {
  const [people, setPeople] = useState<{ user_id: string; name: string; department: string | null }[]>([]);
  const [form, setForm] = useState({ description: '', assignee_user_id: '', due: '', notes: '' });
  const [msg, setMsg] = useState('');

  useEffect(() => {
    apiFetch('/api/v1/commitments/assignable')
      .then((r) => (r.ok ? r.json() : []))
      .then(setPeople)
      .catch(() => {});
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const res = await apiFetch('/api/v1/commitments', {
      method: 'POST',
      body: JSON.stringify({
        description: form.description, assignee_user_id: form.assignee_user_id, notes: form.notes || undefined,
        due_date: form.due ? new Date(`${form.due}T17:00:00`).toISOString() : undefined,
      }),
    });
    const d = await res.json().catch(() => ({}));
    if (!res.ok) return setMsg(d.detail ?? `HTTP ${res.status}`);
    setMsg(`Assigned to ${d.assignee}. They have been notified.`);
    setForm({ description: '', assignee_user_id: '', due: '', notes: '' });
    onCreated();
  };

  const field = 'bg-slate-900 border border-slate-700/80 rounded px-2 py-1.5 text-xs text-slate-100';
  return (
    <form onSubmit={submit} className="glass-panel p-4 space-y-2" aria-label="Assign a task">
      <p className="text-sm font-semibold text-slate-100">Assign a task</p>
      <input required value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
        placeholder="What needs to be done" className={`w-full ${field}`} aria-label="Task" />
      <div className="flex flex-wrap gap-2">
        <select required value={form.assignee_user_id} onChange={(e) => setForm({ ...form, assignee_user_id: e.target.value })}
          className={field} aria-label="Owner">
          <option value="">Owner…</option>
          {people.map((p) => <option key={p.user_id} value={p.user_id}>{p.name}{p.department ? ` (${p.department})` : ''}</option>)}
        </select>
        <input type="date" value={form.due} onChange={(e) => setForm({ ...form, due: e.target.value })} className={field} aria-label="Due date" />
        <input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="Notes (optional)"
          className={`flex-1 ${field}`} aria-label="Notes" />
        <button type="submit" className="px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold cursor-pointer">Assign</button>
      </div>
      {msg && <p className="text-[11px] text-slate-300">{msg}</p>}
    </form>
  );
}

export default function MyWorkPage() {
  const me = useMe();
  const coordinator = isCoordinatorRole(me?.role);
  const [tab, setTab] = useState<'mine' | 'waiting' | 'team' | 'all'>('mine');
  const [mine, setMine] = useState<{ summary: Summary; items: Task[]; awaiting_my_confirmation?: Task[] } | null>(null);
  const [team, setTeam] = useState<TeamGroup[]>([]);
  const [all, setAll] = useState<Task[]>([]);
  const [openId, setOpenId] = useState<string | null>(null);
  const [error, setError] = useState('');

  const loadMine = useCallback(() => {
    apiFetch('/api/v1/commitments/my-work')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setMine)
      .catch((e: Error) => setError(`Could not load your tasks (${e.message}).`));
  }, []);
  const loadOther = useCallback(() => {
    if (tab === 'team') apiFetch('/api/v1/commitments/team').then((r) => (r.ok ? r.json() : [])).then(setTeam).catch(() => {});
    if (tab === 'all') apiFetch('/api/v1/commitments').then((r) => (r.ok ? r.json() : [])).then(setAll).catch(() => {});
  }, [tab]);

  useEffect(() => {
    loadMine();
  }, [loadMine]);
  useEffect(() => {
    loadOther();
  }, [loadOther]);

  const refresh = () => {
    loadMine();
    loadOther();
  };

  const groups = useMemo(() => {
    const items = mine?.items ?? [];
    const active = items.filter((t) => OPEN.includes(t.status));
    const d = (t: Task) => daysLeft(t);
    return {
      overdue: active.filter((t) => (d(t) ?? 1) <= 0),
      week: active.filter((t) => { const x = d(t); return x !== null && x > 0 && x <= 7; }),
      later: active.filter((t) => { const x = d(t); return x === null || x > 7; }),
      review: items.filter((t) => t.status === 'review'),
      closed: items.filter((t) => t.status === 'done' || t.status === 'dropped'),
    };
  }, [mine]);

  const s = mine?.summary;
  const tabs: { key: typeof tab; label: string }[] = [
    { key: 'mine', label: 'My work' },
    ...(coordinator ? [
      { key: 'waiting' as const, label: `Waiting for me${mine?.awaiting_my_confirmation?.length ? ` (${mine.awaiting_my_confirmation.length})` : ''}` },
      { key: 'team' as const, label: 'Team' },
    ] : []),
    { key: 'all', label: 'All tasks' },
  ];

  return (
    <main className="p-4 sm:p-6 md:p-10 max-w-7xl mx-auto space-y-5">
      <div>
        <h1 className="text-2xl md:text-3xl font-bold text-slate-100 tracking-tight">My Work</h1>
        <p className="text-slate-400 text-xs sm:text-sm mt-1">
          Tasks from committee meetings and coordinators. Update progress here or just describe your day on the Faculty
          Desk; marking a task done sends it to a coordinator to confirm.
        </p>
      </div>

      {s && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
          {[
            ['Open', s.open, ''], ['Overdue', s.overdue, s.overdue ? 'text-rose-300' : ''],
            ['Due this week', s.due_this_week, ''], ['Awaiting confirmation', s.awaiting_confirmation, ''],
            ['Average progress', s.average_progress === null ? '—' : `${s.average_progress}%`, ''],
          ].map(([label, value, cls]) => (
            <div key={String(label)} className="glass-panel p-3">
              <p className="text-[10px] uppercase tracking-wider text-slate-400">{label}</p>
              <p className={`text-xl font-bold text-slate-100 ${cls}`}>{value}</p>
            </div>
          ))}
        </div>
      )}

      <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Task views">
        {tabs.map((t) => (
          <button key={t.key} role="tab" aria-selected={tab === t.key} onClick={() => { setTab(t.key); setOpenId(null); }}
            className={`px-3 py-1.5 rounded text-xs font-medium border cursor-pointer ${
              tab === t.key ? 'bg-blue-600/15 text-blue-300 border-blue-500/40' : 'text-slate-400 border-slate-800 hover:text-slate-200'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {error && <p role="alert" className="text-rose-400 text-xs">{error}</p>}

      <div className={`grid gap-4 ${openId ? 'lg:grid-cols-[minmax(0,1fr)_26rem]' : ''}`}>
        <div className="space-y-5">
          {tab === 'mine' && mine && (
            <>
              {mine.items.length === 0 && <p className="text-xs text-slate-500">No tasks assigned to you.</p>}
              <Section title="Overdue or due today" items={groups.overdue} onOpen={setOpenId} />
              <Section title="Due this week" items={groups.week} onOpen={setOpenId} />
              <Section title="Later / no due date" items={groups.later} onOpen={setOpenId} />
              <Section title="Done, awaiting confirmation" items={groups.review} onOpen={setOpenId} />
              <Section title="Completed" items={groups.closed} onOpen={setOpenId} />
            </>
          )}
          {tab === 'waiting' && (
            <Section title="Marked done by their owners" items={mine?.awaiting_my_confirmation ?? []} onOpen={setOpenId}
              showOwner empty="Nothing is waiting for your confirmation." />
          )}
          {tab === 'team' && (
            <>
              <NewTaskForm onCreated={refresh} />
              {team.map((g) => (
                <section key={g.owner} className="space-y-2">
                  <div className="flex flex-wrap items-baseline gap-3">
                    <h2 className="text-sm font-semibold text-slate-100">{g.owner}</h2>
                    <span className="text-[11px] text-slate-400">
                      {g.summary.open} open · <span className={g.summary.overdue ? 'text-rose-300' : ''}>{g.summary.overdue} overdue</span>
                      {' '}· {g.summary.blocked} blocked · {g.summary.awaiting_confirmation} to confirm
                      {g.summary.average_progress !== null ? ` · ${g.summary.average_progress}% average` : ''}
                    </span>
                  </div>
                  <ul className="space-y-2">{g.items.filter((t) => t.status !== 'done' && t.status !== 'dropped').map((t) => (
                    <TaskCard key={t.id} t={t} onOpen={setOpenId} />))}</ul>
                </section>
              ))}
            </>
          )}
          {tab === 'all' && (
            <Section title="All tasks in your departments" items={all} onOpen={setOpenId} showOwner empty="No tasks." />
          )}
        </div>
        {openId && <DetailPanel key={openId} id={openId} onClose={() => setOpenId(null)} onChanged={refresh} />}
      </div>
    </main>
  );
}
