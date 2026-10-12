'use client';
import React, { useCallback, useEffect, useState } from 'react';
import { apiFetch } from '@/lib/api';

const STATUSES = ['open', 'in_progress', 'blocked', 'done', 'dropped'] as const;
type Status = (typeof STATUSES)[number];

interface Commitment {
  id: string;
  description: string;
  assignee: string | null;
  assignee_employee_id: string | null;
  status: Status;
  due_date: string | null;
  source_meeting_id: string | null;
  confidence: number | null;
  last_followup_at: string | null;
  created_at: string;
}

const STATUS_LABEL: Record<Status, string> = {
  open: 'Pending',
  in_progress: 'In Progress',
  blocked: 'Blocked / Escalated',
  done: 'Completed',
  dropped: 'Deferred',
};

const STATUS_STYLE: Record<Status, string> = {
  open: 'bg-blue-500/15 border-blue-500/30 text-blue-300',
  in_progress: 'bg-amber-500/15 border-amber-500/30 text-amber-300',
  blocked: 'bg-rose-500/15 border-rose-500/30 text-rose-300',
  done: 'bg-emerald-500/15 border-emerald-500/30 text-emerald-300',
  dropped: 'bg-slate-700/20 border-slate-600/40 text-slate-400',
};

function formatDate(iso: string | null): string {
  if (!iso) return 'Not specified';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export default function CommitmentsPage() {
  const [commitments, setCommitments] = useState<Commitment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState<Status | 'all'>('all');
  const [mineOnly, setMineOnly] = useState(false);
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  const load = useCallback((statusFilter: Status | 'all', mine: boolean) => {
    let path: string;
    if (mine) {
      path = '/api/v1/commitments/mine';
    } else if (statusFilter !== 'all') {
      path = `/api/v1/commitments?status=${statusFilter}`;
    } else {
      path = '/api/v1/commitments';
    }
    apiFetch(path)
      .then((r) => {
        if (!r.ok) throw new Error(`Failed to load commitments (HTTP ${r.status})`);
        return r.json();
      })
      .then((data: Commitment[]) => {
        const filtered =
          mine && statusFilter !== 'all'
            ? data.filter((c) => c.status === statusFilter)
            : data;
        setCommitments(filtered);
        setError('');
        setLoading(false);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Failed to load commitments');
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    load(filter, mineOnly);
  }, [load, filter, mineOnly]);

  const applyFilter = (next: Status | 'all') => {
    setLoading(true);
    setFilter(next);
  };

  const toggleMine = (mine: boolean) => {
    setLoading(true);
    setMineOnly(mine);
  };

  const updateStatus = async (id: string, status: Status) => {
    setUpdatingId(id);
    setCommitments((prev) =>
      prev.map((c) => (c.id === id ? { ...c, status } : c)),
    );
    try {
      const res = await apiFetch(`/api/v1/commitments/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status }),
      });
      if (!res.ok) throw new Error();
      const updated = (await res.json()) as Commitment;
      setCommitments((prev) => prev.map((c) => (c.id === id ? updated : c)));
    } catch {
      load(filter, mineOnly);
    } finally {
      setUpdatingId(null);
    }
  };

  return (
    <main className="p-6 md:p-10 max-w-4xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl md:text-3xl font-bold text-slate-100 tracking-tight">
          Action Commitments &amp; Responsibilities
        </h1>
        <p className="text-slate-400 text-xs sm:text-sm mt-1">
          Track actionable institutional responsibilities, accreditation deliverables, and committee follow-up deadlines extracted from meeting records.
        </p>
      </div>

      {/* Filter and View Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div className="flex flex-wrap gap-1.5">
          <button
            onClick={() => applyFilter('all')}
            className={`text-xs px-3 py-1.5 rounded-full border transition-colors cursor-pointer ${
              filter === 'all'
                ? 'bg-blue-600/20 border-blue-500/40 text-blue-300 font-semibold'
                : 'border-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
            }`}
          >
            All Items ({commitments.length})
          </button>
          {STATUSES.map((s) => (
            <button
              key={s}
              onClick={() => applyFilter(s)}
              className={`text-xs px-3 py-1.5 rounded-full border transition-colors cursor-pointer ${
                filter === s
                  ? 'bg-blue-600/20 border-blue-500/40 text-blue-300 font-semibold'
                  : 'border-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
              }`}
            >
              {STATUS_LABEL[s]}
            </button>
          ))}
        </div>

        <label className="flex items-center gap-2 text-xs text-slate-400 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={mineOnly}
            onChange={(e) => toggleMine(e.target.checked)}
            className="accent-blue-500 w-4 h-4 rounded"
          />
          <span>Assigned to my profile</span>
        </label>
      </div>

      {/* Commitment List */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="glass-panel p-4 animate-pulse h-20 bg-slate-900/60 rounded" />
          ))}
        </div>
      ) : error ? (
        <div className="p-4 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs">
          {error}
        </div>
      ) : commitments.length === 0 ? (
        <div className="glass-panel p-8 text-center text-slate-400 text-xs">
          No commitments found matching the current filter.
        </div>
      ) : (
        <ul className="space-y-3">
          {commitments.map((c) => (
            <li key={c.id} className="glass-panel p-4 sm:p-5 space-y-3">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 space-y-1.5">
                  <p className="text-slate-100 text-sm font-medium leading-relaxed">
                    {c.description}
                  </p>
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-400">
                    <span>
                      Responsible Person:{' '}
                      <strong className="text-slate-200 font-medium">
                        {c.assignee ?? 'Unassigned Faculty/Staff'}
                      </strong>
                    </span>
                    <span>Deadline: {formatDate(c.due_date)}</span>
                    {c.confidence != null && (
                      <span className="text-slate-400">Confidence: {(c.confidence * 100).toFixed(0)}%</span>
                    )}
                  </div>
                </div>

                <span
                  className={`shrink-0 text-[11px] font-semibold px-2.5 py-0.5 rounded-full border ${STATUS_STYLE[c.status]}`}
                >
                  {STATUS_LABEL[c.status]}
                </span>
              </div>

              <div className="pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <label htmlFor={`status-${c.id}`} className="text-slate-400 font-medium">
                    Update Workflow Status:
                  </label>
                  <select
                    id={`status-${c.id}`}
                    value={c.status}
                    disabled={updatingId === c.id}
                    onChange={(e) => void updateStatus(c.id, e.target.value as Status)}
                    className="bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-slate-200 focus:outline-none focus:border-blue-500 text-xs cursor-pointer"
                  >
                    {STATUSES.map((s) => (
                      <option key={s} value={s}>
                        {STATUS_LABEL[s]}
                      </option>
                    ))}
                  </select>
                </div>
                {updatingId === c.id && (
                  <span className="text-[11px] text-blue-400 animate-pulse">Syncing change…</span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
