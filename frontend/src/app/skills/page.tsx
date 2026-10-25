'use client';
import React, { useCallback, useEffect, useState } from 'react';
import { apiFetch } from '@/lib/api';
import { formatDate, formatDateTime } from '@/lib/format';
import { isCoordinatorRole, useMe } from '@/lib/roles';
import { useInstitution } from '@/lib/useInstitution';
import EvidencePanel, { Citation } from '@/components/skills/EvidencePanel';
import { Badge, Tag, type Tone } from '@/components/ui/Badge';
import EmptyState from '@/components/ui/EmptyState';

const STATUSES = ['draft', 'approved', 'stale', 'deprecated', 'rejected'] as const;
type Status = (typeof STATUSES)[number];

interface SkillMeta {
  id: string;
  name: string;
  description: string;
  trigger: string;
  status: Status;
  status_label: string;
  version: number;
  owner_name: string | null;
  owner_office: string | null;
  review_by: string | null;
  approved_by: string | null;
  approved_at: string | null;
  visibility: 'internal' | 'public';
  department: string;
  category: string | null;
  origin: 'extracted' | 'manual';
  use_count: number;
  stale_reason: string | null;
  reject_reason: string | null;
  updated_at: string;
}

interface SkillFull extends SkillMeta {
  preconditions: string[];
  steps: string[];
  decision_rules: string[];
  guardrails: string[];
  escalation: string | null;
  student_summary: string | null;
  stale_evidence: { source_ref: string | null; source_type: string | null; content: string }[];
  citations: Citation[];
  feedback: { helpful: number; wrong: number };
}

interface Version {
  version: number;
  approved_by: string | null;
  approved_at: string;
  snapshot: Record<string, string | string[] | null>;
}

const STATUS_TONE: Record<Status, Tone> = {
  draft: 'accent', approved: 'success', stale: 'warning', deprecated: 'neutral', rejected: 'danger',
};
const TAB_LABEL: Record<Status, string> = {
  draft: 'Drafts in review', approved: 'Approved', stale: 'Needs review', deprecated: 'Retired', rejected: 'Rejected',
};
const LIST_FIELDS: { key: 'preconditions' | 'steps' | 'decision_rules' | 'guardrails'; label: string; numbered?: boolean }[] = [
  { key: 'preconditions', label: 'Before you start' },
  { key: 'steps', label: 'Steps', numbered: true },
  { key: 'decision_rules', label: 'Decision rules' },
  { key: 'guardrails', label: 'Must never happen' },
];
const field = 'w-full bg-slate-900 border border-slate-700/80 rounded px-2 py-1.5 text-xs text-slate-100 focus:outline-none focus:border-blue-500';

async function download(path: string, fallback: string): Promise<string | null> {
  const res = await apiFetch(path);
  if (!res.ok) return `Export failed (HTTP ${res.status})`;
  const name = /filename="([^"]+)"/.exec(res.headers.get('content-disposition') ?? '')?.[1] ?? fallback;
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
  return null;
}

function ListSection({ title, items, numbered }: { title: string; items: string[]; numbered?: boolean }) {
  if (!items?.length) return null;
  return (
    <div>
      <h3 className="text-[12px] font-semibold text-slate-400 mb-1.5">{title}</h3>
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

/** Lines added / removed between two versions of a list field. */
function Diff({ label, before, after }: { label: string; before: string[]; after: string[] }) {
  const removed = before.filter((x) => !after.includes(x));
  const added = after.filter((x) => !before.includes(x));
  if (!removed.length && !added.length) return null;
  return (
    <div className="text-xs">
      <p className="text-slate-400 font-semibold">{label}</p>
      {removed.map((x) => <p key={`-${x}`} className="text-rose-300">− {x}</p>)}
      {added.map((x) => <p key={`+${x}`} className="text-emerald-300">+ {x}</p>)}
    </div>
  );
}

function Editor({ d, onSaved, onCancel }: { d: SkillFull; onSaved: (msg: string) => void; onCancel: () => void }) {
  const { departments } = useInstitution();
  const [f, setF] = useState({
    name: d.name, description: d.description, trigger: d.trigger, escalation: d.escalation ?? '',
    preconditions: d.preconditions.join('\n'), steps: d.steps.join('\n'),
    decision_rules: d.decision_rules.join('\n'), guardrails: d.guardrails.join('\n'),
    owner_office: d.owner_office ?? '', visibility: d.visibility, department: d.department,
    category: d.category ?? '', student_summary: d.student_summary ?? '',
  });
  const [error, setError] = useState('');
  const lines = (s: string) => s.split('\n').map((x) => x.trim()).filter(Boolean);

  const save = async () => {
    const res = await apiFetch(`/api/v1/skills/${d.id}`, {
      method: 'PATCH',
      body: JSON.stringify({
        ...f, escalation: f.escalation || undefined,
        preconditions: lines(f.preconditions), steps: lines(f.steps), decision_rules: lines(f.decision_rules),
        guardrails: lines(f.guardrails),
      }),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) return setError(body.detail ?? `HTTP ${res.status}`);
    onSaved(d.status === 'approved' && body.status === 'draft'
      ? `Saved as version ${body.version} (draft). Version ${d.version} stays in use until the new one is approved.`
      : 'Saved.');
  };

  return (
    <div className="space-y-3 text-xs">
      {d.status === 'approved' && (
        <p className="text-amber-300/90">Changing the content creates version {d.version + 1} for review; settings-only changes keep the approval.</p>
      )}
      <input className={field} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} aria-label="Name" />
      <textarea className={field} rows={2} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} aria-label="Description" />
      <input className={field} value={f.trigger} onChange={(e) => setF({ ...f, trigger: e.target.value })} placeholder="When it applies" aria-label="When it applies" />
      {LIST_FIELDS.map((lf) => (
        <label key={lf.key} className="block">
          <span className="text-slate-400">{lf.label} (one per line)</span>
          <textarea className={field} rows={Math.max(2, f[lf.key].split('\n').length)} value={f[lf.key]}
            onChange={(e) => setF({ ...f, [lf.key]: e.target.value })} />
        </label>
      ))}
      <input className={field} value={f.escalation} onChange={(e) => setF({ ...f, escalation: e.target.value })} placeholder="Escalation" aria-label="Escalation" />
      <div className="grid sm:grid-cols-2 gap-2">
        <input className={field} value={f.owner_office} onChange={(e) => setF({ ...f, owner_office: e.target.value })} placeholder="Owning office (e.g. Examination Cell)" aria-label="Owning office" />
        <select className={field} value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })} aria-label="Category">
          <option value="">No category</option>
          {['academics', 'examinations', 'attendance', 'facilities', 'careers', 'general'].map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <select className={field} value={f.department} onChange={(e) => setF({ ...f, department: e.target.value })} aria-label="Department">
          <option value="all">Institution-wide</option>
          {departments.map((x) => <option key={x.code} value={x.code}>{x.name}</option>)}
        </select>
        <select className={field} value={f.visibility} onChange={(e) => setF({ ...f, visibility: e.target.value as 'internal' | 'public' })} aria-label="Visibility">
          <option value="internal">Staff only</option>
          <option value="public">Student-facing (students see the summary)</option>
        </select>
      </div>
      {f.visibility === 'public' && (
        <label className="block">
          <span className="text-slate-400">What students need to do (leave empty to let the AI draft it on approval)</span>
          <textarea className={field} rows={3} value={f.student_summary} onChange={(e) => setF({ ...f, student_summary: e.target.value })} />
        </label>
      )}
      {error && <p role="alert" className="text-rose-400">{error}</p>}
      <div className="flex gap-2">
        <button type="button" onClick={save} className="px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-white cursor-pointer">Save</button>
        <button type="button" onClick={onCancel} className="px-3 py-1.5 rounded border border-slate-700 text-slate-300 cursor-pointer">Cancel</button>
      </div>
    </div>
  );
}

function NewProcedure({ onCreated }: { onCreated: (id: string) => void }) {
  const [f, setF] = useState({ name: '', description: '', trigger: '', steps: '', owner_office: '' });
  const [error, setError] = useState('');
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const res = await apiFetch('/api/v1/skills', {
      method: 'POST',
      body: JSON.stringify({ ...f, steps: f.steps.split('\n').map((x) => x.trim()).filter(Boolean) }),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) return setError(body.detail ?? `HTTP ${res.status}`);
    setF({ name: '', description: '', trigger: '', steps: '', owner_office: '' });
    onCreated(body.id);
  };
  return (
    <form onSubmit={submit} className="glass-panel p-4 space-y-2" aria-label="Write a procedure">
      <p className="text-sm font-semibold text-slate-100">Write a procedure</p>
      <p className="text-[12px] text-slate-400">It starts as a draft and goes through the same review as extracted procedures.</p>
      <input required className={field} placeholder="Name (e.g. Issue a bonafide certificate)" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />
      <input className={field} placeholder="What it is for" value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} />
      <input className={field} placeholder="When it applies" value={f.trigger} onChange={(e) => setF({ ...f, trigger: e.target.value })} />
      <textarea required className={field} rows={4} placeholder="Steps, one per line" value={f.steps} onChange={(e) => setF({ ...f, steps: e.target.value })} />
      <input className={field} placeholder="Owning office" value={f.owner_office} onChange={(e) => setF({ ...f, owner_office: e.target.value })} />
      {error && <p role="alert" className="text-rose-400 text-xs">{error}</p>}
      <button type="submit" className="px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold cursor-pointer">Create draft</button>
    </form>
  );
}

export default function SkillsPage() {
  const me = useMe();
  const coordinator = isCoordinatorRole(me?.role);
  const [skills, setSkills] = useState<SkillMeta[]>([]);
  const [filter, setFilter] = useState<Status | 'all'>('all');
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('');
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');
  const [openId, setOpenId] = useState<string | null>(null);
  const [detail, setDetail] = useState<SkillFull | null>(null);
  const [view, setView] = useState<'read' | 'edit' | 'versions'>('read');
  const [versions, setVersions] = useState<Version[]>([]);
  const [rejectReason, setRejectReason] = useState('');
  const [approveOffice, setApproveOffice] = useState('');
  const [showNew, setShowNew] = useState(false);

  const load = useCallback(() => {
    const qs = new URLSearchParams();
    if (filter !== 'all') qs.set('status', filter);
    if (query.trim()) qs.set('q', query.trim());
    if (category) qs.set('category', category);
    apiFetch(`/api/v1/skills${qs.toString() ? `?${qs}` : ''}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((d: SkillMeta[]) => {
        setSkills(d);
        setError('');
      })
      .catch(() => setError('Could not load institutional procedures. Please check backend status.'));
  }, [filter, query, category]);

  useEffect(() => {
    const t = setTimeout(load, 200);
    return () => clearTimeout(t);
  }, [load]);

  const openDetail = useCallback(async (id: string, keepView = false) => {
    setOpenId(id);
    if (!keepView) setView('read');
    const res = await apiFetch(`/api/v1/skills/${id}`);
    if (res.ok) {
      const d: SkillFull = await res.json();
      setDetail(d);
      setApproveOffice(d.owner_office ?? '');
    }
  }, []);

  const showVersions = async (id: string) => {
    setView('versions');
    const res = await apiFetch(`/api/v1/skills/${id}/versions`);
    if (res.ok) setVersions((await res.json()).versions);
  };

  const act = async (id: string, path: string, body?: object, done?: string) => {
    const res = await apiFetch(`/api/v1/skills/${id}/${path}`, { method: 'POST', body: JSON.stringify(body ?? {}) });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return setMsg(data.detail ?? `HTTP ${res.status}`);
    setMsg(done ?? '');
    setRejectReason('');
    await openDetail(id);
    load();
  };

  const runExtraction = async () => {
    const res = await apiFetch('/api/v1/skills/extract', { method: 'POST' });
    if (res.ok) {
      setMsg(`Extraction complete: ${(await res.json()).candidates_created} new draft procedure(s).`);
      load();
    } else setMsg(res.status === 403 ? 'A Committee Coordinator or above runs extraction.' : `HTTP ${res.status}`);
  };

  const d = detail && detail.id === openId ? detail : null;
  const reviewOverdue = (s: SkillMeta) => s.review_by && new Date(s.review_by) < new Date();

  return (
    <main className="p-4 sm:p-6 md:p-10 max-w-7xl mx-auto space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div>
          <h1 className="text-xl md:text-2xl font-semibold text-slate-100 tracking-[-0.02em]">Procedures</h1>
          <p className="text-slate-400 text-xs sm:text-sm mt-1">
            Step-by-step guides for recurring college work. Each guide explains what to do, who is responsible, and
            which rules or checks to follow. Guides are written from committee records and must be reviewed by a
            coordinator before they count as approved; approved guides are what the assistant cites first. Demo guides
            are illustrative, not official DJSCE regulations.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 shrink-0">
          <button onClick={async () => setMsg((await download('/api/v1/skills/handbook?format=pdf', 'Procedures_Handbook.pdf')) ?? '')}
            className="text-xs border border-slate-700 text-slate-200 px-3 py-2 rounded hover:border-blue-500/60 cursor-pointer">
            Handbook (PDF)
          </button>
          {coordinator && (
            <>
              <button onClick={() => setShowNew((v) => !v)} className="text-xs border border-slate-700 text-slate-200 px-3 py-2 rounded hover:border-blue-500/60 cursor-pointer">
                {showNew ? 'Close' : 'Write a procedure'}
              </button>
              <button onClick={runExtraction} className="text-xs bg-blue-600/20 border border-blue-500/40 text-blue-300 px-3 py-2 rounded font-semibold hover:bg-blue-600/30 cursor-pointer">
                Extract from records
              </button>
            </>
          )}
        </div>
      </div>

      <p className="text-[12px] text-slate-500">
        Demonstration content: procedures here are synthetic and are not official DJSCE regulations.
      </p>
      {msg && <div role="status" className="p-3 rounded bg-blue-500/10 border border-blue-500/30 text-blue-300 text-xs">{msg}</div>}
      {showNew && <NewProcedure onCreated={(id) => { setShowNew(false); load(); void openDetail(id); }} />}

      <div className="flex flex-wrap items-center gap-2">
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search name, purpose, office…"
          className="bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1.5 text-xs text-slate-100 w-60" aria-label="Search procedures" />
        <select value={category} onChange={(e) => setCategory(e.target.value)} aria-label="Category"
          className="bg-slate-900 border border-slate-700/80 rounded px-2 py-1.5 text-xs text-slate-100">
          <option value="">All categories</option>
          {['academics', 'examinations', 'attendance', 'facilities', 'careers', 'general'].map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Status">
          {(['all', ...STATUSES] as const).map((s) => (
            <button key={s} role="tab" aria-selected={filter === s} onClick={() => setFilter(s)}
              className={`text-xs px-3 py-1.5 rounded-full border cursor-pointer ${
                filter === s ? 'bg-blue-600/20 border-blue-500/40 text-blue-300 font-semibold' : 'border-slate-800 text-slate-400 hover:text-slate-200'}`}>
              {s === 'all' ? 'All' : TAB_LABEL[s]}
            </button>
          ))}
        </div>
      </div>

      {error && <div className="p-4 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs">{error}</div>}

      <div className={`grid gap-4 ${openId ? 'lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]' : ''}`}>
        <ul className="glass-panel divide-y divide-white/[0.05] overflow-hidden self-start">
          {!error && skills.length === 0 && (
            <li><EmptyState icon="search" title="No procedures here" body="Nothing matches this filter. Try another status or clear the search." /></li>
          )}
          {skills.map((s) => (
            <li key={s.id}>
              <button type="button" onClick={() => void openDetail(s.id)}
                className={`w-full text-left px-4 py-3 cursor-pointer transition-colors ${openId === s.id ? 'bg-white/[0.05]' : 'hover:bg-white/[0.025]'}`}>
                <div className="flex items-center gap-3">
                  <p className="flex-1 min-w-0 text-[13px] font-medium text-slate-100 truncate">{s.name}</p>
                  <Badge tone={STATUS_TONE[s.status]}>{s.status_label}</Badge>
                </div>
                <p className="mt-0.5 text-[12px] text-slate-400 line-clamp-1">{s.description}</p>
                <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[12px] text-slate-500">
                  <Tag>v{s.version}</Tag>
                  {s.visibility === 'public' && <Tag>Student-facing</Tag>}
                  {s.department !== 'all' && <Tag>{s.department}</Tag>}
                  <span>{s.owner_office ?? 'No owning office'}</span>
                  {s.review_by && <span>· review by {formatDate(s.review_by)}</span>}
                  {reviewOverdue(s) && <span className="text-rose-300">· review overdue</span>}
                  {s.use_count ? <span>· cited {s.use_count}×</span> : null}
                  {s.origin === 'manual' && <span>· written by hand</span>}
                </div>
              </button>
            </li>
          ))}
        </ul>

        {openId && (
          <aside className="glass-panel p-4 space-y-4 text-xs" aria-label="Procedure">
            {!d ? <p className="text-slate-400">Loading…</p> : (
              <>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-base font-semibold text-slate-100">{d.name}</p>
                    <p className="text-slate-400">{d.status_label} · version {d.version}</p>
                  </div>
                  <button type="button" onClick={() => { setOpenId(null); setDetail(null); }} className="text-slate-400 hover:text-slate-200 cursor-pointer" aria-label="Close">✕</button>
                </div>

                <div className="flex gap-1.5" role="tablist" aria-label="Procedure view">
                  {(['read', ...(coordinator ? ['edit'] : []), 'versions'] as const).map((v) => (
                    <button key={v} role="tab" aria-selected={view === v}
                      onClick={() => (v === 'versions' ? void showVersions(d.id) : setView(v as 'read' | 'edit'))}
                      className={`px-2.5 py-1 rounded border cursor-pointer ${view === v ? 'border-blue-500/40 text-blue-300' : 'border-slate-800 text-slate-400'}`}>
                      {v === 'read' ? 'Procedure' : v === 'edit' ? 'Edit' : 'Versions'}
                    </button>
                  ))}
                </div>

                {view === 'edit' && coordinator && (
                  <Editor d={d} onCancel={() => setView('read')}
                    onSaved={(m) => { setMsg(m); setView('read'); void openDetail(d.id); load(); }} />
                )}

                {view === 'versions' && (
                  <div className="space-y-3">
                    {versions.length === 0 && <p className="text-slate-500">No approved version yet.</p>}
                    {versions.map((v, i) => {
                      const prev = versions[i + 1];
                      return (
                        <div key={v.version} className="border-l-2 border-slate-700 pl-3 space-y-1">
                          <p className="text-slate-200 font-semibold">Version {v.version}</p>
                          <p className="text-[12px] text-slate-500">Approved by {v.approved_by ?? '—'} · {formatDateTime(v.approved_at)}</p>
                          {prev ? (
                            LIST_FIELDS.map((lf) => (
                              <Diff key={lf.key} label={lf.label} before={(prev.snapshot[lf.key] as string[]) ?? []}
                                after={(v.snapshot[lf.key] as string[]) ?? []} />
                            ))
                          ) : <p className="text-[12px] text-slate-500">First approved version.</p>}
                        </div>
                      );
                    })}
                  </div>
                )}

                {view === 'read' && (
                  <>
                    <dl className="grid grid-cols-[7.5rem_1fr] gap-x-3 gap-y-1 text-slate-300">
                      <dt className="text-slate-500">Owning office</dt><dd>{d.owner_office ?? '—'}{d.owner_name ? ` (${d.owner_name})` : ''}</dd>
                      <dt className="text-slate-500">Review by</dt>
                      <dd className={reviewOverdue(d) ? 'text-rose-300' : ''}>{d.review_by ? formatDate(d.review_by) : '—'}</dd>
                      <dt className="text-slate-500">Approved</dt><dd>{d.approved_by ? `${d.approved_by} · ${formatDate(d.approved_at)}` : '—'}</dd>
                      <dt className="text-slate-500">Who can see it</dt>
                      <dd>{d.visibility === 'public' ? 'Staff + students (summary)' : 'Staff only'} · {d.department === 'all' ? 'institution-wide' : d.department}</dd>
                      <dt className="text-slate-500">Used</dt><dd>cited in {d.use_count} answer(s) or ticket draft(s)</dd>
                    </dl>

                    {d.status === 'stale' && (
                      <div className="p-3 rounded border border-amber-500/40 bg-amber-500/5 space-y-1">
                        <p className="text-amber-300 font-semibold">Needs review: {d.stale_reason ?? 'new evidence may contradict it'}</p>
                        {d.stale_evidence.map((e, i) => (
                          <p key={i} className="text-slate-300">“{e.content}” <span className="text-slate-500">({e.source_ref ?? e.source_type})</span></p>
                        ))}
                        <p className="text-[12px] text-slate-500">It is not cited by the assistant until it is approved again.</p>
                      </div>
                    )}
                    {d.status === 'rejected' && d.reject_reason && (
                      <p className="p-2 rounded border border-rose-500/30 text-rose-300">Rejected: {d.reject_reason}</p>
                    )}

                    {d.description && <p className="text-slate-300">{d.description}</p>}
                    <p><span className="text-slate-500">When it applies: </span><span className="text-slate-200">{d.trigger || '—'}</span></p>
                    {LIST_FIELDS.map((lf) => <ListSection key={lf.key} title={lf.label} items={d[lf.key]} numbered={lf.numbered} />)}
                    {d.escalation && <p><span className="text-slate-500">Escalation: </span><span className="text-slate-200">{d.escalation}</span></p>}
                    {d.visibility === 'public' && (
                      <div className="p-3 rounded border border-emerald-500/30 bg-emerald-500/5">
                        <p className="text-[12px] text-emerald-300 font-semibold mb-1">What students see</p>
                        <p className="text-slate-200">{d.student_summary ?? 'Drafted automatically when approved.'}</p>
                      </div>
                    )}

                    <EvidencePanel citations={d.citations} />

                    {coordinator && (d.status === 'draft' || d.status === 'stale') && (
                      <div className="space-y-2 border-t border-slate-800 pt-3">
                        <div className="flex flex-wrap gap-2">
                          <input className={`${field} flex-1`} value={approveOffice} onChange={(e) => setApproveOffice(e.target.value)}
                            placeholder="Owning office" aria-label="Owning office for approval" />
                          <button type="button" onClick={() => act(d.id, 'approve', { owner_office: approveOffice || undefined },
                            'Approved. The assistant now cites this version.')}
                            className="px-3 py-1.5 rounded bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/40 font-semibold cursor-pointer">
                            Approve v{d.version}
                          </button>
                        </div>
                        <div className="flex gap-2">
                          <input className={`${field} flex-1`} value={rejectReason} onChange={(e) => setRejectReason(e.target.value)}
                            placeholder="Reason for rejecting" aria-label="Reason for rejecting" />
                          <button type="button" disabled={!rejectReason.trim()} onClick={() => act(d.id, 'reject', { reason: rejectReason }, 'Rejected.')}
                            className="px-3 py-1.5 rounded border border-rose-500/40 text-rose-300 disabled:opacity-40 cursor-pointer">
                            Reject
                          </button>
                        </div>
                      </div>
                    )}

                    <div className="flex flex-wrap items-center gap-2 border-t border-slate-800 pt-3">
                      {d.status === 'approved' && (
                        <>
                          <span className="text-slate-400">Was this right?</span>
                          <button type="button" onClick={() => act(d.id, 'feedback', { outcome: 'helpful' }, 'Thanks for the feedback.')}
                            className="px-2 py-1 rounded border border-slate-700 text-slate-200 cursor-pointer">Helpful ({d.feedback.helpful})</button>
                          <button type="button" onClick={() => act(d.id, 'feedback', { outcome: 'wrong' }, 'Reported. Three reports send it back for review.')}
                            className="px-2 py-1 rounded border border-slate-700 text-slate-200 cursor-pointer">Wrong or outdated ({d.feedback.wrong})</button>
                        </>
                      )}
                      <span className="ml-auto flex gap-2">
                        {(['pdf', 'docx'] as const).map((f) => (
                          <button key={f} type="button" onClick={async () => setMsg((await download(`/api/v1/skills/${d.id}/export?format=${f}`, `SOP.${f}`)) ?? '')}
                            className="px-2 py-1 rounded border border-slate-700 text-slate-200 cursor-pointer">{f.toUpperCase()}</button>
                        ))}
                        {coordinator && d.status === 'approved' && (
                          <button type="button" onClick={() => act(d.id, 'retire', {}, 'Retired: no longer cited.')}
                            className="px-2 py-1 rounded border border-slate-700 text-slate-400 hover:text-rose-300 cursor-pointer">Retire</button>
                        )}
                      </span>
                    </div>
                  </>
                )}
              </>
            )}
          </aside>
        )}
      </div>
    </main>
  );
}
