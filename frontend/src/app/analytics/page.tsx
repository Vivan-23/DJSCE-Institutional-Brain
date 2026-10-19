'use client';
import React, { useEffect, useState } from 'react';
import { apiFetch } from '@/lib/api';

interface MeetingRow {
  meeting: string;
  department: string;
  open: number;
  review: number;
  blocked: number;
  done: number;
  dropped: number;
  overdue: number;
  total: number;
  average_progress: number | null;
}

interface QuestionGroup {
  question: string;
  count: number;
  no_sources: number;
}

interface Analytics {
  commitments_by_meeting: MeetingRow[];
  tickets: {
    total: number;
    by_status: Record<string, number>;
    by_category: ({ category: string; total: number } & Record<string, number | string>)[];
    triage_method: Record<string, number>;
    resolution_hours: { n: number; median: number | null; mean: number | null };
    open_over_48h: number;
  };
  questions: {
    days: number;
    total: number;
    by_role: Record<string, number>;
    by_topic: Record<string, number>;
    top: QuestionGroup[];
    knowledge_gaps: QuestionGroup[];
  };
  knowledge: {
    fragments: number;
    by_visibility: Record<string, number>;
    by_department: Record<string, number>;
    procedures_by_status: Record<string, number>;
  };
}

const RANGES = [7, 30, 90];

function Stat({ label, value, hint }: { label: string; value: React.ReactNode; hint?: string }) {
  return (
    <div className="glass-panel p-4">
      <p className="text-[12px] text-slate-400">{label}</p>
      <p className="text-2xl font-semibold text-slate-100 mt-1">{value}</p>
      {hint && <p className="text-[12px] text-slate-500 mt-0.5">{hint}</p>}
    </div>
  );
}

/** Horizontal bars for a {label: count} map. */
function Bars({ data, color = 'bg-blue-500/70' }: { data: Record<string, number>; color?: string }) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...entries.map(([, v]) => v));
  if (entries.length === 0) return <p className="text-xs text-slate-500">No data yet.</p>;
  return (
    <ul className="space-y-1.5">
      {entries.map(([k, v]) => (
        <li key={k} className="grid grid-cols-[8rem_1fr_2.5rem] items-center gap-2 text-xs">
          <span className="text-slate-300 truncate" title={k}>{k.replace(/_/g, ' ')}</span>
          <span className="h-2 rounded bg-slate-800 overflow-hidden">
            <span className={`block h-full ${color}`} style={{ width: `${(v / max) * 100}%` }} />
          </span>
          <span className="text-slate-400 text-right">{v}</span>
        </li>
      ))}
    </ul>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="glass-panel p-4 space-y-3">
      <h2 className="text-sm font-semibold text-slate-100">{title}</h2>
      {children}
    </section>
  );
}

export default function AnalyticsPage() {
  const [days, setDays] = useState(30);
  const [data, setData] = useState<Analytics | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    apiFetch(`/api/v1/analytics?days=${days}`)
      .then((r) => {
        if (!r.ok) throw new Error(r.status === 403 ? 'Analytics is available to committee coordinators and administrators.' : `HTTP ${r.status}`);
        return r.json();
      })
      .then((d: Analytics) => {
        setData(d);
        setError('');
      })
      .catch((e: Error) => setError(e.message));
  }, [days]);

  const t = data?.tickets;
  const q = data?.questions;

  return (
    <main className="p-4 sm:p-6 md:p-10 max-w-7xl mx-auto space-y-5">
      <div>
        <h1 className="text-xl md:text-2xl font-semibold text-slate-100 tracking-[-0.02em]">Analytics</h1>
        <p className="text-slate-400 text-xs sm:text-sm mt-1">
          Open commitments per committee, help-desk resolution times and what people ask the assistant.
        </p>
      </div>

      <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Question window">
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
            Questions: last {r} days
          </button>
        ))}
      </div>

      {error && <p role="alert" className="text-rose-400 text-xs">{error}</p>}

      {data && t && q && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <Stat
              label="Open commitments"
              value={data.commitments_by_meeting.reduce((n, r) => n + r.open, 0)}
              hint={`${data.commitments_by_meeting.reduce((n, r) => n + r.overdue, 0)} overdue`}
            />
            <Stat label="Tickets" value={t.total} hint={`${t.by_status.open ?? 0} open · ${t.open_over_48h} waiting > 48 h`} />
            <Stat
              label="Median time to reply"
              value={t.resolution_hours.median === null ? '—' : `${t.resolution_hours.median} h`}
              hint={t.resolution_hours.n ? `over ${t.resolution_hours.n} replied tickets` : 'no replies yet'}
            />
            <Stat label="Questions asked" value={q.total} hint={`last ${q.days} days`} />
          </div>

          <Panel title="Commitments by committee meeting">
            {data.commitments_by_meeting.length === 0 ? (
              <p className="text-xs text-slate-500">No commitments yet.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead className="text-slate-400 text-left">
                    <tr>
                      <th className="py-1.5 pr-3 font-medium">Meeting</th>
                      <th className="py-1.5 pr-3 font-medium">Dept</th>
                      <th className="py-1.5 pr-3 font-medium text-right">Open</th>
                      <th className="py-1.5 pr-3 font-medium text-right">Overdue</th>
                      <th className="py-1.5 pr-3 font-medium text-right">Blocked</th>
                      <th className="py-1.5 pr-3 font-medium text-right">Avg progress</th>
                      <th className="py-1.5 pr-3 font-medium text-right">To confirm</th>
                      <th className="py-1.5 pr-3 font-medium text-right">Done</th>
                      <th className="py-1.5 font-medium text-right">Total</th>
                    </tr>
                  </thead>
                  <tbody className="text-slate-200">
                    {data.commitments_by_meeting.map((r) => (
                      <tr key={r.meeting} className="border-t border-slate-800/80">
                        <td className="py-1.5 pr-3">{r.meeting}</td>
                        <td className="py-1.5 pr-3 text-slate-400">{r.department}</td>
                        <td className="py-1.5 pr-3 text-right">{r.open}</td>
                        <td className={`py-1.5 pr-3 text-right ${r.overdue ? 'text-rose-300' : ''}`}>{r.overdue}</td>
                        <td className={`py-1.5 pr-3 text-right ${r.blocked ? 'text-rose-300' : ''}`}>{r.blocked}</td>
                        <td className="py-1.5 pr-3 text-right">{r.average_progress === null ? '—' : `${r.average_progress}%`}</td>
                        <td className={`py-1.5 pr-3 text-right ${r.review ? 'text-amber-300' : ''}`}>{r.review}</td>
                        <td className="py-1.5 pr-3 text-right">{r.done}</td>
                        <td className="py-1.5 text-right">{r.total}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>

          <div className="grid lg:grid-cols-2 gap-4">
            <Panel title="Tickets by status">
              <Bars data={t.by_status} />
            </Panel>
            <Panel title="Tickets by category">
              <Bars data={Object.fromEntries(t.by_category.map((c) => [c.category, c.total]))} color="bg-emerald-500/70" />
            </Panel>
            <Panel title="Most-asked questions">
              {q.top.length === 0 ? (
                <p className="text-xs text-slate-500">No questions in this window.</p>
              ) : (
                <ol className="space-y-1 text-xs text-slate-200 list-decimal list-inside">
                  {q.top.map((g) => (
                    <li key={g.question}>
                      {g.question} <span className="text-slate-500">× {g.count}</span>
                    </li>
                  ))}
                </ol>
              )}
            </Panel>
            <Panel title="Knowledge gaps (nothing relevant found)">
              {q.knowledge_gaps.length === 0 ? (
                <p className="text-xs text-slate-500">Every question found at least one source.</p>
              ) : (
                <ul className="space-y-1 text-xs text-slate-200">
                  {q.knowledge_gaps.map((g) => (
                    <li key={g.question}>
                      {g.question} <span className="text-slate-500">× {g.no_sources}</span>
                    </li>
                  ))}
                </ul>
              )}
              <p className="text-[12px] text-slate-500">Add documents that answer these, then mark them public if students ask them.</p>
            </Panel>
            <Panel title="Questions by topic">
              <Bars data={q.by_topic} color="bg-violet-500/70" />
            </Panel>
            <Panel title="Questions by role">
              <Bars data={q.by_role} color="bg-amber-500/70" />
            </Panel>
            <Panel title="Indexed knowledge by department">
              <Bars data={data.knowledge.by_department} color="bg-sky-500/70" />
            </Panel>
            <Panel title="Procedures by status">
              <Bars data={data.knowledge.procedures_by_status} color="bg-teal-500/70" />
            </Panel>
          </div>
        </>
      )}
    </main>
  );
}
