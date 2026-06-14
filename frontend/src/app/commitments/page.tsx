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
  open: 'Open',
  in_progress: 'In Progress',
  blocked: 'Blocked',
  done: 'Done',
  dropped: 'Dropped',
};

const STATUS_STYLE: Record<Status, string> = {
  open: 'bg-blue-500/10 border-blue-500/30 text-blue-400',
  in_progress: 'bg-amber-500/10 border-amber-500/30 text-amber-400',
  blocked: 'bg-danger/10 border-danger/30 text-danger',
  done: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400',
  dropped: 'bg-gray-700/20 border-gray-600/40 text-gray-500',
};

function formatDate(iso: string | null): string {
  if (!iso) return '—';
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

  // State is only set inside the async callbacks (never synchronously in the
  // effect body); callers flip the spinner before invoking when desired.
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
        // The /mine endpoint has no server-side status filter; apply it here.
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
    // Optimistic update.
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
      // Revert on failure.
      load(filter, mineOnly);
    } finally {
      setUpdatingId(null);
    }
  };

  return (
    <main className="min-h-screen p-8 md:p-12">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold mb-2 text-white">Commitments</h1>
        <p className="text-gray-400 mb-8">
          Action items extracted from meetings. Update status as work
          progresses — Company Brain follows up on stale open items.
        </p>

        {/* Controls */}
        <div className="flex flex-wrap items-center gap-3 mb-6">
          <div className="flex flex-wrap gap-1.5">
            <button
              onClick={() => applyFilter('all')}
              className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                filter === 'all'
                  ? 'bg-primary/10 border-primary/30 text-primary'
                  : 'border-gray-700 text-gray-400 hover:text-white'
              }`}
            >
              All
            </button>
            {STATUSES.map((s) => (
              <button
                key={s}
                onClick={() => applyFilter(s)}
                className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                  filter === s
                    ? 'bg-primary/10 border-primary/30 text-primary'
                    : 'border-gray-700 text-gray-400 hover:text-white'
                }`}
              >
                {STATUS_LABEL[s]}
              </button>
            ))}
          </div>

          <label className="flex items-center gap-2 text-xs text-gray-400 ml-auto cursor-pointer select-none">
            <input
              type="checkbox"
              checked={mineOnly}
              onChange={(e) => toggleMine(e.target.checked)}
              className="accent-primary"
            />
            Assigned to me
          </label>
        </div>

        {loading ? (
          <p className="text-gray-500 text-sm">Loading commitments…</p>
        ) : error ? (
          <div className="p-3 rounded-lg bg-danger/10 border border-danger/30 text-danger text-sm">
            {error}
          </div>
        ) : commitments.length === 0 ? (
          <div className="glass-panel p-6 text-center text-gray-500 text-sm">
            No commitments match this view.
          </div>
        ) : (
          <ul className="space-y-3">
            {commitments.map((c) => (
              <li key={c.id} className="glass-panel p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <p className="text-white text-sm">{c.description}</p>
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-xs text-gray-500">
                      <span>
                        Owner:{' '}
                        <span className="text-gray-400">
                          {c.assignee ?? 'Unassigned'}
                        </span>
                      </span>
                      <span>Due: {formatDate(c.due_date)}</span>
                      {c.confidence != null && (
                        <span>Confidence: {(c.confidence * 100).toFixed(0)}%</span>
                      )}
                    </div>
                  </div>

                  <span
                    className={`shrink-0 text-xs px-2 py-0.5 rounded-full border ${STATUS_STYLE[c.status]}`}
                  >
                    {STATUS_LABEL[c.status]}
                  </span>
                </div>

                <div className="mt-3 pt-3 border-t border-gray-800 flex items-center gap-2">
                  <label
                    htmlFor={`status-${c.id}`}
                    className="text-xs text-gray-500"
                  >
                    Set status:
                  </label>
                  <select
                    id={`status-${c.id}`}
                    value={c.status}
                    disabled={updatingId === c.id}
                    onChange={(e) => void updateStatus(c.id, e.target.value as Status)}
                    className="text-xs bg-black/40 border border-gray-700 rounded-md px-2 py-1 text-gray-300 focus:outline-none focus:border-primary/60 disabled:opacity-50"
                  >
                    {STATUSES.map((s) => (
                      <option key={s} value={s}>
                        {STATUS_LABEL[s]}
                      </option>
                    ))}
                  </select>
                  {updatingId === c.id && (
                    <span className="text-xs text-gray-600">saving…</span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </main>
  );
}
