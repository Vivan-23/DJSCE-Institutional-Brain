import React from 'react';
import { formatDateTime } from '@/lib/format';
import { Badge, type Tone } from '@/components/ui/Badge';

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

const CATEGORY: Record<string, { label: string; tone: Tone }> = {
  risk: { label: 'Governance alert', tone: 'warning' },
  bottleneck: { label: 'Bottleneck', tone: 'danger' },
  opportunity: { label: 'Opportunity', tone: 'accent' },
  deadline: { label: 'Deadline', tone: 'warning' },
  info: { label: 'Notice', tone: 'neutral' },
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
  const cat = CATEGORY[catKey] ?? { label: insight.category || 'Notice', tone: 'neutral' as Tone };

  const actions = parseActions(insight.suggested_actions ?? '[]');
  const confidence = Math.round((insight.confidence_score ?? 0) * 100);

  return (
    <article className="group px-5 py-4 transition-colors hover:bg-white/[0.02]" aria-label={`Insight: ${insight.observation}`}>
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2 mb-1.5">
            <Badge tone={cat.tone}>{cat.label}</Badge>
            {insight.created_at && <span className="text-[0.75rem] text-slate-500">{formatDateTime(insight.created_at)}</span>}
            <span className="text-[0.75rem] text-slate-500">· {confidence}% confidence</span>
          </div>
          <h3 className="text-[0.875rem] font-medium text-slate-100 leading-snug">{insight.observation}</h3>
          {insight.impact_rationale && (
            <p className="mt-0.5 text-[0.8125rem] text-slate-400 leading-relaxed">{insight.impact_rationale}</p>
          )}
          {actions.length > 0 && (
            <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
              {actions.map((action, i) => (
                <li key={i} className="text-[0.75rem] text-slate-400 flex items-center gap-1.5">
                  <span className="w-1 h-1 rounded-full bg-slate-600" aria-hidden="true" />
                  {action}
                </li>
              ))}
            </ul>
          )}
        </div>
        {onDismiss && insight.id && (
          <button
            onClick={() => onDismiss(insight.id!)}
            className="shrink-0 text-[0.75rem] text-slate-500 hover:text-slate-200 px-2 py-1 rounded-md hover:bg-white/[0.05] transition-colors cursor-pointer lg:opacity-0 lg:group-hover:opacity-100 focus:opacity-100"
            aria-label="Dismiss insight"
          >
            Dismiss
          </button>
        )}
      </div>
    </article>
  );
}
