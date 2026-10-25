'use client';
import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { Badge } from '@/components/ui/Badge';
import EmptyState from '@/components/ui/EmptyState';
import {
  addDays, CAL_KIND_LABEL, dayHeading, fetchCalendarRange, fetchSchedule, KIND_LABEL, LECTURE_STATUS,
  timeRange, weekStart, type CalendarItem, type Lecture, type ScheduleResponse,
} from '@/lib/schedule';

type Mode = 'day' | 'week';

interface Loaded {
  key: string;
  schedule: ScheduleResponse;
  other: CalendarItem[];
}

function LectureRow({ l }: { l: Lecture }) {
  const st = LECTURE_STATUS[l.status];
  const struck = l.status === 'cancelled' || l.status === 'holiday';
  return (
    <li className="flex flex-wrap sm:flex-nowrap items-start gap-x-4 gap-y-1 px-4 py-3">
      <div className="w-28 shrink-0">
        <p className={`text-sm font-semibold text-slate-100 tabular-nums ${struck ? 'line-through text-slate-500' : ''}`}>{timeRange(l)}</p>
        {l.original && (
          <p className="text-[12px] text-slate-500 line-through tabular-nums">
            {l.original.start_time}–{l.original.end_time}
          </p>
        )}
      </div>
      <div className="min-w-0 flex-1">
        <p className={`text-sm font-medium text-slate-100 ${struck ? 'line-through text-slate-500' : ''}`}>
          <span className="inline-block mr-2 px-1.5 rounded bg-blue-500/15 text-blue-300 text-[11px] font-semibold align-middle no-underline">
            {KIND_LABEL[l.kind] ?? 'Lecture'}
          </span>
          {l.subject ?? 'Subject not set'}
        </p>
        <p className="text-[13px] text-slate-400 mt-0.5">
          {[l.class_label, l.batch ? `Batch ${l.batch}` : null, l.room ? `Room ${l.room}` : 'Room not set'].filter(Boolean).join(' · ')}
        </p>
        {l.note && <p className="text-[13px] text-slate-400 mt-0.5">Note: {l.note}</p>}
      </div>
      <Badge tone={st.tone}>{st.label}</Badge>
    </li>
  );
}

function OtherRow({ i }: { i: CalendarItem }) {
  const isTask = i.source === 'commitment';
  const body = (
    <>
      <div className="w-28 shrink-0 text-[13px] text-slate-500">{isTask ? 'Due' : 'All day'}</div>
      <div className="min-w-0 flex-1">
        <p className="text-sm text-slate-200">
          <span className="inline-block mr-2 px-1.5 rounded bg-amber-500/15 text-amber-300 text-[11px] font-semibold align-middle">
            {CAL_KIND_LABEL[i.kind] ?? 'Date'}
          </span>
          {i.title}
        </p>
        {i.meeting && <p className="text-[13px] text-slate-500 mt-0.5">From “{i.meeting}”</p>}
      </div>
    </>
  );
  return (
    <li>
      {isTask && i.commitment_id ? (
        <Link href={`/commitments?view=tasks&task=${i.commitment_id}`} className="flex items-start gap-4 px-4 py-3 hover:bg-white/[0.03]">
          {body}
        </Link>
      ) : (
        <div className="flex items-start gap-4 px-4 py-3">{body}</div>
      )}
    </li>
  );
}

/** My Schedule (My Work) and My Timetable (Calendar): published lectures plus dated items, by day. */
export default function ScheduleView({ defaultMode = 'day', showOther = true }: { defaultMode?: Mode; showOther?: boolean }) {
  const [mode, setMode] = useState<Mode>(defaultMode);
  const [anchor, setAnchor] = useState<string | null>(null); // null = today (server timezone)
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [error, setError] = useState('');

  const start = anchor === null ? null : mode === 'week' ? weekStart(anchor) : anchor;
  const days = mode === 'week' ? 7 : 1;
  const key = `${mode}:${start ?? 'today'}`;

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      // With no anchor yet, ask the server for "today" in the institution's timezone first.
      let s = start;
      if (s === null) {
        const { today } = await fetchSchedule(null, 1);
        s = mode === 'week' ? weekStart(today) : today;
      }
      const schedule = await fetchSchedule(s, days);
      const other = showOther ? await fetchCalendarRange(schedule.today, s, days) : [];
      if (!cancelled) {
        setLoaded({ key, schedule, other });
        setError('');
        if (start === null) setAnchor(schedule.today);
      }
    };
    run().catch((e: Error) => !cancelled && setError(`Could not load your schedule (${e.message}).`));
    return () => {
      cancelled = true;
    };
  }, [key, start, days, mode, showOther]);

  const current = loaded && (loaded.key === key || anchor === null) ? loaded : null;
  const today = loaded?.schedule.today ?? null;
  const shownStart = current?.schedule.start ?? start;
  const step = (n: number) => anchor && setAnchor(addDays(anchor, n * days));

  const dates = shownStart ? Array.from({ length: days }, (_, i) => addDays(shownStart, i)) : [];
  const rangeLabel = shownStart
    ? mode === 'day'
      ? dayHeading(shownStart)
      : `${dayHeading(shownStart, { day: 'numeric', month: 'short' })} – ${dayHeading(addDays(shownStart, 6), { day: 'numeric', month: 'short', year: 'numeric' })}`
    : 'Loading…';

  const btn = 'h-9 px-3 rounded-lg border border-slate-700 text-sm text-slate-200 hover:bg-white/[0.05] cursor-pointer disabled:opacity-40';

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="inline-flex rounded-lg border border-slate-700 p-0.5" role="group" aria-label="Day or week view">
          {(['day', 'week'] as Mode[]).map((m) => (
            <button
              key={m}
              type="button"
              aria-pressed={mode === m}
              onClick={() => setMode(m)}
              className={`h-8 px-3 rounded-md text-sm cursor-pointer ${mode === m ? 'bg-blue-600 text-white' : 'text-slate-300 hover:text-slate-100'}`}
            >
              {m === 'day' ? 'Day' : 'Week'}
            </button>
          ))}
        </div>
        <button type="button" className={btn} onClick={() => step(-1)} disabled={!anchor} aria-label={`Previous ${mode}`}>
          ← Previous
        </button>
        <button type="button" className={btn} onClick={() => today && setAnchor(today)} disabled={!today}>
          Today
        </button>
        <button type="button" className={btn} onClick={() => step(1)} disabled={!anchor} aria-label={`Next ${mode}`}>
          Next →
        </button>
        <label className="flex items-center gap-2 text-sm text-slate-400">
          <span className="sr-only sm:not-sr-only">Go to date</span>
          <input
            type="date"
            value={anchor ?? ''}
            onChange={(e) => e.target.value && setAnchor(e.target.value)}
            className="h-9 bg-slate-900 border border-slate-700 rounded-lg px-2 text-sm text-slate-100"
          />
        </label>
      </div>
      <h2 className="text-base font-semibold text-slate-100" aria-live="polite">{rangeLabel}</h2>

      {error && <p role="alert" className="text-rose-400 text-sm">{error}</p>}
      {!current && !error && <p className="text-sm text-slate-400" role="status">Loading schedule…</p>}

      {current && !current.schedule.has_timetable && (
        <div className="glass-panel">
          <EmptyState
            icon="calendar"
            title="No teaching timetable published for you yet"
            body="Once your department uploads and publishes the class timetables, your lectures appear here automatically. Task deadlines and academic dates are still shown below."
          />
        </div>
      )}

      {current && (
        <div className="space-y-3">
          {dates.map((d) => {
            const lectures = current.schedule.items.filter((l) => l.date === d);
            const other = current.other.filter((i) => (i.end ? i.date <= d && d <= i.end : i.date === d));
            // The "no timetable" notice above already explains an empty day.
            if (!current.schedule.has_timetable && !lectures.length && !other.length) return null;
            if (mode === 'week' && !lectures.length && !other.length) {
              return (
                <p key={d} className="text-[13px] text-slate-500 px-1">
                  <span className="font-medium text-slate-400">{dayHeading(d, { weekday: 'long', day: 'numeric', month: 'short' })}</span> · nothing scheduled
                </p>
              );
            }
            return (
              <section key={d} aria-label={dayHeading(d)}>
                {mode === 'week' && (
                  <h3 className={`text-sm font-semibold mb-1.5 ${d === today ? 'text-blue-300' : 'text-slate-300'}`}>
                    {dayHeading(d, { weekday: 'long', day: 'numeric', month: 'short' })}
                    {d === today ? ' · Today' : ''}
                  </h3>
                )}
                {!lectures.length && !other.length ? (
                  <div className="glass-panel px-4 py-6 text-center text-sm text-slate-400">Nothing scheduled for this day.</div>
                ) : (
                  <ul className="glass-panel divide-y divide-white/[0.05] overflow-hidden">
                    {lectures.map((l, i) => <LectureRow key={`${l.entry_id ?? l.exception_id}-${i}`} l={l} />)}
                    {other.map((i, n) => <OtherRow key={`${i.title}-${n}`} i={i} />)}
                  </ul>
                )}
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
