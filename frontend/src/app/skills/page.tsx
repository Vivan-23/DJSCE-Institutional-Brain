'use client';
import React, { useCallback, useEffect, useState } from 'react';
import { apiFetch } from '@/lib/api';
import EvidencePanel, { Citation } from '@/components/skills/EvidencePanel';

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

interface SkillFull extends SkillMeta {
  preconditions: string[];
  steps: string[];
  decision_rules: string[];
  guardrails: string[];
  escalation: string | null;
  citations: Citation[];
}

const STATUS_STYLE: Record<Status, { label: string; style: string }> = {
  draft: { label: 'Draft Proposal', style: 'bg-blue-500/15 border-blue-500/30 text-blue-300' },
  approved: { label: 'Ratified / Active', style: 'bg-emerald-500/15 border-emerald-500/30 text-emerald-300' },
  stale: { label: 'Under Revision (Stale)', style: 'bg-amber-500/15 border-amber-500/30 text-amber-300' },
  deprecated: { label: 'Superseded', style: 'bg-slate-700/20 border-slate-600/40 text-slate-400' },
  rejected: { label: 'Rejected by Committee', style: 'bg-rose-500/15 border-rose-500/30 text-rose-300' },
};

function Section({ title, items, numbered }: { title: string; items: string[]; numbered?: boolean }) {
  if (!items?.length) return null;
  return (
    <div>
      <h3 className="text-[11px] uppercase tracking-wider font-semibold text-slate-400 mb-1.5">{title}</h3>
      <ol className={numbered ? 'list-decimal list-inside space-y-1' : 'space-y-1'}>
        {items.map((s, i) => (
          <li key={i} className="text-xs sm:text-sm text-slate-300 leading-relaxed">
            {!numbered && <span className="text-slate-600 mr-1.5">·</span>}
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
        setError('Could not load institutional procedures. Please check backend status.');
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
      setActionMsg('Notice: Committee Convener or Academic Coordinator role required to ratify procedures.');
      return;
    }
    if (res.ok) {
      await openDetail(id);
      load(filter);
    } else {
      setActionMsg(`Procedure update failed (HTTP ${res.status}).`);
    }
  };

  const viewFile = async (id: string) => {
    const res = await apiFetch(`/api/v1/skills/${id}/file`);
    if (res.ok) {
      setFileText(await res.text());
    } else {
      setActionMsg('Notice: Only ratified and approved procedures export an executable SKILL.md file.');
    }
  };

  const runExtraction = async () => {
    setActionMsg('');
    const res = await apiFetch('/api/v1/skills/extract', { method: 'POST' });
    if (res.status === 403) {
      setActionMsg('Notice: Academic Coordinator or Administrator role required to trigger procedure synthesis.');
      return;
    }
    if (res.ok) {
      const data = await res.json();
      setActionMsg(`Extraction complete — ${data.candidates_created} candidate procedure(s) synthesized.`);
      load(filter);
    }
  };

  return (
    <main className="p-6 md:p-10 max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-slate-100 tracking-tight">
            Institutional Procedures &amp; SOPs
          </h1>
          <p className="text-slate-400 text-xs sm:text-sm mt-1">
            Structured operating procedures synthesized from committee decisions, exam bylaws, and quality audits.
          </p>
        </div>
        <button
          onClick={runExtraction}
          className="text-xs bg-blue-600/20 border border-blue-500/40 text-blue-300 px-3.5 py-2 rounded font-semibold hover:bg-blue-600/30 transition-colors shrink-0 cursor-pointer shadow-xs"
        >
          Synthesize SOPs from Records
        </button>
      </div>

      <div className="p-3 rounded bg-slate-900/60 border border-slate-800 text-xs text-slate-400 flex items-center gap-2">
        <span className="text-amber-400 font-semibold uppercase text-[10px] shrink-0">Demo Notice</span>
        <span>Generated procedures are draft demonstration workflows and do not constitute official statutory college regulations.</span>
      </div>

      {actionMsg && (
        <div className="p-3 rounded bg-blue-500/10 border border-blue-500/30 text-blue-300 text-xs">
          {actionMsg}
        </div>
      )}

      {/* Filter Tabs */}
      <div className="flex flex-wrap gap-1.5 border-b border-slate-800 pb-3">
        {(['all', ...STATUSES] as const).map((s) => {
          const label = s === 'all' ? `All Procedures (${skills.length})` : STATUS_STYLE[s].label;
          return (
            <button
              key={s}
              onClick={() => applyFilter(s)}
              className={`text-xs px-3 py-1.5 rounded-full border transition-colors cursor-pointer ${
                filter === s
                  ? 'bg-blue-600/20 border-blue-500/40 text-blue-300 font-semibold'
                  : 'border-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
              }`}
            >
              {label}
            </button>
          );
        })}
      </div>

      {/* Procedures List */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2].map((i) => (
            <div key={i} className="glass-panel p-5 animate-pulse h-20 bg-slate-900/60 rounded" />
          ))}
        </div>
      ) : error ? (
        <div className="p-4 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs">
          {error}
        </div>
      ) : skills.length === 0 ? (
        <div className="glass-panel p-8 text-center text-slate-400 text-xs space-y-2">
          <p className="font-medium text-slate-300">No procedures match the selected view.</p>
          <p className="text-[11px] text-slate-500">
            Ingest committee records and run procedure extraction to automatically synthesize candidate institutional procedures.
          </p>
        </div>
      ) : (
        <ul className="space-y-3">
          {skills.map((s) => {
            const open = expandedId === s.id;
            const badge = STATUS_STYLE[s.status] ?? STATUS_STYLE.draft;
            return (
              <li key={s.id} className="glass-panel overflow-hidden">
                <button
                  onClick={() => void openDetail(s.id)}
                  className="w-full text-left p-4 sm:p-5 hover:bg-slate-900/50 transition-colors cursor-pointer"
                  aria-expanded={open}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0 space-y-1">
                      <div className="flex items-center gap-2">
                        <span className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full border ${badge.style}`}>
                          {badge.label}
                        </span>
                        <span className="text-[11px] text-slate-400">Rev. v{s.version}</span>
                      </div>
                      <h2 className="text-sm sm:text-base font-semibold text-slate-100">
                        {s.name}
                      </h2>
                      <p className="text-xs text-slate-300 line-clamp-2">
                        {s.description}
                      </p>
                    </div>
                    <span
                      className={`text-slate-500 text-base leading-none transition-transform shrink-0 ${
                        open ? 'rotate-180' : ''
                      }`}
                      aria-hidden
                    >
                      ⌄
                    </span>
                  </div>
                </button>

                {open && (
                  <div className="border-t border-slate-800/80 p-5 space-y-5 bg-slate-950/40">
                    {detail && detail.id === s.id ? (
                      <>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                          <div className="p-3 rounded bg-slate-900/60 border border-slate-800">
                            <span className="text-[10px] uppercase tracking-wider font-semibold text-slate-400 block mb-1">
                              Invocation Trigger
                            </span>
                            <p className="text-slate-200">{detail.trigger}</p>
                          </div>
                          {detail.escalation && (
                            <div className="p-3 rounded bg-slate-900/60 border border-slate-800">
                              <span className="text-[10px] uppercase tracking-wider font-semibold text-slate-400 block mb-1">
                                Escalation Protocol
                              </span>
                              <p className="text-slate-200">{detail.escalation}</p>
                            </div>
                          )}
                        </div>

                        <Section title="Required Preconditions" items={detail.preconditions} />
                        <Section title="Mandatory Execution Steps" items={detail.steps} numbered />
                        <Section title="Decision Rules & Thresholds" items={detail.decision_rules} />
                        <Section title="Safety Guardrails & Academic Integrity Checks" items={detail.guardrails} />

                        <EvidencePanel citations={detail.citations} />

                        {/* Action buttons */}
                        <div className="pt-3 border-t border-slate-800 flex flex-wrap gap-2 text-xs">
                          {s.status === 'draft' && (
                            <>
                              <button
                                onClick={() => act(s.id, 'approve')}
                                className="px-3 py-1.5 rounded bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/40 font-semibold transition-colors cursor-pointer"
                              >
                                Ratify Procedure (Approve)
                              </button>
                              <button
                                onClick={() => act(s.id, 'reject')}
                                className="px-3 py-1.5 rounded bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/40 transition-colors cursor-pointer"
                              >
                                Reject Proposal
                              </button>
                            </>
                          )}
                          <button
                            onClick={() => viewFile(s.id)}
                            className="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-colors cursor-pointer"
                          >
                            Export Standardized SKILL.md
                          </button>
                        </div>

                        {fileText && (
                          <div className="mt-3">
                            <h4 className="text-[11px] uppercase tracking-wider font-semibold text-slate-400 mb-1">
                              Agent-Consumable Standardized SOP Specification:
                            </h4>
                            <pre className="p-3.5 rounded bg-slate-900 border border-slate-800 text-xs font-mono text-slate-300 overflow-x-auto whitespace-pre leading-relaxed">
                              {fileText}
                            </pre>
                          </div>
                        )}
                      </>
                    ) : (
                      <p className="text-slate-400 text-xs">Loading procedure details…</p>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </main>
  );
}
