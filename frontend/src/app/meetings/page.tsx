'use client';
import React, { useCallback, useEffect, useState } from 'react';
import { apiFetch } from '@/lib/api';
import { formatDateTime } from '@/lib/format';

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

const SAMPLE_TEMPLATES = [
  {
    name: 'Academic Council (Elective Review)',
    title: 'Academic Council: Autonomous Elective Curriculum Review',
    text: `[DEMONSTRATION PROTOTYPE · SYNTHETIC INSTITUTIONAL RECORD]
Academic Council Meeting: Autonomous Elective Curriculum Review
Date: October 4, 2026
Attendees: Dr. Aditi Rao, Dr. Rohan Mehta, Prof. Neha Iyer, Prof. Karan Shah

Dr. Aditi Rao: Welcome everyone. Today we are reviewing the proposed elective on Applied Generative AI and Machine Learning for the final-year B.Tech autonomous curriculum.
Dr. Rohan Mehta: The syllabus has 3 lecture hours and 2 laboratory practical hours per week.
Prof. Neha Iyer: From an IQAC and accreditation perspective, we need mapped Course Outcomes (COs) aligned with Program Outcomes (POs).
Dr. Aditi Rao: Decision: The elective syllabus is cleared for Board of Studies external review with a cap of 60 students per batch.
Dr. Aditi Rao: Decision: Cloud API compute allocation of Rs 75,000 is approved under department computing budget.
Prof. Karan Shah: I will compile the finalized elective syllabus and CO-PO mapping matrix by Friday.
Dr. Rohan Mehta: I will schedule the external Board of Studies ratification review meeting by next Monday.
Prof. Neha Iyer: I will prepare the accreditation compliance checklist and prerequisite evaluation report by Wednesday.`,
  },
  {
    name: 'IQAC Quality Audit',
    title: 'Internal Quality Assurance Cell: Academic Quality & Feedback Audit',
    text: `[DEMONSTRATION PROTOTYPE · SYNTHETIC INSTITUTIONAL RECORD]
Internal Quality Assurance Cell (IQAC): Academic Quality & Feedback Audit
Date: October 6, 2026
Attendees: Dr. Aditi Rao, Prof. Neha Iyer, Dr. Rohan Mehta, Prof. Pooja Verma

Prof. Neha Iyer: Student feedback analytics show average course satisfaction at 87%, but three laboratory subjects flagged delays in assignment grading.
Dr. Aditi Rao: Decision: All laboratory rubrics and continuous evaluation marks must be posted within 7 working days of experiment completion.
Prof. Neha Iyer: Decision: Unified mini-project rubrics developed by the IQAC committee are hereby adopted for all autonomous semester batches.
Prof. Pooja Verma: I will update the laboratory continuous assessment rubrics and share the grading guidelines with all lab in-charges by Thursday.
Prof. Neha Iyer: I will publish the consolidated student feedback report and action-taken recommendations by next Tuesday.
Dr. Rohan Mehta: I will follow up with the remaining faculty on missing course file attainment sheets by end of week.`,
  },
];

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

  const handleSelectSample = (sample: typeof SAMPLE_TEMPLATES[0]) => {
    setTitle(sample.title);
    setTranscript(sample.text);
    setStatus('idle');
    setResult(null);
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
          source: 'demo_institutional',
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
      setTimeout(refreshMeetings, 2500);
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
    <main className="p-6 md:p-10 max-w-4xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl md:text-3xl font-bold text-slate-100 tracking-tight">
          Minutes &amp; Committee Meetings
        </h1>
        <p className="text-slate-400 text-xs sm:text-sm mt-1">
          Record, summarize, and extract actionable institutional decisions and commitments from Academic Council, IQAC, Departmental, and Exam Committee meetings.
        </p>
      </div>

      {/* Submission Form */}
      <section className="glass-panel p-5 sm:p-6 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-slate-800 pb-3">
          <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wider">
            Record Minutes of Meeting (MoM)
          </h2>
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-[11px] text-slate-500 font-medium mr-1">Load Demo Scenario:</span>
            {SAMPLE_TEMPLATES.map((sample, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => handleSelectSample(sample)}
                className="px-2 py-1 rounded bg-slate-900 hover:bg-slate-800 text-[11px] text-blue-400 border border-slate-800 hover:border-slate-700 transition-colors cursor-pointer"
              >
                {sample.name}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-4">
          <div>
            <label
              htmlFor="meeting-title"
              className="block text-xs font-medium text-slate-300 mb-1"
            >
              Committee / Meeting Title
            </label>
            <input
              id="meeting-title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Academic Council: Autonomous Curriculum Scrutiny"
              className="w-full bg-slate-900/90 border border-slate-700/80 rounded-lg px-3.5 py-2 text-xs sm:text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div>
            <label
              htmlFor="meeting-transcript"
              className="block text-xs font-medium text-slate-300 mb-1"
            >
              Meeting Transcript or Minutes Text
            </label>
            <textarea
              id="meeting-transcript"
              value={transcript}
              onChange={(e) => setTranscript(e.target.value)}
              placeholder="Paste dialogue turns (e.g. 'Dr. Aditi Rao: Decision: ...') or committee minutes here…"
              rows={8}
              className="w-full bg-slate-900/90 border border-slate-700/80 rounded-lg px-3.5 py-2 text-xs sm:text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 font-mono resize-y"
            />
            <p className="text-[11px] text-slate-400 mt-1">
              {transcript.length.toLocaleString()} characters · The intelligence engine automatically parses speakers, decisions, and actionable commitments with owners and due dates.
            </p>
          </div>

          <button
            onClick={handleSubmit}
            disabled={!canSubmit}
            className="w-full bg-blue-600 hover:bg-blue-500 text-white py-2.5 rounded-lg transition-colors disabled:opacity-40 font-semibold text-xs sm:text-sm cursor-pointer shadow-sm"
          >
            {status === 'submitting' ? 'Submitting to Queue…' : 'Extract Institutional Decisions & Action Items'}
          </button>
        </div>

        {status === 'queued' && result && (
          <div className="p-3.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs space-y-1">
            <p className="font-semibold">✓ {result.title} queued for institutional extraction</p>
            <p className="text-emerald-500/80">{result.message}</p>
          </div>
        )}
        {status === 'error' && (
          <div className="p-3.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs">
            {errorMsg}
          </div>
        )}
      </section>

      {/* Ingested Meetings List */}
      <section className="space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-2">
          <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wider">
            Indexed Committee Proceedings ({meetings.length})
          </h2>
          <button
            onClick={refreshMeetings}
            className="text-xs text-blue-400 hover:underline cursor-pointer"
          >
            Refresh records
          </button>
        </div>

        {loadingList ? (
          <div className="space-y-3">
            {[1, 2].map((i) => (
              <div key={i} className="glass-panel p-4 animate-pulse h-16 bg-slate-900/60 rounded" />
            ))}
          </div>
        ) : listError ? (
          <div className="p-4 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs">
            {listError}
          </div>
        ) : meetings.length === 0 ? (
          <div className="glass-panel p-8 text-center text-slate-400 text-xs">
            No institutional meetings recorded yet. Use the form above or run the institutional ingestion script.
          </div>
        ) : (
          <ul className="space-y-3">
            {meetings.map((m) => {
              const open = expandedId === m.id;
              return (
                <li key={m.id} className="glass-panel overflow-hidden">
                  <button
                    onClick={() => void toggleExpand(m.id)}
                    className="w-full text-left p-4 hover:bg-slate-900/50 transition-colors cursor-pointer"
                    aria-expanded={open}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <p className="text-slate-100 font-semibold text-sm truncate">
                          {m.title}
                        </p>
                        <p className="text-[11px] text-slate-400 mt-0.5">
                          Conducted: {formatDateTime(m.occurred_at)} · Source: {m.source}
                        </p>
                        {m.summary && (
                          <p className="text-xs text-slate-300 mt-2 line-clamp-2 leading-relaxed">
                            {m.summary}
                          </p>
                        )}
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
                    <div className="border-t border-slate-800/80 p-4 space-y-4 bg-slate-950/40">
                      {loadingDetail ? (
                        <p className="text-slate-400 text-xs">Retrieving meeting details…</p>
                      ) : detail && detail.id === m.id ? (
                        <>
                          {detail.summary && (
                            <div>
                              <h3 className="text-[11px] uppercase tracking-wider font-semibold text-slate-400 mb-1">
                                Executive Summary
                              </h3>
                              <p className="text-xs sm:text-sm text-slate-200 whitespace-pre-wrap leading-relaxed">
                                {detail.summary}
                              </p>
                            </div>
                          )}

                          {detail.participants.length > 0 && (
                            <div>
                              <h3 className="text-[11px] uppercase tracking-wider font-semibold text-slate-400 mb-1.5">
                                Verified Attendees &amp; Committee Members
                              </h3>
                              <div className="flex flex-wrap gap-1.5">
                                {detail.participants.map((p) => (
                                  <span
                                    key={p}
                                    className="text-xs px-2.5 py-0.5 rounded-full bg-blue-500/15 border border-blue-500/30 text-blue-300"
                                  >
                                    {p}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}

                          <details className="group pt-1">
                            <summary className="text-[11px] uppercase tracking-wider text-slate-400 cursor-pointer hover:text-slate-300 select-none font-semibold">
                              View Raw Minutes / Transcript
                            </summary>
                            <pre className="mt-2 text-xs text-slate-400 whitespace-pre-wrap font-mono max-h-72 overflow-y-auto bg-slate-900/90 rounded p-3 border border-slate-800 leading-relaxed">
                              {detail.raw_transcript}
                            </pre>
                          </details>
                        </>
                      ) : (
                        <p className="text-slate-400 text-xs">Could not load proceedings details.</p>
                      )}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </main>
  );
}
