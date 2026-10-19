'use client';
import React, { useRef, useState } from 'react';
import { apiFetch } from '@/lib/api';
import { useInstitution } from '@/lib/useInstitution';

type UploadStatus = 'idle' | 'uploading' | 'queued' | 'error';

interface UploadResult {
  filename: string;
  task_id: string;
  message: string;
}

export default function SourcesPage() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<UploadStatus>('idle');
  const [result, setResult] = useState<UploadResult | null>(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [visibility, setVisibility] = useState<'internal' | 'public'>('internal');
  const [department, setDepartment] = useState('all');
  const { departments } = useInstitution();

  const handleUpload = async () => {
    if (!file) return;
    setStatus('uploading');
    setResult(null);
    setErrorMsg('');

    const form = new FormData();
    form.append('file', file);
    form.append('visibility', visibility);
    form.append('department', department);

    try {
      const res = await apiFetch('/api/v1/ingest/file', { method: 'POST', body: form });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail ?? `Upload failed (HTTP ${res.status})`);
      }
      setResult(data);
      setStatus('queued');
      setFile(null);
      if (fileRef.current) fileRef.current.value = '';
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Upload failed');
      setStatus('error');
    }
  };

  return (
    <main className="p-4 sm:p-6 md:p-10 max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl md:text-2xl font-semibold text-slate-100 tracking-[-0.02em]">
          Documents
        </h1>
        <p className="text-slate-400 text-[13px] mt-1">
          Add circulars, syllabi, accreditation papers and committee notes so the assistant can cite them.
        </p>
      </div>

      {/* File Upload Panel */}
      <section className="glass-panel p-5 sm:p-6 space-y-4">
        <div>
          <h2 className="text-sm font-semibold text-slate-200 mb-1">
            Upload a document
          </h2>
          <p className="text-[12px] text-slate-500">
            The text is split into passages for search, and people and committees it names are added to the knowledge graph.
          </p>
        </div>

        <div className="space-y-3">
          <label
            htmlFor="doc-upload"
            className={`flex items-center justify-center w-full h-32 border border-dashed rounded-lg cursor-pointer transition-colors ${
              file
                ? 'border-blue-600/70 bg-blue-600/[0.06]'
                : 'border-white/[0.1] hover:border-white/[0.2] bg-white/[0.015]'
            }`}
          >
            <div className="text-center p-4">
              {file ? (
                <>
                  <p className="text-slate-100 text-[13px] font-medium">{file.name}</p>
                  <p className="text-slate-400 text-[12px] mt-1 font-mono">
                    {(file.size / 1024).toFixed(1)} KB · ready to upload
                  </p>
                </>
              ) : (
                <>
                  <p className="text-slate-300 text-[13px] font-medium">
                    Choose a file
                  </p>
                  <p className="text-slate-500 text-[12px] mt-1">
                    .txt, .pdf or .docx · up to 10 MB
                  </p>
                </>
              )}
            </div>
            <input
              id="doc-upload"
              ref={fileRef}
              type="file"
              accept=".txt,.pdf,.docx"
              className="sr-only"
              onChange={(e) => {
                setFile(e.target.files?.[0] ?? null);
                setStatus('idle');
                setResult(null);
                setErrorMsg('');
              }}
            />
          </label>

          <fieldset className="flex flex-wrap gap-x-5 gap-y-1.5 text-xs text-slate-300">
            <legend className="sr-only">Who can see this document</legend>
            <label className="flex items-center gap-1.5 cursor-pointer">
              <input
                type="radio"
                name="visibility"
                checked={visibility === 'internal'}
                onChange={() => setVisibility('internal')}
              />
              Internal — faculty &amp; staff only
            </label>
            <label className="flex items-center gap-1.5 cursor-pointer">
              <input
                type="radio"
                name="visibility"
                checked={visibility === 'public'}
                onChange={() => setVisibility('public')}
              />
              Public — students can get answers from it
            </label>
          </fieldset>

          {departments.length > 0 && (
            <label className="flex items-center gap-2 text-xs text-slate-300">
              Department
              <select
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
                className="flex-1 bg-slate-900 border border-slate-700/80 rounded-md px-2.5 py-1.5 text-xs text-slate-100 focus:outline-none focus:border-blue-500"
              >
                <option value="all">Institution-wide (every department)</option>
                {departments.map((d) => (
                  <option key={d.code} value={d.code}>
                    {d.name} only
                  </option>
                ))}
              </select>
            </label>
          )}

          <button
            onClick={handleUpload}
            disabled={!file || status === 'uploading'}
            className="bg-blue-600 hover:bg-blue-500 text-white h-9 px-4 rounded-md text-[13px] font-medium transition-colors disabled:opacity-40 cursor-pointer"
          >
            {status === 'uploading' ? 'Uploading…' : 'Upload and index'}
          </button>
        </div>

        {/* Status notification */}
        {status === 'queued' && result && (
          <div className="p-3.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs space-y-1">
            <p className="font-semibold">{result.filename} queued</p>
            <p className="text-emerald-400/80">{result.message}</p>
            <p className="text-[11px] text-slate-500 font-mono">Task ID: {result.task_id}</p>
          </div>
        )}
        {status === 'error' && (
          <div className="p-3.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs">
            {errorMsg}
          </div>
        )}
      </section>

      {/* Institutional Ingestion Pipeline Description */}
      <section className="glass-panel p-5 space-y-3">
        <h2 className="text-[13px] font-medium text-slate-200">
          What happens to an upload
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
          <div className="p-3 rounded-md bg-white/[0.02] border border-white/[0.06] space-y-1">
            <p className="font-medium text-slate-200">Record</p>
            <p className="text-slate-400 text-[12px]">PostgreSQL keeps each passage with its source file, visibility and department.</p>
          </div>
          <div className="p-3 rounded-md bg-white/[0.02] border border-white/[0.06] space-y-1">
            <p className="font-medium text-slate-200">Search</p>
            <p className="text-slate-400 text-[12px]">ChromaDB indexes the passages so the assistant can find and cite them.</p>
          </div>
          <div className="p-3 rounded-md bg-white/[0.02] border border-white/[0.06] space-y-1">
            <p className="font-medium text-slate-200">Graph</p>
            <p className="text-slate-400 text-[12px]">Neo4j links the people and committees the document mentions.</p>
          </div>
        </div>
      </section>
    </main>
  );
}
