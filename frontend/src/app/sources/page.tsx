'use client';
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { apiFetch } from '@/lib/api';
import { formatDate } from '@/lib/format';
import { useInstitution } from '@/lib/useInstitution';

type UploadStatus = 'idle' | 'uploading' | 'done' | 'error';

interface Doc {
  filename: string | null;
  visibility: 'internal' | 'public';
  department: string;
  passages: number;
  added_at: string | null;
}

const ACCESS = [
  { value: 'internal', title: 'Staff only', body: 'Faculty and staff can get answers from it.' },
  { value: 'public', title: 'Students too', body: 'Students can also get answers from it.' },
] as const;

export default function SourcesPage() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<UploadStatus>('idle');
  const [message, setMessage] = useState('');
  const [visibility, setVisibility] = useState<'internal' | 'public'>('internal');
  const [department, setDepartment] = useState('all');
  const [docs, setDocs] = useState<Doc[] | null>(null);
  const [filter, setFilter] = useState('');
  const { departments } = useInstitution();
  const deptName = (code: string) =>
    code === 'all' ? 'Whole college' : departments.find((d) => d.code === code)?.name ?? code;

  const loadDocs = useCallback(() => {
    apiFetch('/api/v1/ingest/documents')
      .then((r) => (r.ok ? r.json() : []))
      .then(setDocs)
      .catch(() => setDocs([]));
  }, []);
  useEffect(() => { loadDocs(); }, [loadDocs]);

  const handleUpload = async () => {
    if (!file) return;
    setStatus('uploading');
    setMessage('');
    const form = new FormData();
    form.append('file', file);
    form.append('visibility', visibility);
    form.append('department', department);
    try {
      const res = await apiFetch('/api/v1/ingest/file', { method: 'POST', body: form });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? `Upload failed (HTTP ${res.status})`);
      setStatus('done');
      setMessage(`${file.name} was added. It will be searchable in about a minute.`);
      setFile(null);
      if (fileRef.current) fileRef.current.value = '';
      // Processing runs in the background; refresh the list once it has had time to finish.
      setTimeout(loadDocs, 20_000);
    } catch (err: unknown) {
      setStatus('error');
      setMessage(err instanceof Error ? err.message : 'The upload did not work. Please try again.');
    }
  };

  const shown = (docs ?? []).filter((d) => !filter || (d.filename ?? '').toLowerCase().includes(filter.toLowerCase()));

  return (
    <main className="p-4 sm:p-6 md:p-10 max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl md:text-2xl font-semibold text-slate-100 tracking-[-0.02em]">Documents</h1>
        <p className="text-slate-400 text-sm mt-1">
          Circulars, syllabi, rules and committee notes. The assistant uses them to answer questions and shows which document an answer came from.
        </p>
      </div>

      {/* Add a document */}
      <section className="glass-panel p-5 sm:p-6 space-y-5" aria-labelledby="add-doc">
        <h2 id="add-doc" className="text-base font-semibold text-slate-100">Add a document</h2>

        <label
          htmlFor="doc-upload"
          className={`flex items-center justify-center w-full h-28 border-2 border-dashed rounded-lg cursor-pointer transition-colors ${
            file ? 'border-blue-500/70 bg-blue-600/[0.06]' : 'border-slate-700 hover:border-slate-500'
          }`}
        >
          <span className="text-center p-4">
            {file ? (
              <>
                <span className="block text-base font-medium text-slate-100">{file.name}</span>
                <span className="block text-sm text-slate-400 mt-1">{(file.size / 1024).toFixed(0)} KB · click to choose a different file</span>
              </>
            ) : (
              <>
                <span className="block text-base font-medium text-blue-400">Click to choose a file</span>
                <span className="block text-sm text-slate-400 mt-1">PDF, Word (.docx) or text file, up to 10 MB</span>
              </>
            )}
          </span>
          <input
            id="doc-upload"
            ref={fileRef}
            type="file"
            accept=".txt,.pdf,.docx"
            className="sr-only"
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null);
              setStatus('idle');
              setMessage('');
            }}
          />
        </label>

        <fieldset className="space-y-2">
          <legend className="text-sm font-medium text-slate-200 mb-2">Who can use it?</legend>
          <div className="grid sm:grid-cols-2 gap-2">
            {ACCESS.map((a) => (
              <label key={a.value}
                className={`flex gap-3 p-3 rounded-lg border cursor-pointer ${visibility === a.value ? 'border-blue-500 bg-blue-600/[0.08]' : 'border-slate-700 hover:border-slate-500'}`}>
                <input type="radio" name="visibility" className="mt-1" checked={visibility === a.value} onChange={() => setVisibility(a.value)} />
                <span>
                  <span className="block text-sm font-medium text-slate-100">{a.title}</span>
                  <span className="block text-[0.8125rem] text-slate-400">{a.body}</span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>

        {departments.length > 0 && (
          <label className="block space-y-1.5">
            <span className="block text-sm font-medium text-slate-200">Which department is it for?</span>
            <select
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 h-11 text-sm text-slate-100 focus:outline-none focus:border-blue-500"
            >
              <option value="all">Whole college (every department)</option>
              {departments.map((d) => <option key={d.code} value={d.code}>{d.name} only</option>)}
            </select>
          </label>
        )}

        <button
          onClick={handleUpload}
          disabled={!file || status === 'uploading'}
          className="px-5 h-11 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-base font-semibold disabled:opacity-40 cursor-pointer"
        >
          {status === 'uploading' ? 'Adding…' : 'Add document'}
        </button>

        {message && (
          <p role={status === 'error' ? 'alert' : 'status'}
            className={`p-3 rounded-lg text-sm border ${status === 'error' ? 'bg-rose-500/10 border-rose-500/30 text-rose-300' : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'}`}>
            {status === 'error' ? '⚠ ' : '✓ '}{message}
          </p>
        )}
      </section>

      {/* Already added */}
      <section className="glass-panel overflow-hidden" aria-labelledby="doc-list">
        <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 border-b border-white/[0.06]">
          <h2 id="doc-list" className="text-base font-semibold text-slate-100">
            Documents already added{docs ? ` (${docs.length})` : ''}
          </h2>
          {(docs?.length ?? 0) > 8 && (
            <input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Find by name…" aria-label="Find a document by name"
              className="bg-slate-900 border border-slate-700 rounded-lg px-3 h-9 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500" />
          )}
        </div>
        {docs === null ? (
          <p className="px-4 py-4 text-sm text-slate-400">Loading…</p>
        ) : shown.length === 0 ? (
          <p className="px-4 py-4 text-sm text-slate-400">{filter ? 'No document with that name.' : 'No documents yet. Add the first one above.'}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[0.75rem] uppercase tracking-wide text-slate-500 border-b border-white/[0.06]">
                  <th scope="col" className="px-4 py-2 font-medium">Name</th>
                  <th scope="col" className="px-2 py-2 font-medium">Who can use it</th>
                  <th scope="col" className="px-2 py-2 font-medium">Department</th>
                  <th scope="col" className="px-4 py-2 font-medium">Added</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.05]">
                {shown.map((d) => (
                  <tr key={`${d.filename}-${d.visibility}-${d.department}`}>
                    <td className="px-4 py-2 text-slate-100 break-all">{d.filename ?? 'Untitled'}</td>
                    <td className="px-2 py-2 text-slate-300 whitespace-nowrap">{d.visibility === 'public' ? 'Students too' : 'Staff only'}</td>
                    <td className="px-2 py-2 text-slate-300">{deptName(d.department)}</td>
                    <td className="px-4 py-2 text-slate-400 whitespace-nowrap">{d.added_at ? formatDate(d.added_at) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
