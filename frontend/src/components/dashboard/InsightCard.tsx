import React from 'react';

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

const CATEGORY_STYLES: Record<string, string> = {
  risk: 'text-warning border-warning/30 bg-warning/5',
  opportunity: 'text-primary border-primary/30 bg-primary/5',
  info: 'text-gray-400 border-gray-700 bg-gray-800/30',
};

function parseActions(raw: string): string[] {
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) return parsed.filter((a) => typeof a === 'string');
  } catch {
    // fallback: treat as a single action if parsing fails
    if (raw.trim()) return [raw.trim()];
  }
  return [];
}

export default function InsightCard({ insight, onDismiss }: Props) {
  const categoryStyle =
    CATEGORY_STYLES[insight.category?.toLowerCase()] ?? CATEGORY_STYLES.info;
  const actions = parseActions(insight.suggested_actions ?? '[]');
  const confidence = Math.round((insight.confidence_score ?? 0) * 100);

  return (
    <article
      className="glass-panel p-6 flex flex-col gap-3 transition-transform hover:-translate-y-0.5 hover:shadow-lg hover:shadow-primary/10"
      aria-label={`Insight: ${insight.observation}`}
    >
      {/* Header row */}
      <div className="flex justify-between items-start gap-4">
        <span
          className={`text-xs font-bold uppercase tracking-wider px-2 py-0.5 rounded border ${categoryStyle}`}
        >
          {insight.category ?? 'insight'}
        </span>
        <div className="flex items-center gap-3 shrink-0">
          <span className="text-xs text-gray-400">{confidence}% confidence</span>
          {onDismiss && insight.id && (
            <button
              onClick={() => onDismiss(insight.id!)}
              className="text-xs text-gray-600 hover:text-gray-300 transition-colors"
              aria-label="Dismiss insight"
            >
              Dismiss
            </button>
          )}
        </div>
      </div>

      {/* Observation */}
      <h3 className="text-base font-semibold text-white leading-snug">
        {insight.observation}
      </h3>

      {/* Why it matters */}
      <p className="text-sm text-gray-300">{insight.impact_rationale}</p>

      {/* Suggested actions */}
      {actions.length > 0 && (
        <div className="mt-2 pt-3 border-t border-gray-800">
          <h4 className="text-xs text-gray-500 uppercase tracking-wider mb-2">
            Suggested Actions
          </h4>
          <ul className="space-y-1">
            {actions.map((action, i) => (
              <li key={i} className="text-sm text-primary flex items-start gap-2">
                <span className="mt-0.5 shrink-0">→</span>
                <span>{action}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Timestamp */}
      {insight.created_at && (
        <p className="text-xs text-gray-600 mt-1">
          {new Date(insight.created_at).toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
          })}
        </p>
      )}
    </article>
  );
}
