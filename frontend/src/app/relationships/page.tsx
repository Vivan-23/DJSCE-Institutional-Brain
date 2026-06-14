import React from 'react';
import GraphCanvas from '@/components/graph/GraphCanvas';

export default function RelationshipsPage() {
  return (
    <main className="min-h-screen p-8 md:p-12">
      <div className="max-w-5xl mx-auto">
        <h1 className="text-3xl font-bold mb-2 text-white">
          Organizational Relationships
        </h1>
        <p className="text-gray-400 mb-8">
          Force-directed graph of employees, projects, and their connections —
          populated automatically as you ingest documents.
        </p>
        <GraphCanvas />
        <div className="mt-6 flex gap-6 text-sm text-gray-500">
          <span className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-blue-500 inline-block" />
            Employee
          </span>
          <span className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-emerald-500 inline-block" />
            Project
          </span>
        </div>
      </div>
    </main>
  );
}
