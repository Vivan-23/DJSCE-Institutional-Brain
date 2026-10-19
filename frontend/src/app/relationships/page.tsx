'use client';
import React, { useEffect, useState } from 'react';
import GraphCanvas from '@/components/graph/GraphCanvas';
import { apiFetch } from '@/lib/api';

interface GraphStats {
  employees: number;
  projects: number;
  meetings: number;
  documents: number;
  relationships: number;
}

export default function RelationshipsPage() {
  const [stats, setStats] = useState<GraphStats | null>(null);

  useEffect(() => {
    apiFetch('/api/v1/graph/stats')
      .then((r) => (r.ok ? r.json() : null))
      .then((data: GraphStats | null) => {
        if (data) setStats(data);
      })
      .catch(() => {});
  }, []);

  return (
    <main className="p-6 md:p-10 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl md:text-2xl font-semibold text-slate-100 tracking-[-0.02em]">
            Knowledge Graph
          </h1>
          <p className="text-slate-400 text-xs sm:text-sm mt-1">
            Who attended which meetings and which committees, departments and documents are connected, extracted automatically from meetings and documents. Filter by type, search, and click a node to focus on it.
          </p>
        </div>
        {stats && (
          <div className="flex items-center gap-3 bg-slate-900/80 border border-slate-800 rounded px-3 py-1.5 text-xs text-slate-400 shrink-0">
            <span><strong className="text-blue-400">{stats.employees}</strong> People</span>
            <span>·</span>
            <span><strong className="text-emerald-400">{stats.projects}</strong> Bodies</span>
            <span>·</span>
            <span><strong className="text-amber-400">{stats.meetings}</strong> Meetings</span>
            <span>·</span>
            <span><strong className="text-violet-400">{stats.documents}</strong> Documents</span>
            <span>·</span>
            <span><strong className="text-slate-200">{stats.relationships}</strong> Edges</span>
          </div>
        )}
      </div>

      {/* Canvas */}
      <GraphCanvas />

      {/* Honest Legend & Documentation Strip */}
      <div className="glass-panel p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 text-xs">
        <div className="flex flex-wrap items-center gap-6">
          <span className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-blue-500 inline-block shadow-xs shadow-blue-500/50" />
            <span className="text-slate-300 font-medium">People</span>
          </span>
          <span className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-emerald-500 inline-block shadow-xs shadow-emerald-500/50" />
            <span className="text-slate-300 font-medium">Committees, departments &amp; initiatives</span>
          </span>
          <span className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-amber-500 inline-block" />
            <span className="text-slate-300 font-medium">Meetings</span>
          </span>
          <span className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-violet-400 inline-block" />
            <span className="text-slate-300 font-medium">Documents</span>
          </span>
          <span className="flex items-center gap-2 text-slate-400">
            <span className="w-4 h-0.5 bg-indigo-500 inline-block" />
            <span>ATTENDED · MENTIONS</span>
          </span>
        </div>

        <p className="text-[12px] text-slate-400 max-w-sm sm:text-right">
          People attend meetings; documents and meetings mention the bodies they concern. Names come from meeting speakers and spaCy NER (people only with a title or roster match).
        </p>
      </div>
    </main>
  );
}
