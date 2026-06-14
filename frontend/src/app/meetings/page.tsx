'use client';
import React, { useCallback, useEffect, useState } from 'react';
import { apiFetch } from '@/lib/api';

type SubmitStatus = 'idle' | 'submitting' | 'queued' | 'error';

interface MeetingSummary {
  id: string;
  title: string;
  occurred_at: string;
  summary: string | null;
  source: string;
}

interface MeetingDetail extends MeetingSummary {
  participants: string[];
  raw_transcript: string;
}

interface QueueResult {
  title: string;
  task_id: string;
  message: string;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function MeetingsPage() {
  const [title, setTitle] = useState('');
  const [transcript, setTranscript] = useState('');
  const [status, setStatus] = useState<SubmitStatus>('idle');
  const [result, setResult] = useState<QueueResult | null>(null);
  const [errorMsg, setErrorMsg] = useState('');

  const [meetings, setMeetings] = useState<MeetingSummary[]>([]);
  const [loadingList, setLoadingList] = useState(true);
  const [listError, setListError] = useState('');

  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<MeetingDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // State is only set inside the async callbacks (never synchronously in the
  // effect body) so the spinner toggle lives in the callers that need it.
  const loadMeetings = useCallback(() => {
    apiFetch('/api/v1/transcripts')
      .then((r) => {
        if (!r.ok) throw new Error(`Failed to load meetings (HTTP ${r.status})`);
        return r.json();
      })
      .then((data: MeetingSummary[]) => {
        setMeetings(data);
        setListError('');
        setLoadingList(false);
      })
      .catch((err: unknown) => {
        setListError(err instanceof Error ? err.message : 'Failed to load meetings');
        setLoadingList(false);
      });
  }, []);

  useEffect(() => {
    loadMeetings();
  }, [loadMeetings]);

  const refreshMeetings = () => {
    setLoadingList(true);
    loadMeetings();
  };

  const handleSubmit = async () => {
    if (!title.trim() || !transcript.trim()) return;
    setStatus('submitting');
    setResult(null);
    setErrorMsg('');
    try {
      const res = await apiFetch('/api/v1/transcripts', {
        method: 'POST',
        body: JSON.stringify({
          title: title.trim(),
          transcript,
          source: 'upload',
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail ?? `Submission failed (HTTP ${res.status})`);
      }
      setResult(data);
      setStatus('queued');
      setTitle('');
      setTranscript('');
      // Give the worker a moment, then refresh the list.
      setTimeout(refreshMeetings, 1500);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Submission failed');
      setStatus('error');
    }
  };

  const toggleExpand = async (id: string) => {
    if (expandedId === id) {
      setExpandedId(null);
      setDetail(null);
      return;
    }
    setExpandedId(id);
    setDetail(null);
    setLoadingDetail(true);
    try {
      const res = await apiFetch(`/api/v1/transcripts/${id}`);
      if (!res.ok) throw new Error(`Failed to load meeting (HTTP ${res.status})`);
      setDetail((await res.json()) as MeetingDetail);
    } catch {
      setDetail(null);
    } finally {
      setLoadingDetail(false);
    }
  };

  const canSubmit =
    title.trim().length > 0 && transcript.trim().length > 0 && status !== 'submitting';

  return (
    <main className="min-h-screen p-8 md:p-12">
      <div className="max-w-3xl mx-auto">
        <h1 className="text-3xl font-bold mb-2 text-white">Meetings</h1>
        <p className="text-gray-400 mb-8">
          Paste a meeting transcript to capture it. Company Brain extracts a
          summary, participants, decisions, and action items automatically.
        </p>

        {/* Submit transcript */}
        <section className="glass-panel p-6 mb-8">
          <h2 className="text-lg font-semibold text-white mb-4">
            Add a Transcript
          </h2>

          <div className="space-y-4">
            <div>
              <label
                htmlFor="meeting-title"
                className="block text-sm text-gray-400 mb-1.5"
              >
                Title
              </label>
              <input
                id="meeting-title"
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Q3 Planning Sync"
                className="w-full bg-black/40 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-primary/60"
              />
            </div>

            <div>
              <label
                htmlFor="meeting-transcript"
                className="block text-sm text-gray-400 mb-1.5"
              >
                Transcript
              </label>
              <textarea
                id="meeting-transcript"
                value={transcript}
                onChange={(e) => setTranscript(e.target.value)}
                placeholder="Paste the full meeting transcript here…"
                rows={10}
                className="w-full bg-black/40 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-primary/60 font-mono resize-y"
              />
              <p className="text-xs text-gray-600 mt-1">
                {transcript.length.toLocaleString()} characters
              </p>
            </div>

            <button
              onClick={handleSubmit}
              disabled={!canSubmit}
              className="w-full bg-primary text-white py-2.5 rounded-lg hover:bg-primary/80 transition-colors disabled:opacity-40 font-medium"
            >
              {status === 'submitting' ? 'Submitting…' : 'Process Transcript'}
            </button>
          </div>

          {status === 'queued' && result && (
            <div className="mt-4 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-sm">
              <p className="font-medium">✓ {result.title} queued</p>
              <p className="text-xs mt-1 text-emerald-500/80">{result.message}</p>
              <p className="text-xs mt-0.5 text-emerald-600">
                Task ID: {result.task_id}
              </p>
            </div>
          )}
          {status === 'error' && (
            <div className="mt-4 p-3 rounded-lg bg-danger/10 border border-danger/30 text-danger text-sm">
              {errorMsg}
            </div>
          )}
        </section>

        {/* Ingested meetings */}
        <section>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white">
              Ingested Meetings
            </h2>
            <button
              onClick={refreshMeetings}
              className="text-xs text-gray-500 hover:text-primary transition-colors"
            >
              Refresh
            </button>
          </div>

          {loadingList ? (
            <p className="text-gray-500 text-sm">Loading meetings…</p>
          ) : listError ? (
            <div className="p-3 rounded-lg bg-danger/10 border border-danger/30 text-danger text-sm">
              {listError}
            </div>
          ) : meetings.length === 0 ? (
            <div className="glass-panel p-6 text-center text-gray-500 text-sm">
              No meetings yet. Add a transcript above to get started.
            </div>
          ) : (
            <ul className="space-y-3">
              {meetings.map((m) => {
                const open = expandedId === m.id;
                return (
                  <li key={m.id} className="glass-panel overflow-hidden">
                    <button
                      onClick={() => void toggleExpand(m.id)}
                      className="w-full text-left p-4 hover:bg-gray-900/40 transition-colors"
                      aria-expanded={open}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0">
                          <p className="text-white font-medium truncate">
                            {m.title}
                          </p>
                          <p className="text-xs text-gray-500 mt-0.5">
                            {formatDate(m.occurred_at)} · {m.source}
                          </p>
                          {m.summary && (
                            <p className="text-sm text-gray-400 mt-2 line-clamp-2">
                              {m.summary}
                            </p>
                          )}
                        </div>
                        <span
                          className={`text-gray-600 text-lg leading-none transition-transform ${
                            open ? 'rotate-180' : ''
                          }`}
                          aria-hidden
                        >
                          ⌄
                        </span>
                      </div>
                    </button>

                    {open && (
                      <div className="border-t border-gray-800 p-4 space-y-4">
                        {loadingDetail ? (
                          <p className="text-gray-500 text-sm">Loading details…</p>
                        ) : detail && detail.id === m.id ? (
                          <>
                            {detail.summary && (
                              <div>
                                <h3 className="text-xs uppercase tracking-wide text-gray-500 mb-1">
                                  Summary
                                </h3>
                                <p className="text-sm text-gray-300 whitespace-pre-wrap">
                                  {detail.summary}
                                </p>
                              </div>
                            )}

                            {detail.participants.length > 0 && (
                              <div>
                                <h3 className="text-xs uppercase tracking-wide text-gray-500 mb-1.5">
                                  Participants
                                </h3>
                                <div className="flex flex-wrap gap-2">
                                  {detail.participants.map((p) => (
                                    <span
                                      key={p}
                                      className="text-xs px-2 py-0.5 rounded-full bg-primary/10 border border-primary/20 text-primary"
                                    >
                                      {p}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            )}

                            <details className="group">
                              <summary className="text-xs uppercase tracking-wide text-gray-500 cursor-pointer hover:text-gray-400 select-none">
                                Raw transcript
                              </summary>
                              <pre className="mt-2 text-xs text-gray-400 whitespace-pre-wrap font-mono max-h-72 overflow-y-auto bg-black/40 rounded-lg p-3 border border-gray-800">
                                {detail.raw_transcript}
                              </pre>
                            </details>
                          </>
                        ) : (
                          <p className="text-gray-500 text-sm">
                            Couldn’t load details.
                          </p>
                        )}
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      </div>
    </main>
  );
}
