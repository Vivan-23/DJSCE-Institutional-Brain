import React from 'react';
import { formatDateTime } from '@/lib/format';

export interface Insight {
  id?: string;
  category: string;
  observation: string;
  impact_rationale: string;
  /** JSON-encoded string: '["action 1", "action 2"]' */
  suggested_actions: string;
  confidence_score: number;
  is_dismissed?: boolean;
  created_at?: string;
}

interface Props {
  insight: Insight;
  onDismiss?: (id: string) => void;
}

const CATEGORY_STYLES: Record<string, { label: string; style: string }> = {
  risk: { label: 'Governance Alert', style: 'text-amber-400 border-amber-500/30 bg-amber-500/10' },
  bottleneck: { label: 'Workflow Bottleneck', style: 'text-rose-400 border-rose-500/30 bg-rose-500/10' },
  opportunity: { label: 'Academic Opportunity', style: 'text-blue-400 border-blue-500/30 bg-blue-500/10' },
  info: { label: 'Institutional Notice', style: 'text-slate-300 border-slate-700 bg-slate-800/40' },
};

function parseActions(raw: string): string[] {
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) return parsed.filter((a) => typeof a === 'string');
  } catch {
    if (raw.trim()) return [raw.trim()];
  }
  return [];
}

export default function InsightCard({ insight, onDismiss }: Props) {
  const catKey = insight.category?.toLowerCase() || 'info';
  const badgeConfig = CATEGORY_STYLES[catKey] ?? {
    label: insight.category || 'Institutional Notice',
    style: CATEGORY_STYLES.info.style,
  };

  const actions = parseActions(insight.suggested_actions ?? '[]');
  const confidence = Math.round((insight.confidence_score ?? 0) * 100);

  return (
    <article
      className="glass-panel p-5 sm:p-6 flex flex-col gap-3 transition-colors hover:border-slate-700/80"
      aria-label={`Governance Insight: ${insight.observation}`}
    >
      {/* Header row */}
      <div className="flex justify-between items-start gap-4">
        <span
          className={`text-[12px] font-semibold px-2 py-0.5 rounded border ${badgeConfig.style}`}
        >
          {badgeConfig.label}
        </span>
        <div className="flex items-center gap-3 shrink-0">
          <span className="text-xs text-slate-400 font-mono">{confidence}% confidence</span>
          {onDismiss && insight.id && (
            <button
              onClick={() => onDismiss(insight.id!)}
              className="text-xs text-slate-400 hover:text-slate-200 transition-colors cursor-pointer px-1 py-0.5"
              aria-label="Dismiss insight"
            >
              Dismiss
            </button>
          )}
        </div>
      </div>

      {/* Observation */}
      <h3 className="text-sm sm:text-base font-semibold text-slate-100 leading-snug">
        {insight.observation}
      </h3>

      {/* Institutional Impact */}
      <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">{insight.impact_rationale}</p>

      {/* Suggested institutional actions */}
      {actions.length > 0 && (
        <div className="mt-1 pt-3 border-t border-slate-800/80">
          <h4 className="text-[12px] font-semibold text-slate-400 mb-2">
            Recommended Follow-Up Steps
          </h4>
          <ul className="space-y-1.5">
            {actions.map((action, i) => (
              <li key={i} className="text-xs text-blue-300 flex items-start gap-2">
                <span className="mt-0.5 text-blue-400 shrink-0">→</span>
                <span>{action}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Timestamp */}
      {insight.created_at && (
        <p className="text-[12px] text-slate-400 mt-0.5">
          Observed on{' '}
          {formatDateTime(insight.created_at)}
        </p>
      )}
    </article>
  );
}
