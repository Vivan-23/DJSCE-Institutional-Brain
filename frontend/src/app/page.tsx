'use client';
import React, { useEffect, useState } from 'react';
import InsightCard, { type Insight } from '@/components/dashboard/InsightCard';
import { apiFetch } from '@/lib/api';

export default function Dashboard() {
  const [insights, setInsights] = useState<Insight[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch('/api/v1/insights/')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data: Insight[]) => {
        setInsights(data);
        setLoading(false);
      })
      .catch(() => {
        setError('Could not load insights. Check that the backend is running.');
        setLoading(false);
      });
  }, []);

  const handleDismiss = async (id: string) => {
    try {
      await apiFetch(`/api/v1/insights/${id}/dismiss`, { method: 'POST' });
      setInsights((prev) => prev.filter((i) => i.id !== id));
    } catch {
      // non-critical; silently ignore
    }
  };

  return (
    <main className="min-h-screen p-8 md:p-12 lg:p-16">
      <div className="max-w-3xl mx-auto">
        <h1 className="text-4xl font-bold mb-2 bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-primary">
          Company Brain
        </h1>
        <p className="text-gray-400 mb-10">Active Intelligence Feed</p>

        {loading && (
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="glass-panel p-6 animate-pulse">
                <div className="h-3 w-16 bg-gray-700 rounded mb-3" />
                <div className="h-5 w-3/4 bg-gray-800 rounded mb-2" />
                <div className="h-4 w-full bg-gray-800/60 rounded" />
              </div>
            ))}
          </div>
        )}

        {!loading && error && (
          <div className="glass-panel p-8 text-center">
            <p className="text-danger mb-2">Failed to load insights</p>
            <p className="text-gray-500 text-sm">{error}</p>
          </div>
        )}

        {!loading && !error && insights.length === 0 && (
          <div className="glass-panel p-10 text-center">
            <p className="text-gray-400 font-medium mb-2">No active insights</p>
            <p className="text-gray-600 text-sm">
              Upload documents in{' '}
              <a href="/sources" className="text-primary hover:underline">
                Data Sources
              </a>{' '}
              to start generating organizational intelligence.
            </p>
          </div>
        )}

        <div className="space-y-5">
          {insights.map((insight) => (
            <InsightCard
              key={insight.id}
              insight={insight}
              onDismiss={handleDismiss}
            />
          ))}
        </div>
      </div>
    </main>
  );
}
