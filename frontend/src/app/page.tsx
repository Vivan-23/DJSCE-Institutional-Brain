'use client';
import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import InsightCard, { type Insight } from '@/components/dashboard/InsightCard';
import { Badge, type Tone } from '@/components/ui/Badge';
import { apiFetch } from '@/lib/api';
import { formatDateTime } from '@/lib/format';
import { isCoordinatorRole, isStaffRole, useMe } from '@/lib/roles';
import {
  CAL_KIND_LABEL, dayHeading, fetchSchedule, KIND_LABEL, LECTURE_STATUS, timeRange,
  type CalendarItem, type ScheduleResponse,
} from '@/lib/schedule';

type Status = 'open' | 'in_progress' | 'blocked' | 'review' | 'done' | 'dropped';

interface Task {
  id: string;
  description: string;
  assignee: string | null;
  status: Status;
  progress: number;
  due_date: string | null;
  assigned_by: string | null;
  source_meeting: string | null;
  created_at: string;
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

interface MyWork {
  summary: Summary;
  items: Task[];
  awaiting_my_confirmation?: Task[];
}

interface TeamGroup {
  owner: string;
  summary: Summary;
  items: Task[];
}

interface Notice {
  id: string;
  title: string;
  body: string;
  sender: string | null;
  created_at: string;
  read: boolean;
}

const OPEN: Status[] = ['open', 'in_progress', 'blocked'];
const NEW_TASK_DAYS = 3;

function daysLeft(due: string | null): number | null {
  if (!due) return null;
  return Math.ceil((new Date(due).getTime() - Date.now()) / 86_400_000);
}

/** Why a task needs attention, most urgent reason first; null if it doesn't. */
function attention(t: Task): { label: string; tone: Tone; rank: number } | null {
  const d = daysLeft(t.due_date);
  if (OPEN.includes(t.status) && d !== null && d < 0) return { label: `${-d} day${d === -1 ? '' : 's'} overdue`, tone: 'danger', rank: 0 };
  if (OPEN.includes(t.status) && d === 0) return { label: 'Due today', tone: 'warning', rank: 1 };
  if (t.status === 'blocked') return { label: 'Blocked', tone: 'danger', rank: 2 };
  if (t.status === 'review') return { label: 'Awaiting confirmation', tone: 'warning', rank: 3 };
  const ageDays = (Date.now() - new Date(t.created_at).getTime()) / 86_400_000;
  if (t.status === 'open' && t.progress === 0 && ageDays <= NEW_TASK_DAYS) return { label: 'New', tone: 'accent', rank: 4 };
  return null;
}

const greeting = () => {
  const h = new Date().getHours();
  return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening';
};

function Panel({ title, action, children }: { title: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="glass-panel overflow-hidden" aria-label={title}>
      <div className="flex items-center justify-between gap-3 px-4 py-3 border-b border-white/[0.06]">
        <h2 className="text-sm font-semibold text-slate-100">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

const linkCls = 'text-[0.8125rem] font-medium text-blue-400 hover:text-blue-300 underline-offset-2 hover:underline';

export default function Overview() {
  const router = useRouter();
  const me = useMe();
  const coordinator = isCoordinatorRole(me?.role);
  // Overview is for staff; students belong on the Help Desk.
  useEffect(() => {
    if (me && !isStaffRole(me.role)) router.replace('/helpdesk');
  }, [me, router]);

  const [schedule, setSchedule] = useState<ScheduleResponse | null>(null);
  const [work, setWork] = useState<MyWork | null>(null);
  const [upcoming, setUpcoming] = useState<CalendarItem[]>([]);
  const [notices, setNotices] = useState<Notice[]>([]);
  const [team, setTeam] = useState<TeamGroup[] | null>(null);
  const [insights, setInsights] = useState<Insight[]>([]);
  const [error, setError] = useState('');
  const [ask, setAsk] = useState('');

  useEffect(() => {
    if (!me || !isStaffRole(me.role)) return;
    fetchSchedule(null, 1).then(setSchedule).catch(() => setSchedule(null));
    apiFetch('/api/v1/commitments/my-work')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setWork)
      .catch((e: Error) => setError(`Could not load your work (${e.message}).`));
    apiFetch('/api/v1/calendar?days=7')
      .then((r) => (r.ok ? r.json() : { items: [] }))
      .then((d: { items: CalendarItem[] }) => setUpcoming(d.items.filter((i) => i.urgency !== 'overdue')))
      .catch(() => {});
    apiFetch('/api/v1/notices/mine')
      .then((r) => (r.ok ? r.json() : []))
      .then((d: Notice[]) => setNotices(d))
      .catch(() => {});
    if (isCoordinatorRole(me.role)) {
      apiFetch('/api/v1/commitments/team').then((r) => (r.ok ? r.json() : [])).then(setTeam).catch(() => setTeam([]));
      apiFetch('/api/v1/insights/').then((r) => (r.ok ? r.json() : [])).then(setInsights).catch(() => {});
    }
  }, [me]);

  const dismissInsight = async (id: string) => {
    await apiFetch(`/api/v1/insights/${id}/dismiss`, { method: 'POST' }).catch(() => {});
    setInsights((prev) => prev.filter((i) => i.id !== id));
  };

  const firstName = (me?.full_name || '').replace(/^(Dr|Prof|Mr|Ms|Mrs)\.?\s+/i, '').split(' ')[0];
  const today = schedule?.today;
  const lectures = schedule?.items ?? [];
  const classesToday = lectures.filter((l) => l.status !== 'cancelled' && l.status !== 'holiday').length;
  const attentionList = (work?.items ?? [])
    .map((t) => ({ t, a: attention(t) }))
    .filter((x): x is { t: Task; a: NonNullable<ReturnType<typeof attention>> } => x.a !== null)
    .sort((x, y) => x.a.rank - y.a.rank);
  const dueNow = attentionList.filter((x) => x.a.rank <= 1).length;
  const unread = notices.filter((n) => !n.read).length;
  const otherUpcoming = upcoming.filter((i) => i.source !== 'commitment');

  const teamTotals = (team ?? []).reduce(
    (acc, g) => ({
      open: acc.open + g.summary.open, overdue: acc.overdue + g.summary.overdue,
      blocked: acc.blocked + g.summary.blocked, review: acc.review + g.summary.awaiting_confirmation,
    }),
    { open: 0, overdue: 0, blocked: 0, review: 0 },
  );

  const examples = [
    'What do I need to complete today?',
    'Which of my tasks are overdue?',
    'Show my classes tomorrow.',
    'Summarize my pending work.',
  ];
  const goAsk = (q: string) => router.push(`/chat?q=${encodeURIComponent(q)}`);

  const stats: { label: string; value: number | string; href: string; tone?: string }[] = [
    { label: 'Classes today', value: schedule ? (schedule.has_timetable ? classesToday : '—') : '…', href: '/commitments?view=schedule' },
    { label: 'Tasks needing attention', value: work ? attentionList.length : '…', href: '/commitments?view=tasks' },
    { label: 'Due today or overdue', value: work ? dueNow : '…', href: '/commitments?view=tasks', tone: dueNow ? 'text-rose-300' : '' },
    { label: 'Upcoming dates (7 days)', value: upcoming.length, href: '/calendar' },
    { label: 'Unread notifications', value: unread, href: '/notices' },
  ];

  const askPanel = (
    <section className="glass-panel p-4 sm:p-5 space-y-3" aria-labelledby="ask-assistant">
      <div>
        <h2 id="ask-assistant" className="text-base font-semibold text-slate-100">Ask a question</h2>
        <p className="text-[0.8125rem] text-slate-400">
          Type a question in plain words — about your work, your classes, or college records.
        </p>
      </div>
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (ask.trim()) goAsk(ask.trim());
        }}
      >
        <label htmlFor="overview-ask" className="sr-only">Ask a question</label>
        <input
          id="overview-ask"
          value={ask}
          onChange={(e) => setAsk(e.target.value)}
          placeholder="e.g. What do I need to complete today?"
          className="flex-1 min-w-0 bg-slate-900 border border-slate-700 rounded-lg px-3.5 h-11 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500"
        />
        <button type="submit" disabled={!ask.trim()} className="px-5 h-11 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold disabled:opacity-40 cursor-pointer">
          Ask
        </button>
      </form>
      <div className="flex flex-wrap gap-2">
        {(coordinator ? examples : examples.slice(0, 2)).map((q) => (
          <button key={q} type="button" onClick={() => goAsk(q)}
            className="px-3 h-8 rounded-full border border-slate-700 text-[0.8125rem] text-slate-300 hover:text-slate-100 hover:border-slate-500 cursor-pointer">
            {q}
          </button>
        ))}
      </div>
    </section>
  );

  // Faculty see every class today (a teaching day is rarely more than 6); coordinators get a preview.
  const shownLectures = coordinator ? lectures.slice(0, 5) : lectures;
  const classesPanel = (
    <Panel title="Today's classes" action={<Link href="/commitments?view=schedule" className={linkCls}>Full timetable →</Link>}>
      {!schedule ? (
        <p className="px-4 py-4 text-sm text-slate-400">Loading…</p>
      ) : !schedule.has_timetable ? (
        <p className="px-4 py-4 text-sm text-slate-400">
          No teaching timetable has been published for you yet. Your lectures will appear here once your department publishes the class timetables.
        </p>
      ) : lectures.length === 0 ? (
        <p className="px-4 py-4 text-sm text-slate-400">No classes today.</p>
      ) : (
        <ul className="divide-y divide-white/[0.05]">
          {shownLectures.map((l, i) => (
            <li key={`${l.entry_id}-${i}`} className="px-4 py-3 flex flex-wrap sm:flex-nowrap items-center gap-x-4 gap-y-1">
              <span className="w-32 text-base font-semibold text-slate-100 tabular-nums">{timeRange(l)}</span>
              <span className="flex-1 min-w-0">
                <span className="block text-base text-slate-100">
                  {l.subject ?? 'Subject not set'}{l.kind !== 'lecture' && KIND_LABEL[l.kind] ? ` (${KIND_LABEL[l.kind]})` : ''}
                </span>
                <span className="block text-sm text-slate-400">{[l.class_label, l.room ? `Room ${l.room}` : null].filter(Boolean).join(' · ')}</span>
              </span>
              {l.status !== 'scheduled' && <Badge tone={LECTURE_STATUS[l.status].tone}>{LECTURE_STATUS[l.status].label}</Badge>}
            </li>
          ))}
          {lectures.length > shownLectures.length && <li className="px-4 py-2 text-[0.8125rem] text-slate-400">+{lectures.length - shownLectures.length} more today</li>}
        </ul>
      )}
    </Panel>
  );

  const tasksPanel = (
    <Panel title={coordinator ? 'My tasks needing attention' : 'Needs your attention'} action={<Link href="/commitments?view=tasks" className={linkCls}>All my work →</Link>}>
      {!work ? (
        <p className="px-4 py-4 text-sm text-slate-400">Loading…</p>
      ) : attentionList.length === 0 ? (
        <p className="px-4 py-4 text-sm text-slate-400">
          Nothing urgent. {work.summary.open ? `You have ${work.summary.open} open task(s), none overdue or blocked.` : 'No open tasks.'}
        </p>
      ) : (
        <ul className="divide-y divide-white/[0.05]">
          {attentionList.slice(0, 6).map(({ t, a }) => (
            <li key={t.id}>
              <Link href={`/commitments?view=tasks&task=${t.id}`} className="px-4 py-2.5 flex items-start justify-between gap-3 hover:bg-white/[0.03]">
                <span className="min-w-0">
                  <span className="block text-sm text-slate-100">{t.description}</span>
                  <span className="block text-[0.8125rem] text-slate-400 mt-0.5">
                    {t.assigned_by ? `Assigned by ${t.assigned_by}` : t.source_meeting ? `From “${t.source_meeting}”` : 'Assigned directly'}
                    {` · ${t.progress}% done`}
                  </span>
                </span>
                <Badge tone={a.tone}>{a.label}</Badge>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );

  const noticesPanel = (
    <Panel title={unread ? `Notices (${unread} new)` : 'Notices'} action={<Link href="/notices" className={linkCls}>See all →</Link>}>
      {notices.length === 0 ? (
        <p className="px-4 py-4 text-sm text-slate-400">
          No notices. New assignments, deadline changes and timetable changes will appear here.
        </p>
      ) : (
        <ul className="divide-y divide-white/[0.05]">
          {notices.slice(0, coordinator ? 5 : 3).map((n) => (
            <li key={n.id} className="px-4 py-2.5">
              <p className="text-sm text-slate-100">
                {!n.read && <span className="sr-only">Unread: </span>}
                {!n.read && <span className="inline-block w-1.5 h-1.5 rounded-full bg-blue-500 mr-2 align-middle" aria-hidden="true" />}
                {n.title}
              </p>
              <p className="text-[0.8125rem] text-slate-400 line-clamp-2">{n.body}</p>
              <p className="text-[0.75rem] text-slate-500 mt-0.5">{n.sender ? `${n.sender} · ` : ''}{formatDateTime(n.created_at)}</p>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );

  const upcomingPanel = (
    <Panel title="Coming up this week" action={<Link href="/calendar" className={linkCls}>Calendar →</Link>}>
      {upcoming.length === 0 ? (
        <p className="px-4 py-4 text-sm text-slate-400">No deadlines or academic dates in the next 7 days.</p>
      ) : (
        <ul className="divide-y divide-white/[0.05]">
          {[...upcoming.filter((i) => i.source === 'commitment'), ...otherUpcoming].slice(0, 6).map((i, n) => (
            <li key={`${i.title}-${n}`} className="px-4 py-2.5">
              <p className="text-sm text-slate-100">{i.title}</p>
              <p className="text-[0.8125rem] text-slate-400">
                {CAL_KIND_LABEL[i.kind] ?? 'Date'} · {i.days_left === 0 ? 'Today' : i.days_left === 1 ? 'Tomorrow' : dayHeading(i.date, { weekday: 'short', day: 'numeric', month: 'short' })}
              </p>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );

  const welcome = (
    <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
      <div>
        <h1 className="text-xl md:text-2xl font-semibold text-slate-100 tracking-[-0.02em]">
          {/* Time-of-day text only after client data loads, so prerendered HTML and hydration match. */}
          {today ? greeting() : 'Welcome'}{firstName ? `, ${firstName}` : ''}
        </h1>
        <p className="text-slate-400 text-sm mt-1">{today ? dayHeading(today, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }) : ' '}</p>
      </div>
      {coordinator && (
        <Link href="/commitments?view=team" className="self-start lg:self-auto inline-flex items-center gap-2 px-4 h-10 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold">
          + Assign work
        </Link>
      )}
    </div>
  );

  // Faculty: one column in the order they need it (where to be, what is due, what is coming, what is new).
  // Each section is a short summary that links to its full page.
  if (!coordinator) {
    return (
      <main className="p-4 sm:p-6 md:p-10 max-w-3xl mx-auto space-y-5">
        {welcome}
        {error && <p role="alert" className="text-rose-400 text-sm">{error}</p>}
        {classesPanel}
        {tasksPanel}
        {upcomingPanel}
        {noticesPanel}
        {askPanel}
      </main>
    );
  }

  return (
    <main className="p-4 sm:p-6 md:p-10 max-w-7xl mx-auto space-y-6">
      {welcome}

      <section aria-label="Today at a glance" className="grid grid-cols-2 md:grid-cols-5 gap-2">
        {stats.map((s) => (
          <Link key={s.label} href={s.href} className="glass-panel p-3.5 hover:border-blue-500/40 transition-colors">
            <p className="text-[0.8125rem] text-slate-400">{s.label}</p>
            <p className={`text-2xl font-semibold text-slate-100 mt-1 ${s.tone ?? ''}`}>{s.value}</p>
          </Link>
        ))}
      </section>

      {error && <p role="alert" className="text-rose-400 text-sm">{error}</p>}

      {askPanel}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2 space-y-5">
          <Panel title="Team work needing attention" action={<Link href="/commitments?view=team" className={linkCls}>Open Team</Link>}>
            {team === null ? (
              <p className="px-4 py-4 text-sm text-slate-400">Loading…</p>
            ) : team.length === 0 ? (
              <p className="px-4 py-4 text-sm text-slate-400">No team tasks yet. Use “Assign work” to create one.</p>
            ) : (
              <>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-px bg-white/[0.04]">
                  {[
                    ['Open', teamTotals.open, ''], ['Overdue', teamTotals.overdue, teamTotals.overdue ? 'text-rose-300' : ''],
                    ['Blocked', teamTotals.blocked, teamTotals.blocked ? 'text-rose-300' : ''], ['To confirm', teamTotals.review, teamTotals.review ? 'text-amber-300' : ''],
                  ].map(([l, v, c]) => (
                    <div key={String(l)} className="bg-[var(--surface)] px-4 py-3">
                      <p className="text-[0.75rem] text-slate-400">{l}</p>
                      <p className={`text-lg font-semibold text-slate-100 ${c}`}>{v}</p>
                    </div>
                  ))}
                </div>
                <ul className="divide-y divide-white/[0.05]">
                  {team
                    .filter((g) => g.summary.overdue || g.summary.blocked || g.summary.awaiting_confirmation)
                    .slice(0, 6)
                    .map((g) => (
                      <li key={g.owner} className="px-4 py-2.5 flex flex-wrap items-center justify-between gap-2">
                        <span className="text-sm text-slate-200">{g.owner}</span>
                        <span className="flex flex-wrap gap-1.5">
                          {g.summary.overdue > 0 && <Badge tone="danger">{g.summary.overdue} overdue</Badge>}
                          {g.summary.blocked > 0 && <Badge tone="danger">{g.summary.blocked} blocked</Badge>}
                          {g.summary.awaiting_confirmation > 0 && <Badge tone="warning">{g.summary.awaiting_confirmation} to confirm</Badge>}
                        </span>
                      </li>
                    ))}
                </ul>
                {(work?.awaiting_my_confirmation?.length ?? 0) > 0 && (
                  <p className="px-4 py-3 border-t border-white/[0.06] text-[0.8125rem] text-slate-300">
                    {work?.awaiting_my_confirmation?.length} task(s) marked done are waiting for your confirmation.{' '}
                    <Link href="/commitments?view=team" className={linkCls}>Review now</Link>
                  </p>
                )}
              </>
            )}
          </Panel>
          {classesPanel}
          {tasksPanel}
        </div>

        <div className="space-y-5">
          {noticesPanel}
          {upcomingPanel}
          {insights.length > 0 && (
            <Panel title={`Institution alerts (${insights.length})`}>
              <div className="divide-y divide-white/[0.05]">
                {insights.slice(0, 3).map((i) => <InsightCard key={i.id} insight={i} onDismiss={dismissInsight} />)}
              </div>
            </Panel>
          )}
        </div>
      </div>
    </main>
  );
}
