'use client';
import React, { useEffect, useState } from 'react';
import { apiFetch } from '@/lib/api';
import { Badge, type Tone } from '@/components/ui/Badge';
import { formatDate } from '@/lib/format';

type Urgency = 'overdue' | 'today' | 'soon' | 'upcoming';

interface CalendarItem {
  date: string;
  end: string | null;
  title: string;
  kind: string;
  department: string;
  source: 'calendar' | 'commitment';
  meeting?: string | null;
  status?: string;
  days_left: number;
  urgency: Urgency;
}

interface CalendarResponse {
  note: string;
  soon_days: number;
  items: CalendarItem[];
}

const URGENCY: Record<Urgency, { label: string; style: string; tone: Tone }> = {
  overdue: { label: 'Overdue', style: 'bg-rose-500/15 text-rose-300 border-rose-500/40', tone: 'danger' },
  today: { label: 'Today', style: 'bg-amber-500/15 text-amber-300 border-amber-500/40', tone: 'warning' },
  soon: { label: 'Soon', style: 'bg-yellow-500/10 text-yellow-200 border-yellow-500/30', tone: 'accent' },
  upcoming: { label: 'Upcoming', style: 'bg-slate-700/30 text-slate-300 border-slate-600/50', tone: 'neutral' },
};

const KIND_DOT: Record<string, string> = {
  exam: 'bg-rose-400',
  deadline: 'bg-amber-400',
  holiday: 'bg-emerald-400',
  term: 'bg-blue-400',
  commitment: 'bg-violet-400',
};

const RANGES = [30, 60, 120];

function when(item: CalendarItem): string {
  if (item.days_left < 0) return `${-item.days_left} day${item.days_left === -1 ? '' : 's'} overdue`;
  if (item.days_left === 0) return item.end ? 'In progress' : 'Today';
  return `In ${item.days_left} day${item.days_left === 1 ? '' : 's'}`;
}

export default function CalendarPage() {
  const [days, setDays] = useState(60);
  const [data, setData] = useState<CalendarResponse | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    apiFetch(`/api/v1/calendar?days=${days}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d: CalendarResponse) => {
        setData(d);
        setError('');
      })
      .catch((e: Error) => setError(`Could not load the calendar (${e.message}).`));
  }, [days]);

  const items = data?.items ?? [];
  const urgent = items.filter((i) => i.urgency !== 'upcoming');

  return (
    <main className="p-4 sm:p-6 md:p-10 max-w-5xl mx-auto space-y-5">
      <div>
        <h1 className="text-xl md:text-2xl font-semibold text-slate-100 tracking-[-0.02em]">Calendar</h1>
        <p className="text-slate-400 text-xs sm:text-sm mt-1">
          Published academic dates for your department, plus your own commitments from meetings (faculty).
        </p>
        {data?.note && <p className="text-amber-300/80 text-[12px] mt-2">{data.note}</p>}
      </div>

      <div className="flex flex-wrap items-center gap-1.5" role="tablist" aria-label="Date range">
        {RANGES.map((r) => (
          <button
            key={r}
            role="tab"
            aria-selected={days === r}
            onClick={() => setDays(r)}
            className={`px-3 py-1.5 rounded text-xs font-medium border cursor-pointer ${
              days === r ? 'bg-blue-600/15 text-blue-300 border-blue-500/40' : 'text-slate-400 border-slate-800 hover:text-slate-200'
            }`}
          >
            Next {r} days
          </button>
        ))}
      </div>

      {error && <p role="alert" className="text-rose-400 text-xs">{error}</p>}

      {urgent.length > 0 && (
        <section className="glass-panel p-4 border border-amber-500/30" aria-label="Reminders">
          <h2 className="text-sm font-semibold text-amber-200 mb-2">
            Reminders: {urgent.length} item{urgent.length === 1 ? '' : 's'} overdue or due within {data?.soon_days} days
          </h2>
          <ul className="space-y-1">
            {urgent.map((i) => (
              <li key={`r-${i.source}-${i.date}-${i.title}`} className="text-xs text-slate-200">
                <span className="text-slate-400">{formatDate(i.date)}</span> · {i.title}{' '}
                <span className="text-slate-500">({when(i)})</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <ul className="space-y-2" aria-label="Upcoming dates">
        {data && items.length === 0 && <li className="text-xs text-slate-500">Nothing scheduled in this range.</li>}
        {items.map((i) => (
          <li key={`${i.source}-${i.date}-${i.title}`} className="glass-panel p-3 flex items-start gap-3">
            <span className={`mt-1.5 w-2 h-2 rounded-full shrink-0 ${KIND_DOT[i.kind] ?? 'bg-slate-400'}`} aria-hidden />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-medium text-slate-100">{i.title}</p>
                <Badge tone={URGENCY[i.urgency].tone}>{URGENCY[i.urgency].label}</Badge>
              </div>
              <p className="text-[12px] text-slate-400 mt-0.5">
                {formatDate(i.date)}
                {i.end ? ` – ${formatDate(i.end)}` : ''} · {when(i)} · {i.kind}
                {i.department !== 'all' ? ` · ${i.department} only` : ''}
                {i.meeting ? ` · from “${i.meeting}”` : ''}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </main>
  );
}
