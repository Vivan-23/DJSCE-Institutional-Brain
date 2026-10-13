'use client';
import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import InsightCard, { type Insight } from '@/components/dashboard/InsightCard';
import { apiFetch } from '@/lib/api';
import { formatDate } from '@/lib/format';

interface MetricState {
  totalInsights: number;
  openCommitments: number;
  blockedCommitments: number;
  totalMeetings: number;
  totalProcedures: number;
}

interface RecentMeeting {
  id: string;
  title: string;
  occurred_at: string;
  summary: string | null;
}

interface RecentCommitment {
  id: string;
  description: string;
  assignee: string | null;
  status: string;
  due_date: string | null;
}

export default function Dashboard() {
  const [insights, setInsights] = useState<Insight[]>([]);
  const [recentMeetings, setRecentMeetings] = useState<RecentMeeting[]>([]);
  const [recentCommitments, setRecentCommitments] = useState<RecentCommitment[]>([]);
  const [metrics, setMetrics] = useState<MetricState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.allSettled([
      apiFetch('/api/v1/insights/').then((r) => (r.ok ? r.json() : [])),
      apiFetch('/api/v1/commitments').then((r) => (r.ok ? r.json() : [])),
      apiFetch('/api/v1/transcripts').then((r) => (r.ok ? r.json() : [])),
      apiFetch('/api/v1/skills').then((r) => (r.ok ? r.json() : [])),
    ])
      .then(([insightsRes, commitmentsRes, meetingsRes, skillsRes]) => {
        const insightsData: Insight[] = insightsRes.status === 'fulfilled' ? insightsRes.value : [];
        const commitmentsData: RecentCommitment[] = commitmentsRes.status === 'fulfilled' ? commitmentsRes.value : [];
        const meetingsData: RecentMeeting[] = meetingsRes.status === 'fulfilled' ? meetingsRes.value : [];
        const skillsData: unknown[] = skillsRes.status === 'fulfilled' ? skillsRes.value : [];

        setInsights(insightsData);
        setRecentMeetings(meetingsData.slice(0, 3));
        setRecentCommitments(commitmentsData.filter((c) => c.status !== 'done' && c.status !== 'dropped').slice(0, 4));

        const openCount = commitmentsData.filter((c) => c.status === 'open' || c.status === 'in_progress').length;
        const blockedCount = commitmentsData.filter((c) => c.status === 'blocked').length;

        setMetrics({
          totalInsights: insightsData.length,
          openCommitments: openCount,
          blockedCommitments: blockedCount,
          totalMeetings: meetingsData.length,
          totalProcedures: skillsData.length,
        });
        setLoading(false);
      })
      .catch(() => {
        setError('Could not reach backend services. Please ensure the API is running.');
        setLoading(false);
      });
  }, []);

  const handleDismiss = async (id: string) => {
    try {
      await apiFetch(`/api/v1/insights/${id}/dismiss`, { method: 'POST' });
      setInsights((prev) => prev.filter((i) => i.id !== id));
      setMetrics((prev) => prev ? { ...prev, totalInsights: Math.max(0, prev.totalInsights - 1) } : null);
    } catch {
      // non-critical
    }
  };

  return (
    <main className="p-6 md:p-10 max-w-7xl mx-auto space-y-8">
      {/* Header section */}
      <div>
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl md:text-3xl font-bold text-slate-100 tracking-tight">
              Institutional Governance Intelligence
            </h1>
            <p className="text-slate-400 text-sm mt-1">
              Connect institutional knowledge, decisions, procedures and follow-up responsibilities.
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Link
              href="/chat"
              className="px-3.5 py-2 text-xs font-semibold rounded bg-blue-600 hover:bg-blue-500 text-white transition-colors flex items-center gap-1.5 shadow-sm"
            >
              <span>Ask Assistant</span>
              <span aria-hidden="true">→</span>
            </Link>
          </div>
        </div>
      </div>

      {/* Real-time Genuine Metrics Strip */}
      {metrics !== null && (
        <section aria-label="Summary Metrics" className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="glass-panel p-4 flex flex-col justify-between">
            <span className="text-xs font-medium text-slate-400">Active Insights</span>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-2xl font-bold text-slate-100">{metrics.totalInsights}</span>
              <span className="text-[11px] text-slate-400">system flags</span>
            </div>
          </div>
          <div className="glass-panel p-4 flex flex-col justify-between">
            <span className="text-xs font-medium text-slate-400">Pending Commitments</span>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-2xl font-bold text-blue-400">{metrics.openCommitments}</span>
              {metrics.blockedCommitments > 0 && (
                <span className="text-[11px] text-rose-400 font-medium">({metrics.blockedCommitments} blocked)</span>
              )}
            </div>
          </div>
          <div className="glass-panel p-4 flex flex-col justify-between">
            <span className="text-xs font-medium text-slate-400">Committee Records</span>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-2xl font-bold text-slate-100">{metrics.totalMeetings}</span>
              <span className="text-[11px] text-slate-400">indexed</span>
            </div>
          </div>
          <div className="glass-panel p-4 flex flex-col justify-between">
            <span className="text-xs font-medium text-slate-400">Institutional Procedures</span>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-2xl font-bold text-emerald-400">{metrics.totalProcedures}</span>
              <span className="text-[11px] text-slate-400">SOPs</span>
            </div>
          </div>
        </section>
      )}

      {/* Main Content Grid: Insights + Activity Feeds */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column (2 cols): Actionable Governance Insights */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-slate-100 flex items-center gap-2">
              <span>Actionable Governance Insights</span>
              {insights.length > 0 && (
                <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-blue-500/20 text-blue-400 border border-blue-500/30">
                  {insights.length}
                </span>
              )}
            </h2>
          </div>

          {loading && (
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="glass-panel p-6 animate-pulse space-y-3">
                  <div className="h-3 w-20 bg-slate-800 rounded" />
                  <div className="h-5 w-3/4 bg-slate-800 rounded" />
                  <div className="h-4 w-full bg-slate-800/60 rounded" />
                </div>
              ))}
            </div>
          )}

          {!loading && error && (
            <div className="glass-panel p-6 text-center border-rose-900/40">
              <p className="text-rose-400 text-sm font-medium mb-1">Backend Connection Notice</p>
              <p className="text-slate-400 text-xs">{error}</p>
            </div>
          )}

          {!loading && !error && insights.length === 0 && (
            <div className="glass-panel p-8 text-center space-y-3">
              <div className="w-10 h-10 rounded-full bg-slate-800/80 border border-slate-700 flex items-center justify-center mx-auto text-slate-400 text-lg">
                ✓
              </div>
              <h3 className="text-sm font-medium text-slate-200">No Pending Bottlenecks or Governance Alerts</h3>
              <p className="text-xs text-slate-400 max-w-md mx-auto">
                All tracked committee commitments and institutional procedures are currently aligned. Ingest committee
                transcripts or documents to generate automated governance observations.
              </p>
              <div className="pt-2 flex justify-center gap-3">
                <Link
                  href="/meetings"
                  className="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 border border-slate-700 transition-colors"
                >
                  Upload Meeting Minutes
                </Link>
                <Link
                  href="/sources"
                  className="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 border border-slate-700 transition-colors"
                >
                  Ingest Documents
                </Link>
              </div>
            </div>
          )}

          <div className="space-y-4">
            {insights.map((insight) => (
              <InsightCard
                key={insight.id}
                insight={insight}
                onDismiss={handleDismiss}
              />
            ))}
          </div>
        </div>

        {/* Right Column (1 col): Recent Activity & Quick Navigation */}
        <div className="space-y-6">
          {/* Quick Navigation Panel */}
          <div className="glass-panel p-5 space-y-3">
            <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
              Workspaces &amp; Decision Tools
            </h3>
            <div className="grid grid-cols-1 gap-2 text-xs">
              <Link
                href="/chat"
                className="p-2.5 rounded bg-slate-900/80 hover:bg-slate-800/80 border border-slate-800 flex items-center justify-between group transition-colors"
              >
                <div>
                  <p className="font-medium text-slate-200 group-hover:text-blue-400 transition-colors">Institutional Assistant</p>
                  <p className="text-[11px] text-slate-400">Query decisions, syllabus &amp; records</p>
                </div>
                <span className="text-slate-500 group-hover:text-blue-400">→</span>
              </Link>
              <Link
                href="/meetings"
                className="p-2.5 rounded bg-slate-900/80 hover:bg-slate-800/80 border border-slate-800 flex items-center justify-between group transition-colors"
              >
                <div>
                  <p className="font-medium text-slate-200 group-hover:text-blue-400 transition-colors">Minutes &amp; Meetings</p>
                  <p className="text-[11px] text-slate-400">Upload &amp; extract action points</p>
                </div>
                <span className="text-slate-500 group-hover:text-blue-400">→</span>
              </Link>
              <Link
                href="/commitments"
                className="p-2.5 rounded bg-slate-900/80 hover:bg-slate-800/80 border border-slate-800 flex items-center justify-between group transition-colors"
              >
                <div>
                  <p className="font-medium text-slate-200 group-hover:text-blue-400 transition-colors">Action Commitments</p>
                  <p className="text-[11px] text-slate-400">Track assigned deliverables &amp; deadlines</p>
                </div>
                <span className="text-slate-500 group-hover:text-blue-400">→</span>
              </Link>
              <Link
                href="/skills"
                className="p-2.5 rounded bg-slate-900/80 hover:bg-slate-800/80 border border-slate-800 flex items-center justify-between group transition-colors"
              >
                <div>
                  <p className="font-medium text-slate-200 group-hover:text-blue-400 transition-colors">Institutional Procedures</p>
                  <p className="text-[11px] text-slate-400">Review synthesized SOPs</p>
                </div>
                <span className="text-slate-500 group-hover:text-blue-400">→</span>
              </Link>
            </div>
          </div>

          {/* Active Commitments Feed */}
          {recentCommitments.length > 0 && (
            <div className="glass-panel p-5 space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                  Upcoming Responsibilities
                </h3>
                <Link href="/commitments" className="text-[11px] text-blue-400 hover:underline">
                  View all
                </Link>
              </div>
              <div className="space-y-2.5">
                {recentCommitments.map((c) => (
                  <div key={c.id} className="p-2.5 rounded bg-slate-900/60 border border-slate-800/80 text-xs space-y-1">
                    <p className="font-medium text-slate-200 line-clamp-2">{c.description}</p>
                    <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1">
                      <span>{c.assignee || 'Unassigned'}</span>
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase ${
                        c.status === 'blocked' ? 'bg-rose-500/10 text-rose-400' :
                        c.status === 'in_progress' ? 'bg-amber-500/10 text-amber-400' :
                        'bg-blue-500/10 text-blue-400'
                      }`}>
                        {c.status}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Recent Indexed Committee Records */}
          {recentMeetings.length > 0 && (
            <div className="glass-panel p-5 space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                  Recent Committee Records
                </h3>
                <Link href="/meetings" className="text-[11px] text-blue-400 hover:underline">
                  View all
                </Link>
              </div>
              <div className="space-y-2.5">
                {recentMeetings.map((m) => (
                  <div key={m.id} className="p-2.5 rounded bg-slate-900/60 border border-slate-800/80 text-xs space-y-1">
                    <p className="font-medium text-slate-200 truncate">{m.title}</p>
                    {m.summary && (
                      <p className="text-[11px] text-slate-400 line-clamp-2">{m.summary}</p>
                    )}
                    <p className="text-[10px] text-slate-500 pt-0.5">
                      {formatDate(m.occurred_at)}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
