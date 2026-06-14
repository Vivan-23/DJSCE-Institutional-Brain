'use client';
import React, { useCallback, useEffect, useState } from 'react';
import { apiFetch } from '@/lib/api';

const STATUSES = ['draft', 'approved', 'stale', 'deprecated', 'rejected'] as const;
type Status = (typeof STATUSES)[number];

interface SkillMeta {
  id: string;
  name: string;
  description: string;
  trigger: string;
  status: Status;
  version: number;
  updated_at: string;
}

interface Citation {
  citation_id: string;
  fragment_id: string;
  source_type: string | null;
  content: string | null;
}

interface SkillFull extends SkillMeta {
  preconditions: string[];
  steps: string[];
  decision_rules: string[];
  guardrails: string[];
  escalation: string | null;
  citations: Citation[];
}

const STATUS_STYLE: Record<Status, string> = {
  draft: 'bg-blue-500/10 border-blue-500/30 text-blue-400',
  approved: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400',
  stale: 'bg-warning/10 border-warning/30 text-warning',
  deprecated: 'bg-gray-700/20 border-gray-600/40 text-gray-500',
  rejected: 'bg-danger/10 border-danger/30 text-danger',
};

function Section({ title, items, numbered }: { title: string; items: string[]; numbered?: boolean }) {
  if (!items?.length) return null;
  return (
    <div>
      <h3 className="text-xs uppercase tracking-wide text-gray-500 mb-1.5">{title}</h3>
      <ol className={numbered ? 'list-decimal list-inside space-y-1' : 'space-y-1'}>
        {items.map((s, i) => (
          <li key={i} className="text-sm text-gray-300">
            {!numbered && <span className="text-gray-600 mr-1.5">·</span>}
            {s}
          </li>
        ))}
      </ol>
    </div>
  );
}

export default function SkillsPage() {
  const [skills, setSkills] = useState<SkillMeta[]>([]);
  const [filter, setFilter] = useState<Status | 'all'>('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<SkillFull | null>(null);
  const [fileText, setFileText] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState('');

  const load = useCallback((status: Status | 'all') => {
    const path = status === 'all' ? '/api/v1/skills' : `/api/v1/skills?status=${status}`;
    apiFetch(path)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data: SkillMeta[]) => {
        setSkills(data);
        setError('');
        setLoading(false);
      })
      .catch(() => {
        setError('Could not load skills. Is the backend running?');
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    load(filter);
  }, [load, filter]);

  const applyFilter = (next: Status | 'all') => {
    setLoading(true);
    setFilter(next);
  };

  const openDetail = async (id: string) => {
    if (expandedId === id) {
      setExpandedId(null);
      setDetail(null);
      setFileText(null);
      return;
    }
    setExpandedId(id);
    setDetail(null);
    setFileText(null);
    setActionMsg('');
    const res = await apiFetch(`/api/v1/skills/${id}`);
    if (res.ok) setDetail(await res.json());
  };

  const act = async (id: string, action: 'approve' | 'reject') => {
    setActionMsg('');
    const res = await apiFetch(`/api/v1/skills/${id}/${action}`, { method: 'POST' });
    if (res.status === 403) {
      setActionMsg('You need a manager role to review skills.');
      return;
    }
    if (res.ok) {
      await openDetail(id); // collapse
      load(filter);
    } else {
      setActionMsg(`Action failed (HTTP ${res.status}).`);
    }
  };

  const viewFile = async (id: string) => {
    const res = await apiFetch(`/api/v1/skills/${id}/file`);
    if (res.ok) {
      setFileText(await res.text());
    } else {
      setActionMsg('Only approved skills export a file.');
    }
  };

  const runExtraction = async () => {
    setActionMsg('');
    const res = await apiFetch('/api/v1/skills/extract', { method: 'POST' });
    if (res.status === 403) {
      setActionMsg('You need a manager role to run extraction.');
      return;
    }
    if (res.ok) {
      const data = await res.json();
      setActionMsg(`Extraction complete — ${data.candidates_created} candidate skill(s) created.`);
      load(filter);
    }
  };

  return (
    <main className="min-h-screen p-8 md:p-12">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-start justify-between gap-4 mb-2">
          <h1 className="text-3xl font-bold text-white">Skills</h1>
          <button
            onClick={runExtraction}
            className="text-sm bg-primary/10 border border-primary/30 text-primary px-3 py-1.5 rounded-lg hover:bg-primary/20 transition-colors"
          >
            Run extraction
          </button>
        </div>
        <p className="text-gray-400 mb-6">
          Executable procedures synthesized from your company&apos;s fragments. Review,
          approve, and export them as agent-consumable skill files.
        </p>

        {actionMsg && (
          <div className="mb-4 p-3 rounded-lg bg-primary/10 border border-primary/30 text-primary text-sm">
            {actionMsg}
          </div>
        )}

        <div className="flex flex-wrap gap-1.5 mb-6">
          {(['all', ...STATUSES] as const).map((s) => (
            <button
              key={s}
              onClick={() => applyFilter(s)}
              className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                filter === s
                  ? 'bg-primary/10 border-primary/30 text-primary'
                  : 'border-gray-700 text-gray-400 hover:text-white'
              }`}
            >
              {s === 'all' ? 'All' : s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>

        {loading ? (
          <p className="text-gray-500 text-sm">Loading skills…</p>
        ) : error ? (
          <div className="p-3 rounded-lg bg-danger/10 border border-danger/30 text-danger text-sm">
            {error}
          </div>
        ) : skills.length === 0 ? (
          <div className="glass-panel p-6 text-center text-gray-500 text-sm">
            No skills yet. Ingest fragments, then run extraction to synthesize candidates.
          </div>
        ) : (
          <ul className="space-y-3">
            {skills.map((s) => {
              const open = expandedId === s.id;
              return (
                <li key={s.id} className="glass-panel overflow-hidden">
                  <button
                    onClick={() => openDetail(s.id)}
                    className="w-full text-left p-4 hover:bg-gray-900/40 transition-colors"
                    aria-expanded={open}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <p className="text-white font-medium">{s.name}</p>
                        <p className="text-sm text-gray-400 mt-0.5 line-clamp-2">{s.description}</p>
                      </div>
                      <span
                        className={`shrink-0 text-xs px-2 py-0.5 rounded-full border ${STATUS_STYLE[s.status]}`}
                      >
                        {s.status}
                      </span>
                    </div>
                  </button>

                  {open && (
                    <div className="border-t border-gray-800 p-4 space-y-4">
                      {!detail || detail.id !== s.id ? (
                        <p className="text-gray-500 text-sm">Loading…</p>
                      ) : (
                        <>
                          {detail.trigger && (
                            <p className="text-sm text-gray-300">
                              <span className="text-gray-500">Trigger:</span> {detail.trigger}
                            </p>
                          )}
                          <Section title="Preconditions" items={detail.preconditions} />
                          <Section title="Steps" items={detail.steps} numbered />
                          <Section title="Decision Rules" items={detail.decision_rules} />
                          <Section title="Guardrails" items={detail.guardrails} />
                          {detail.escalation && (
                            <div>
                              <h3 className="text-xs uppercase tracking-wide text-gray-500 mb-1">
                                Escalation
                              </h3>
                              <p className="text-sm text-gray-300">{detail.escalation}</p>
                            </div>
                          )}

                          <div>
                            <h3 className="text-xs uppercase tracking-wide text-gray-500 mb-1.5">
                              Citations ({detail.citations.length})
                            </h3>
                            <ul className="space-y-1.5">
                              {detail.citations.slice(0, 6).map((c) => (
                                <li
                                  key={c.citation_id}
                                  className="text-xs text-gray-500 bg-black/30 border border-gray-800 rounded p-2"
                                >
                                  <span className="text-gray-600">[{c.source_type}]</span>{' '}
                                  {c.content?.slice(0, 160)}
                                </li>
                              ))}
                            </ul>
                          </div>

                          {/* Actions */}
                          <div className="flex flex-wrap gap-2 pt-2 border-t border-gray-800">
                            {detail.status !== 'approved' && (
                              <button
                                onClick={() => act(s.id, 'approve')}
                                className="text-sm bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 px-3 py-1.5 rounded-lg hover:bg-emerald-500/20 transition-colors"
                              >
                                Approve
                              </button>
                            )}
                            {detail.status !== 'rejected' && (
                              <button
                                onClick={() => act(s.id, 'reject')}
                                className="text-sm bg-danger/10 border border-danger/30 text-danger px-3 py-1.5 rounded-lg hover:bg-danger/20 transition-colors"
                              >
                                Reject
                              </button>
                            )}
                            <button
                              onClick={() => viewFile(s.id)}
                              className="text-sm border border-gray-700 text-gray-300 px-3 py-1.5 rounded-lg hover:bg-gray-900/50 transition-colors"
                            >
                              View skill file
                            </button>
                          </div>

                          {fileText && (
                            <pre className="mt-2 text-xs text-gray-400 whitespace-pre-wrap font-mono max-h-80 overflow-y-auto bg-black/40 rounded-lg p-3 border border-gray-800">
                              {fileText}
                            </pre>
                          )}
                        </>
                      )}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </main>
  );
}
