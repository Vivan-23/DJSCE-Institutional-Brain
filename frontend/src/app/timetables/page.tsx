'use client';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { apiFetch } from '@/lib/api';
import { Badge, type Tone } from '@/components/ui/Badge';
import EmptyState from '@/components/ui/EmptyState';
import { formatDate, formatDateTime } from '@/lib/format';
import { isCoordinatorRole, useMe } from '@/lib/roles';

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

interface Issue { code: string; text: string; blocking: boolean }
interface Entry {
  id: string; weekday: number | null; day: string | null; start_time: string | null; end_time: string | null;
  subject: string | null; room: string | null; faculty_abbrev: string | null; faculty_user_id: string | null;
  faculty_name: string | null; kind: string; batch: string | null; source_cell: string | null; edited: boolean; issues: Issue[];
}
interface Counts { entries: number; blocking: number; warnings: number; by_issue: Record<string, number> }
interface Summary {
  id: string; class_key: string | null; class_label: string | null; year_label: string | null; division: string | null;
  semester: string | null; academic_term: string | null; effective_from: string | null; source_filename: string;
  version: number; status: 'extracting' | 'failed' | 'draft' | 'published' | 'superseded' | 'discarded';
  extraction_method: string | null; extraction_error: string | null; uploaded_by: string | null; created_at: string;
  published_at: string | null; published_by: string | null; counts: Counts;
}
interface Detail extends Summary {
  legend: { code: string; subject: string; faculty: string }[];
  extraction_notes: string[];
  entries: Entry[];
  diff: null | { published_version: number; added: Entry[]; removed: Entry[]; changed: { before: Entry; after: Entry }[]; unchanged: number };
}
interface Suggestion {
  abbrev: string; subjects: string[]; legend_names: string[]; ambiguous: boolean;
  candidates: { user_id: string; name: string; email: string; department: string | null; reason: string }[];
}
interface Staff { user_id: string; name: string; email: string; department: string | null }
interface Alias { id: string; abbrev: string; user_id: string; name: string | null; verified_by: string | null; created_at: string }
interface Change {
  id: string; date: string; kind: string; subject: string | null; class_label: string | null;
  start_time: string | null; end_time: string | null; room: string | null; reason: string | null;
}

const STATUS: Record<Summary['status'], { label: string; tone: Tone }> = {
  extracting: { label: 'Reading the file…', tone: 'accent' },
  failed: { label: 'Could not read', tone: 'danger' },
  draft: { label: 'Draft · needs review', tone: 'warning' },
  published: { label: 'Published', tone: 'success' },
  superseded: { label: 'Replaced by newer version', tone: 'neutral' },
  discarded: { label: 'Discarded', tone: 'neutral' },
};
const CHANGE_LABEL: Record<string, string> = {
  cancelled: 'Cancelled', modified: 'Rescheduled', holiday: 'Holiday', extra: 'Extra lecture',
};

const field = 'h-9 bg-slate-900 border border-slate-700 rounded-md px-2 text-sm text-slate-100';
const btn = 'h-9 px-3 rounded-md text-sm font-medium cursor-pointer disabled:opacity-40';
const primary = `${btn} bg-blue-600 hover:bg-blue-500 text-white`;
const secondary = `${btn} border border-slate-700 text-slate-200 hover:bg-white/[0.05]`;

async function readError(res: Response): Promise<string> {
  const d = await res.json().catch(() => ({}));
  return typeof d.detail === 'string' ? d.detail : `Request failed (HTTP ${res.status})`;
}

function entryLine(e: Entry): string {
  return [e.day, e.start_time && e.end_time ? `${e.start_time}–${e.end_time}` : null, e.subject, e.batch ? `batch ${e.batch}` : null,
    e.faculty_abbrev, e.room ? `room ${e.room}` : null].filter(Boolean).join(' · ');
}

// ── upload + list ───────────────────────────────────────────────────────────
function Uploads({ onOpen }: { onOpen: (id: string) => void }) {
  const [items, setItems] = useState<Summary[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const load = useCallback(() => {
    apiFetch('/api/v1/timetables').then((r) => (r.ok ? r.json() : [])).then(setItems).catch(() => {});
  }, []);
  useEffect(() => {
    load();
  }, [load]);
  // While anything is being read, refresh every few seconds.
  const extracting = items.some((i) => i.status === 'extracting');
  useEffect(() => {
    if (!extracting) return;
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [extracting, load]);

  const upload = async (files: FileList | null) => {
    if (!files?.length) return;
    setBusy(true);
    setMsg(null);
    const done: string[] = [];
    for (const f of Array.from(files)) {
      const fd = new FormData();
      fd.append('file', f);
      const res = await apiFetch('/api/v1/timetables', { method: 'POST', body: fd });
      if (!res.ok) {
        setMsg({ ok: false, text: `${f.name}: ${await readError(res)}` });
        continue;
      }
      const d = await res.json();
      done.push(d.duplicate ? `${f.name} (already uploaded)` : f.name);
    }
    setBusy(false);
    if (done.length) setMsg({ ok: true, text: `Uploaded: ${done.join(', ')}. Each one is read into a draft for you to review.` });
    load();
  };

  return (
    <div className="space-y-4">
      <section className="glass-panel p-5 space-y-3" aria-labelledby="upload-heading">
        <h2 id="upload-heading" className="text-base font-semibold text-slate-100">Upload class timetables</h2>
        <p className="text-[13px] text-slate-400">
          Photos (PNG/JPG), PDF, Word (.docx), Excel (.xlsx) or CSV. You can select several files at once. Each file is
          read into a <strong className="text-slate-200">draft</strong> — nothing reaches anyone&apos;s schedule until you
          review it and press Publish. Photos are read by an AI model, so check every entry against the sheet.
        </p>
        <label className={`${primary} inline-flex items-center ${busy ? 'opacity-50 pointer-events-none' : ''}`}>
          {busy ? 'Uploading…' : 'Choose files'}
          <input type="file" multiple accept=".png,.jpg,.jpeg,.webp,.pdf,.docx,.xlsx,.csv" className="sr-only"
            onChange={(e) => { upload(e.target.files); e.target.value = ''; }} />
        </label>
        {msg && <p role="status" className={`text-[13px] ${msg.ok ? 'text-emerald-400' : 'text-rose-400'}`}>{msg.ok ? '✓ ' : '⚠ '}{msg.text}</p>}
      </section>

      {items.length === 0 ? (
        <div className="glass-panel"><EmptyState icon="calendar" title="No timetables uploaded yet" body="Upload the class timetables above to build each faculty member's teaching schedule." /></div>
      ) : (
        <ul className="glass-panel divide-y divide-white/[0.05] overflow-hidden" aria-label="Uploaded timetables">
          {items.map((i) => (
            <li key={i.id}>
              <button type="button" onClick={() => onOpen(i.id)} className="w-full text-left px-4 py-3 hover:bg-white/[0.03] cursor-pointer">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-medium text-slate-100">
                    {i.class_label ?? 'Class not identified'}{i.semester ? ` · Sem ${i.semester}` : ''} · version {i.version}
                  </p>
                  <Badge tone={STATUS[i.status].tone}>{STATUS[i.status].label}</Badge>
                </div>
                <p className="text-[13px] text-slate-400 mt-0.5">
                  {i.source_filename} · {i.counts.entries} entries
                  {i.status === 'draft' && ` · ${i.counts.blocking} need fixing · ${i.counts.warnings} warnings`}
                  {' · '}uploaded {formatDateTime(i.created_at)}{i.uploaded_by ? ` by ${i.uploaded_by}` : ''}
                </p>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ── review one timetable ────────────────────────────────────────────────────
function EntryEditor({ initial, onSave, onCancel }: {
  initial: Partial<Entry>; onSave: (f: Record<string, unknown>) => Promise<string | null>; onCancel: () => void;
}) {
  const [f, setF] = useState({
    weekday: initial.weekday ?? 0, start_time: initial.start_time ?? '', end_time: initial.end_time ?? '',
    subject: initial.subject ?? '', batch: initial.batch ?? '', kind: initial.kind ?? 'lecture',
    room: initial.room ?? '', faculty_abbrev: initial.faculty_abbrev ?? '',
  });
  const [err, setErr] = useState('');
  const set = (k: keyof typeof f, v: string | number) => setF({ ...f, [k]: v });
  return (
    <form
      className="flex flex-wrap items-end gap-2 p-3 bg-slate-900/60"
      onSubmit={async (e) => {
        e.preventDefault();
        const error = await onSave({ ...f, batch: f.batch || null, room: f.room || null, faculty_abbrev: f.faculty_abbrev || null });
        if (error) setErr(error);
      }}
    >
      <label className="text-[12px] text-slate-400">Day<br />
        <select value={f.weekday} onChange={(e) => set('weekday', Number(e.target.value))} className={field}>
          {DAYS.slice(0, 6).map((d, i) => <option key={d} value={i}>{d}</option>)}
        </select>
      </label>
      <label className="text-[12px] text-slate-400">Start<br /><input type="time" required value={f.start_time} onChange={(e) => set('start_time', e.target.value)} className={field} /></label>
      <label className="text-[12px] text-slate-400">End<br /><input type="time" required value={f.end_time} onChange={(e) => set('end_time', e.target.value)} className={field} /></label>
      <label className="text-[12px] text-slate-400">Subject<br /><input required value={f.subject} onChange={(e) => set('subject', e.target.value)} className={`${field} w-24`} /></label>
      <label className="text-[12px] text-slate-400">Batch<br /><input value={f.batch} onChange={(e) => set('batch', e.target.value)} className={`${field} w-20`} /></label>
      <label className="text-[12px] text-slate-400">Type<br />
        <select value={f.kind} onChange={(e) => set('kind', e.target.value)} className={field}>
          <option value="lecture">Lecture</option><option value="lab">Lab</option><option value="tutorial">Tutorial</option>
        </select>
      </label>
      <label className="text-[12px] text-slate-400">Room<br /><input value={f.room} onChange={(e) => set('room', e.target.value)} className={`${field} w-24`} /></label>
      <label className="text-[12px] text-slate-400">Initials<br /><input value={f.faculty_abbrev} maxLength={4} onChange={(e) => set('faculty_abbrev', e.target.value.toUpperCase())} className={`${field} w-20`} /></label>
      <button type="submit" className={primary}>Save</button>
      <button type="button" onClick={onCancel} className={secondary}>Cancel</button>
      {err && <p role="alert" className="w-full text-[13px] text-rose-400">{err}</p>}
    </form>
  );
}

function DateChangeForm({ entry, onDone }: { entry: Entry; onDone: (msg: string) => void }) {
  const [f, setF] = useState({ on_date: '', kind: 'cancelled', start_time: '', end_time: '', room: '', reason: '' });
  const [err, setErr] = useState('');
  return (
    <form
      className="flex flex-wrap items-end gap-2 p-3 bg-slate-900/60"
      onSubmit={async (e) => {
        e.preventDefault();
        const res = await apiFetch('/api/v1/schedule/exceptions', {
          method: 'POST',
          body: JSON.stringify({
            on_date: f.on_date, kind: f.kind, entry_id: entry.id, reason: f.reason || null,
            ...(f.kind === 'modified' ? { start_time: f.start_time || null, end_time: f.end_time || null, room: f.room || null } : {}),
          }),
        });
        if (!res.ok) return setErr(await readError(res));
        onDone(`${f.kind === 'cancelled' ? 'Cancelled' : 'Rescheduled'} ${entry.subject} on ${f.on_date}. ${entry.faculty_name ?? 'The faculty member'} has been notified.`);
      }}
    >
      <label className="text-[12px] text-slate-400">Date (a {entry.day})<br /><input type="date" required value={f.on_date} onChange={(e) => setF({ ...f, on_date: e.target.value })} className={field} /></label>
      <label className="text-[12px] text-slate-400">Change<br />
        <select value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })} className={field}>
          <option value="cancelled">Cancel this lecture</option><option value="modified">Move time / room</option>
        </select>
      </label>
      {f.kind === 'modified' && (
        <>
          <label className="text-[12px] text-slate-400">New start<br /><input type="time" value={f.start_time} onChange={(e) => setF({ ...f, start_time: e.target.value })} className={field} /></label>
          <label className="text-[12px] text-slate-400">New end<br /><input type="time" value={f.end_time} onChange={(e) => setF({ ...f, end_time: e.target.value })} className={field} /></label>
          <label className="text-[12px] text-slate-400">New room<br /><input value={f.room} onChange={(e) => setF({ ...f, room: e.target.value })} className={`${field} w-24`} /></label>
        </>
      )}
      <label className="text-[12px] text-slate-400 flex-1 min-w-[10rem]">Reason (shown to faculty)<br /><input value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} className={`${field} w-full`} /></label>
      <button type="submit" className={primary}>Apply to that date only</button>
      {err && <p role="alert" className="w-full text-[13px] text-rose-400">{err}</p>}
    </form>
  );
}

function Review({ id, onBack }: { id: string; onBack: () => void }) {
  const [d, setD] = useState<Detail | null>(null);
  const [sugg, setSugg] = useState<Suggestion[]>([]);
  const [staff, setStaff] = useState<Staff[]>([]);
  const [pick, setPick] = useState<Record<string, string>>({});
  const [sourceUrl, setSourceUrl] = useState<{ url: string; type: string } | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [changing, setChanging] = useState<string | null>(null);
  const [onlyProblems, setOnlyProblems] = useState(false);
  const [ack, setAck] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [header, setHeader] = useState<Record<string, string>>({});

  const load = useCallback(() => {
    apiFetch(`/api/v1/timetables/${id}`).then((r) => (r.ok ? r.json() : null)).then((x: Detail | null) => {
      if (!x) return;
      setD(x);
      setHeader({ year_label: x.year_label ?? '', division: x.division ?? '', semester: x.semester ?? '',
        academic_term: x.academic_term ?? '', effective_from: x.effective_from ?? '' });
    }).catch(() => {});
    apiFetch(`/api/v1/timetables/${id}/suggestions`).then((r) => (r.ok ? r.json() : [])).then((s: Suggestion[]) => {
      setSugg(s);
      // Pre-select only an unambiguous candidate; the coordinator still has to press Confirm.
      setPick((p) => ({ ...Object.fromEntries(s.filter((x) => x.candidates.length === 1).map((x) => [x.abbrev, x.candidates[0].user_id])), ...p }));
    }).catch(() => {});
  }, [id]);

  useEffect(() => {
    load();
    apiFetch('/api/v1/timetables/staff').then((r) => (r.ok ? r.json() : [])).then(setStaff).catch(() => {});
  }, [load]);

  useEffect(() => {
    if (d?.status !== 'extracting') return;
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [d?.status, load]);

  useEffect(() => {
    let url: string | null = null;
    apiFetch(`/api/v1/timetables/${id}/source`).then(async (r) => {
      if (!r.ok) return;
      const blob = await r.blob();
      url = URL.createObjectURL(blob);
      setSourceUrl({ url, type: blob.type });
    }).catch(() => {});
    return () => { if (url) URL.revokeObjectURL(url); };
  }, [id]);

  const call = async (path: string, init: RequestInit, ok: string) => {
    const res = await apiFetch(`/api/v1/timetables/${id}${path}`, init);
    if (!res.ok) {
      const text = await readError(res);
      setMsg({ ok: false, text });
      return text;
    }
    setMsg({ ok: true, text: ok });
    load();
    return null;
  };

  const confirmAlias = async (abbrev: string) => {
    const user_id = pick[abbrev];
    if (!user_id) return;
    const res = await apiFetch('/api/v1/timetables/aliases', { method: 'POST', body: JSON.stringify({ abbrev, user_id }) });
    if (!res.ok) return setMsg({ ok: false, text: await readError(res) });
    const who = staff.find((s) => s.user_id === user_id)?.name ?? 'the selected account';
    setMsg({ ok: true, text: `${abbrev} is now mapped to ${who} for every timetable.` });
    load();
  };

  const entries = useMemo(() => {
    const all = d?.entries ?? [];
    return onlyProblems ? all.filter((e) => e.issues.length) : all;
  }, [d, onlyProblems]);

  if (!d) return <p className="text-sm text-slate-400">Loading…</p>;
  const draft = d.status === 'draft';
  const published = d.status === 'published';

  return (
    <div className="space-y-4">
      <button type="button" onClick={onBack} className="text-sm text-blue-400 hover:text-blue-300">← All timetables</button>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-100">
            {d.class_label ?? 'Class not identified'}{d.semester ? ` · Sem ${d.semester}` : ''} · version {d.version}
          </h2>
          <p className="text-[13px] text-slate-400">
            {d.source_filename} · read by {d.extraction_method === 'vision' ? 'AI from a photo/PDF (check carefully)' : d.extraction_method ?? '—'}
            {d.published_at ? ` · published ${formatDateTime(d.published_at)}${d.published_by ? ` by ${d.published_by}` : ''}` : ''}
          </p>
        </div>
        <Badge tone={STATUS[d.status].tone}>{STATUS[d.status].label}</Badge>
      </div>

      {msg && <p role="status" className={`text-[13px] ${msg.ok ? 'text-emerald-400' : 'text-rose-400'}`}>{msg.ok ? '✓ ' : '⚠ '}{msg.text}</p>}
      {d.status === 'extracting' && <p className="text-sm text-slate-300" role="status">Reading the file… this page refreshes by itself.</p>}
      {d.extraction_error && (
        <p className="text-[13px] text-amber-300" role="alert">{d.extraction_error}{draft ? ' You can add the lectures by hand below.' : ''}</p>
      )}
      {d.extraction_notes.length > 0 && (
        <ul className="text-[13px] text-amber-300 list-disc pl-5">{d.extraction_notes.map((n) => <li key={n}>{n}</li>)}</ul>
      )}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] items-start">
        {/* Source */}
        <section className="glass-panel p-3 space-y-2 xl:sticky xl:top-2" aria-label="Uploaded timetable">
          <p className="text-[13px] font-medium text-slate-300">Uploaded sheet</p>
          {sourceUrl?.type.startsWith('image/') ? (
            // eslint-disable-next-line @next/next/no-img-element -- authenticated blob URL, not an optimizable asset
            <a href={sourceUrl.url} target="_blank" rel="noreferrer"><img src={sourceUrl.url} alt={`Uploaded timetable ${d.source_filename}`} className="w-full rounded border border-slate-800" /></a>
          ) : sourceUrl?.type === 'application/pdf' ? (
            <iframe src={sourceUrl.url} title="Uploaded timetable PDF" className="w-full h-[32rem] rounded border border-slate-800" />
          ) : sourceUrl ? (
            <a href={sourceUrl.url} download={d.source_filename} className="text-sm text-blue-400 underline">Download {d.source_filename}</a>
          ) : (
            <p className="text-[13px] text-slate-500">Loading…</p>
          )}
          <p className="text-[12px] text-slate-500">Open the image in a new tab to zoom.</p>
        </section>

        <div className="space-y-4">
          {/* Header */}
          <section className="glass-panel p-4 space-y-2" aria-label="Class details">
            <p className="text-sm font-semibold text-slate-100">Class details</p>
            <div className="flex flex-wrap items-end gap-2">
              {([['year_label', 'Year (FE/SY/TY/LY)', 'w-24'], ['division', 'Division', 'w-24'], ['semester', 'Semester', 'w-20'],
                ['academic_term', 'Term', 'w-36']] as const).map(([k, label, w]) => (
                <label key={k} className="text-[12px] text-slate-400">{label}<br />
                  <input disabled={!draft} value={header[k] ?? ''} onChange={(e) => setHeader({ ...header, [k]: e.target.value })} className={`${field} ${w}`} />
                </label>
              ))}
              <label className="text-[12px] text-slate-400">Applies from<br />
                <input type="date" disabled={!draft} value={header.effective_from ?? ''} onChange={(e) => setHeader({ ...header, effective_from: e.target.value })} className={field} />
              </label>
              {draft && (
                <button type="button" className={secondary} onClick={() => call('', { method: 'PATCH', body: JSON.stringify({
                  ...header, effective_from: header.effective_from || null }) }, 'Class details saved.')}>Save details</button>
              )}
            </div>
            {!d.class_key && <p className="text-[13px] text-rose-400">Year and division are needed before publishing.</p>}
          </section>

          {/* Initials */}
          {draft && sugg.length > 0 && (
            <section className="glass-panel p-4 space-y-3" aria-label="Unrecognised initials">
              <div>
                <p className="text-sm font-semibold text-slate-100">Who are these initials? ({sugg.length})</p>
                <p className="text-[13px] text-slate-400">
                  Lectures are only added to a schedule after you confirm who the initials belong to. Suggestions come from
                  the sheet&apos;s legend and matching initials — check them; nothing is mapped automatically.
                </p>
              </div>
              <ul className="space-y-2">
                {sugg.map((s) => (
                  <li key={s.abbrev} className="flex flex-wrap items-center gap-2">
                    <span className="w-14 font-semibold text-slate-100">{s.abbrev}</span>
                    <span className="text-[13px] text-slate-400 min-w-[8rem]">teaches {s.subjects.join(', ') || '—'}</span>
                    <select value={pick[s.abbrev] ?? ''} onChange={(e) => setPick({ ...pick, [s.abbrev]: e.target.value })}
                      className={`${field} min-w-[14rem]`} aria-label={`Account for ${s.abbrev}`}>
                      <option value="">Choose a faculty account…</option>
                      {s.candidates.length > 0 && (
                        <optgroup label="Suggested">
                          {s.candidates.map((c) => <option key={c.user_id} value={c.user_id}>{c.name} — {c.reason}</option>)}
                        </optgroup>
                      )}
                      <optgroup label="All staff">
                        {staff.map((u) => <option key={u.user_id} value={u.user_id}>{u.name} ({u.email})</option>)}
                      </optgroup>
                    </select>
                    <button type="button" disabled={!pick[s.abbrev]} onClick={() => confirmAlias(s.abbrev)} className={primary}>Confirm</button>
                    {s.ambiguous && <span className="text-[12px] text-amber-300">Several possible matches — choose carefully.</span>}
                    {s.legend_names.length > 0 && <span className="text-[12px] text-slate-500 w-full pl-16">Legend: {s.legend_names.join(', ')}</span>}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Diff */}
          {d.diff && (
            <section className="glass-panel p-4 space-y-2" aria-label="Changes from the published version">
              <p className="text-sm font-semibold text-slate-100">Changes compared with published version {d.diff.published_version}</p>
              <p className="text-[13px] text-slate-400">
                {d.diff.added.length} added · {d.diff.removed.length} removed · {d.diff.changed.length} changed · {d.diff.unchanged} unchanged.
                Publishing replaces only this class&apos;s timetable; date changes on unchanged lectures are kept.
              </p>
              <ul className="text-[13px] space-y-0.5">
                {d.diff.added.map((e) => <li key={`a${e.id}`} className="text-emerald-400">+ Added: {entryLine(e)}</li>)}
                {d.diff.removed.map((e) => <li key={`r${e.id}`} className="text-rose-400">− Removed: {entryLine(e)}</li>)}
                {d.diff.changed.map((c) => <li key={`c${c.after.id}`} className="text-amber-300">~ Changed: {entryLine(c.before)} → {entryLine(c.after)}</li>)}
              </ul>
            </section>
          )}

          {/* Entries */}
          <section className="glass-panel overflow-hidden" aria-label="Timetable entries">
            <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 border-b border-white/[0.06]">
              <p className="text-sm font-semibold text-slate-100">
                Entries ({d.counts.entries}){draft && ` · ${d.counts.blocking} need fixing · ${d.counts.warnings} warnings`}
              </p>
              <div className="flex items-center gap-3">
                <label className="text-[13px] text-slate-300 flex items-center gap-1.5">
                  <input type="checkbox" checked={onlyProblems} onChange={(e) => setOnlyProblems(e.target.checked)} /> Only entries with problems
                </label>
                {draft && <button type="button" onClick={() => setEditing('new')} className={secondary}>+ Add entry</button>}
              </div>
            </div>
            {editing === 'new' && (
              <EntryEditor initial={{}} onCancel={() => setEditing(null)}
                onSave={async (f) => { const e = await call('/entries', { method: 'POST', body: JSON.stringify(f) }, 'Entry added.'); if (!e) setEditing(null); return e; }} />
            )}
            {entries.length === 0 ? (
              <p className="px-4 py-6 text-sm text-slate-400">{onlyProblems ? 'No problems left.' : 'No entries.'}</p>
            ) : (
              <ul className="divide-y divide-white/[0.05]">
                {entries.map((e) => (
                  <li key={e.id}>
                    <div className="px-4 py-2.5 flex flex-wrap items-start gap-x-4 gap-y-1">
                      <span className="w-32 text-sm text-slate-200 tabular-nums">
                        {e.day ?? <span className="text-rose-400">Day?</span>}<br />
                        <span className="text-slate-400">{e.start_time && e.end_time ? `${e.start_time}–${e.end_time}` : <span className="text-rose-400">Time?</span>}</span>
                      </span>
                      <span className="flex-1 min-w-[12rem]">
                        <span className="block text-sm text-slate-100">
                          {e.kind === 'lab' ? 'Lab: ' : e.kind === 'tutorial' ? 'Tutorial: ' : ''}{e.subject ?? <span className="text-rose-400">Subject?</span>}
                          {e.batch ? ` · batch ${e.batch}` : ''}{e.room ? ` · room ${e.room}` : ''}
                        </span>
                        <span className="block text-[13px] text-slate-400">
                          {e.faculty_abbrev ?? 'No initials'}{e.faculty_name ? ` → ${e.faculty_name}` : e.faculty_abbrev ? ' → not mapped yet' : ''}
                          {e.source_cell ? <span className="text-slate-500"> · sheet: “{e.source_cell}”</span> : null}
                          {e.edited ? <span className="text-slate-500"> · corrected</span> : null}
                        </span>
                        {e.issues.length > 0 && (
                          <span className="flex flex-wrap gap-1 mt-1">
                            {e.issues.map((i) => <Badge key={i.code} tone={i.blocking ? 'danger' : 'warning'}>{i.blocking ? 'Fix: ' : ''}{i.text}</Badge>)}
                          </span>
                        )}
                      </span>
                      <span className="flex gap-2">
                        {draft && <button type="button" onClick={() => setEditing(e.id)} className={secondary}>Edit</button>}
                        {draft && <button type="button" onClick={() => call(`/entries/${e.id}`, { method: 'DELETE' }, 'Entry removed.')} className={secondary} aria-label={`Delete ${entryLine(e)}`}>Delete</button>}
                        {published && <button type="button" onClick={() => setChanging(changing === e.id ? null : e.id)} className={secondary}>Change a date</button>}
                      </span>
                    </div>
                    {editing === e.id && (
                      <EntryEditor initial={e} onCancel={() => setEditing(null)}
                        onSave={async (f) => { const err = await call(`/entries/${e.id}`, { method: 'PATCH', body: JSON.stringify(f) }, 'Entry saved.'); if (!err) setEditing(null); return err; }} />
                    )}
                    {changing === e.id && <DateChangeForm entry={e} onDone={(text) => { setChanging(null); setMsg({ ok: true, text }); }} />}
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* Publish */}
          {(draft || d.status === 'failed') && (
            <section className="glass-panel p-4 space-y-3" aria-label="Publish">
              <p className="text-sm font-semibold text-slate-100">Publish</p>
              {draft && d.counts.blocking > 0 && (
                <p className="text-[13px] text-rose-400">Fix or delete the {d.counts.blocking} entr{d.counts.blocking === 1 ? 'y' : 'ies'} marked “Fix” first.</p>
              )}
              {draft && d.counts.warnings > 0 && (
                <label className="flex items-start gap-2 text-[13px] text-slate-300">
                  <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} className="mt-0.5" />
                  I have checked the {d.counts.warnings} entr{d.counts.warnings === 1 ? 'y' : 'ies'} with warnings against the sheet.
                </label>
              )}
              <div className="flex flex-wrap gap-2">
                {draft && (
                  <button type="button" className={primary} disabled={d.counts.blocking > 0 || !d.class_key || (d.counts.warnings > 0 && !ack)}
                    onClick={() => call('/publish', { method: 'POST', body: JSON.stringify({ acknowledge_warnings: ack }) },
                      'Published. The lectures now appear in each faculty member’s My Schedule, and they have been notified.')}>
                    Publish timetable
                  </button>
                )}
                <button type="button" className={secondary} onClick={() => call('/reextract', { method: 'POST' }, 'Reading the file again…')}>Read the file again</button>
                <button type="button" className={secondary} onClick={async () => { const e = await call('/discard', { method: 'POST' }, 'Draft discarded.'); if (!e) onBack(); }}>Discard draft</button>
              </div>
            </section>
          )}

          {d.legend.length > 0 && (
            <details className="glass-panel p-4 text-[13px] text-slate-300">
              <summary className="cursor-pointer font-medium text-slate-200">Legend as read from the sheet ({d.legend.length})</summary>
              <ul className="mt-2 space-y-0.5">{d.legend.map((l, i) => <li key={i}><strong>{l.code}</strong> — {l.subject} — {l.faculty}</li>)}</ul>
            </details>
          )}
        </div>
      </div>
    </div>
  );
}

// ── initials mappings ───────────────────────────────────────────────────────
function Initials() {
  const [aliases, setAliases] = useState<Alias[]>([]);
  const [staff, setStaff] = useState<Staff[]>([]);
  const [f, setF] = useState({ abbrev: '', user_id: '' });
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const load = useCallback(() => {
    apiFetch('/api/v1/timetables/aliases').then((r) => (r.ok ? r.json() : [])).then(setAliases).catch(() => {});
  }, []);
  useEffect(() => {
    load();
    apiFetch('/api/v1/timetables/staff').then((r) => (r.ok ? r.json() : [])).then(setStaff).catch(() => {});
  }, [load]);
  return (
    <div className="space-y-4">
      <form className="glass-panel p-4 flex flex-wrap items-end gap-2" onSubmit={async (e) => {
        e.preventDefault();
        const res = await apiFetch('/api/v1/timetables/aliases', { method: 'POST', body: JSON.stringify(f) });
        if (!res.ok) return setMsg({ ok: false, text: await readError(res) });
        setMsg({ ok: true, text: `${f.abbrev.toUpperCase()} mapped.` });
        setF({ abbrev: '', user_id: '' });
        load();
      }}>
        <label className="text-[12px] text-slate-400">Initials<br /><input required maxLength={4} value={f.abbrev} onChange={(e) => setF({ ...f, abbrev: e.target.value.toUpperCase() })} className={`${field} w-24`} /></label>
        <label className="text-[12px] text-slate-400">Faculty account<br />
          <select required value={f.user_id} onChange={(e) => setF({ ...f, user_id: e.target.value })} className={`${field} min-w-[16rem]`}>
            <option value="">Choose…</option>
            {staff.map((u) => <option key={u.user_id} value={u.user_id}>{u.name} ({u.email})</option>)}
          </select>
        </label>
        <button type="submit" className={primary}>Add mapping</button>
        {msg && <p role="status" className={`w-full text-[13px] ${msg.ok ? 'text-emerald-400' : 'text-rose-400'}`}>{msg.text}</p>}
      </form>
      <p className="text-[13px] text-slate-400">
        A mapping applies to every timetable. Removing or changing one affects drafts immediately; published timetables
        keep the accounts they were published with until the class is published again.
      </p>
      {aliases.length === 0 ? (
        <div className="glass-panel"><EmptyState title="No initials mapped yet" body="Map initials here or while reviewing an uploaded timetable." /></div>
      ) : (
        <ul className="glass-panel divide-y divide-white/[0.05]">
          {aliases.map((a) => (
            <li key={a.id} className="px-4 py-2.5 flex flex-wrap items-center justify-between gap-2">
              <span className="text-sm text-slate-100"><strong className="inline-block w-14">{a.abbrev}</strong>{a.name}</span>
              <span className="flex items-center gap-3 text-[12px] text-slate-500">
                confirmed by {a.verified_by ?? '—'} · {formatDate(a.created_at)}
                <button type="button" className={secondary} onClick={async () => {
                  const res = await apiFetch(`/api/v1/timetables/aliases/${a.id}`, { method: 'DELETE' });
                  if (res.ok) load();
                }}>Remove</button>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ── date changes (holidays, extra lectures, list) ───────────────────────────
function DateChanges() {
  const [changes, setChanges] = useState<Change[]>([]);
  const [staff, setStaff] = useState<Staff[]>([]);
  const [hol, setHol] = useState({ on_date: '', reason: '' });
  const [extra, setExtra] = useState({ faculty_user_id: '', on_date: '', start_time: '', end_time: '', subject: '', class_label: '', room: '', reason: '' });
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const load = useCallback(() => {
    apiFetch('/api/v1/schedule/exceptions?days=120').then((r) => (r.ok ? r.json() : [])).then(setChanges).catch(() => {});
  }, []);
  useEffect(() => {
    load();
    apiFetch('/api/v1/timetables/staff').then((r) => (r.ok ? r.json() : [])).then(setStaff).catch(() => {});
  }, [load]);
  const post = async (body: Record<string, unknown>, ok: string) => {
    const res = await apiFetch('/api/v1/schedule/exceptions', { method: 'POST', body: JSON.stringify(body) });
    if (!res.ok) { setMsg({ ok: false, text: await readError(res) }); return false; }
    setMsg({ ok: true, text: ok });
    load();
    return true;
  };
  return (
    <div className="space-y-4">
      <p className="text-[13px] text-slate-400">
        Changes apply to one date only; the weekly timetable stays as published. To cancel or move a single lecture,
        open the published timetable and use “Change a date”. Affected faculty are notified.
      </p>
      {msg && <p role="status" className={`text-[13px] ${msg.ok ? 'text-emerald-400' : 'text-rose-400'}`}>{msg.ok ? '✓ ' : '⚠ '}{msg.text}</p>}
      <form className="glass-panel p-4 flex flex-wrap items-end gap-2" aria-label="Declare a holiday" onSubmit={async (e) => {
        e.preventDefault();
        if (await post({ kind: 'holiday', on_date: hol.on_date, reason: hol.reason || null }, `No teaching on ${hol.on_date}.`)) setHol({ on_date: '', reason: '' });
      }}>
        <p className="w-full text-sm font-semibold text-slate-100">Holiday / no teaching</p>
        <label className="text-[12px] text-slate-400">Date<br /><input type="date" required value={hol.on_date} onChange={(e) => setHol({ ...hol, on_date: e.target.value })} className={field} /></label>
        <label className="text-[12px] text-slate-400 flex-1 min-w-[12rem]">Reason<br /><input value={hol.reason} onChange={(e) => setHol({ ...hol, reason: e.target.value })} className={`${field} w-full`} /></label>
        <button type="submit" className={primary}>Add holiday</button>
      </form>
      <form className="glass-panel p-4 flex flex-wrap items-end gap-2" aria-label="Schedule an extra lecture" onSubmit={async (e) => {
        e.preventDefault();
        if (await post({ kind: 'extra', ...extra, class_label: extra.class_label || null, room: extra.room || null, reason: extra.reason || null },
          `Extra lecture added on ${extra.on_date}.`)) setExtra({ faculty_user_id: '', on_date: '', start_time: '', end_time: '', subject: '', class_label: '', room: '', reason: '' });
      }}>
        <p className="w-full text-sm font-semibold text-slate-100">Extra / replacement lecture</p>
        <label className="text-[12px] text-slate-400">Faculty<br />
          <select required value={extra.faculty_user_id} onChange={(e) => setExtra({ ...extra, faculty_user_id: e.target.value })} className={`${field} min-w-[12rem]`}>
            <option value="">Choose…</option>
            {staff.map((u) => <option key={u.user_id} value={u.user_id}>{u.name}</option>)}
          </select>
        </label>
        <label className="text-[12px] text-slate-400">Date<br /><input type="date" required value={extra.on_date} onChange={(e) => setExtra({ ...extra, on_date: e.target.value })} className={field} /></label>
        <label className="text-[12px] text-slate-400">Start<br /><input type="time" required value={extra.start_time} onChange={(e) => setExtra({ ...extra, start_time: e.target.value })} className={field} /></label>
        <label className="text-[12px] text-slate-400">End<br /><input type="time" required value={extra.end_time} onChange={(e) => setExtra({ ...extra, end_time: e.target.value })} className={field} /></label>
        <label className="text-[12px] text-slate-400">Subject<br /><input required value={extra.subject} onChange={(e) => setExtra({ ...extra, subject: e.target.value })} className={`${field} w-24`} /></label>
        <label className="text-[12px] text-slate-400">Class<br /><input value={extra.class_label} onChange={(e) => setExtra({ ...extra, class_label: e.target.value })} placeholder="TY C3" className={`${field} w-24`} /></label>
        <label className="text-[12px] text-slate-400">Room<br /><input value={extra.room} onChange={(e) => setExtra({ ...extra, room: e.target.value })} className={`${field} w-20`} /></label>
        <button type="submit" className={primary}>Add lecture</button>
      </form>
      <section className="glass-panel overflow-hidden" aria-label="Upcoming date changes">
        <p className="px-4 py-3 text-sm font-semibold text-slate-100 border-b border-white/[0.06]">Upcoming date changes ({changes.length})</p>
        {changes.length === 0 ? <p className="px-4 py-4 text-sm text-slate-400">None.</p> : (
          <ul className="divide-y divide-white/[0.05]">
            {changes.map((c) => (
              <li key={c.id} className="px-4 py-2.5 flex flex-wrap items-center justify-between gap-2">
                <span className="text-sm text-slate-200">
                  <Badge tone={c.kind === 'cancelled' ? 'danger' : c.kind === 'holiday' ? 'success' : 'warning'}>{CHANGE_LABEL[c.kind] ?? c.kind}</Badge>{' '}
                  {formatDate(c.date)} · {[c.subject, c.class_label, c.start_time && `${c.start_time}${c.end_time ? `–${c.end_time}` : ''}`, c.room && `room ${c.room}`].filter(Boolean).join(' · ')}
                  {c.reason ? <span className="text-slate-400"> · {c.reason}</span> : null}
                </span>
                <button type="button" className={secondary} onClick={async () => {
                  const res = await apiFetch(`/api/v1/schedule/exceptions/${c.id}`, { method: 'DELETE' });
                  if (res.ok) { setMsg({ ok: true, text: 'Change withdrawn; the regular timetable applies.' }); load(); }
                }}>Withdraw</button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

export default function TimetablesPage() {
  const me = useMe();
  const [tab, setTab] = useState<'uploads' | 'initials' | 'changes'>('uploads');
  const [openId, setOpenId] = useState<string | null>(null);

  if (me && !isCoordinatorRole(me.role)) {
    return (
      <main className="p-4 sm:p-6 md:p-10 max-w-3xl mx-auto">
        <h1 className="text-xl md:text-2xl font-semibold text-slate-100">Timetables</h1>
        <p className="text-sm text-slate-400 mt-2">Timetables are uploaded and published by Committee Coordinators. Your lectures appear in My Work → My Schedule.</p>
      </main>
    );
  }

  return (
    <main className="p-4 sm:p-6 md:p-10 max-w-[90rem] mx-auto space-y-5">
      <div>
        <h1 className="text-xl md:text-2xl font-semibold text-slate-100 tracking-[-0.02em]">Timetables</h1>
        <p className="text-slate-400 text-sm mt-1">
          Upload class timetables, confirm who each set of initials belongs to, check the entries, and publish. Every
          faculty member&apos;s lectures from all classes are combined into their own schedule.
        </p>
      </div>
      {!openId && (
        <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Timetable sections">
          {([['uploads', 'Uploads'], ['initials', 'Faculty initials'], ['changes', 'Date changes']] as const).map(([k, label]) => (
            <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
              className={`px-3 py-1.5 rounded text-[13px] font-medium border cursor-pointer ${
                tab === k ? 'bg-blue-600/15 text-blue-300 border-blue-500/40' : 'text-slate-400 border-slate-800 hover:text-slate-200'}`}>
              {label}
            </button>
          ))}
        </div>
      )}
      {openId ? <Review id={openId} onBack={() => setOpenId(null)} />
        : tab === 'uploads' ? <Uploads onOpen={setOpenId} />
          : tab === 'initials' ? <Initials /> : <DateChanges />}
    </main>
  );
}
