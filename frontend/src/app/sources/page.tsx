'use client';
import React, { useRef, useState } from 'react';
import { getToken, API_BASE } from '@/lib/api';

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

  const handleUpload = async () => {
    if (!file) return;
    setStatus('uploading');
    setResult(null);
    setErrorMsg('');

    const form = new FormData();
    form.append('file', file);

    const token = getToken();
    try {
      const res = await fetch(`${API_BASE}/api/v1/ingest/file`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: form,
      });
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
    <main className="min-h-screen p-8 md:p-12">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-3xl font-bold mb-2 text-white">Data Sources</h1>
        <p className="text-gray-400 mb-8">
          Upload documents to ingest them into Company Brain. Supported formats:
          .txt, .pdf, .docx.
        </p>

        {/* File Upload */}
        <section className="glass-panel p-6 mb-6">
          <h2 className="text-lg font-semibold text-white mb-1">
            Upload Document
          </h2>
          <p className="text-sm text-gray-400 mb-4">
            Meeting notes, status reports, architecture docs — anything up to 10 MB.
            Entities (people &amp; projects) will be extracted and added to the
            relationship graph automatically.
          </p>

          <div className="space-y-3">
            <label
              htmlFor="doc-upload"
              className={`flex items-center justify-center w-full h-28 border-2 border-dashed rounded-lg cursor-pointer transition-colors ${
                file
                  ? 'border-primary/50 bg-primary/5'
                  : 'border-gray-700 hover:border-gray-600'
              }`}
            >
              <div className="text-center">
                {file ? (
                  <>
                    <p className="text-primary text-sm font-medium">{file.name}</p>
                    <p className="text-gray-500 text-xs mt-1">
                      {(file.size / 1024).toFixed(1)} KB — ready to upload
                    </p>
                  </>
                ) : (
                  <>
                    <p className="text-gray-400 text-sm">
                      Click to choose a file
                    </p>
                    <p className="text-gray-600 text-xs mt-1">
                      .txt · .pdf · .docx up to 10 MB
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

            <button
              onClick={handleUpload}
              disabled={!file || status === 'uploading'}
              className="w-full bg-primary text-white py-2.5 rounded-lg hover:bg-primary/80 transition-colors disabled:opacity-40 font-medium"
            >
              {status === 'uploading' ? 'Uploading…' : 'Upload & Ingest'}
            </button>
          </div>

          {/* Status messages */}
          {status === 'queued' && result && (
            <div className="mt-4 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-sm">
              <p className="font-medium">✓ {result.filename} queued successfully</p>
              <p className="text-xs mt-1 text-emerald-500/80">{result.message}</p>
              <p className="text-xs mt-0.5 text-emerald-600">Task ID: {result.task_id}</p>
            </div>
          )}
          {status === 'error' && (
            <div className="mt-4 p-3 rounded-lg bg-danger/10 border border-danger/30 text-danger text-sm">
              {errorMsg}
            </div>
          )}
        </section>

        {/* External integrations (placeholder — backend not wired) */}
        <section className="glass-panel p-6 mb-4 opacity-60">
          <div className="flex justify-between items-start">
            <div>
              <h2 className="text-lg font-semibold text-white mb-1">
                GitHub Integration
              </h2>
              <p className="text-sm text-gray-400">
                Sync commit history, PRs, and issues automatically.
              </p>
            </div>
            <span className="text-xs text-gray-600 border border-gray-700 rounded px-2 py-0.5">
              Coming soon
            </span>
          </div>
        </section>

        <section className="glass-panel p-6 opacity-60">
          <div className="flex justify-between items-start">
            <div>
              <h2 className="text-lg font-semibold text-white mb-1">
                Jira / Trello
              </h2>
              <p className="text-sm text-gray-400">
                Sync project boards and task dependencies.
              </p>
            </div>
            <span className="text-xs text-gray-600 border border-gray-700 rounded px-2 py-0.5">
              Coming soon
            </span>
          </div>
        </section>
      </div>
    </main>
  );
}
