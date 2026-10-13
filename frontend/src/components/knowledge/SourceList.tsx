'use client';
import React, { useState } from 'react';

/** One retrieved evidence excerpt, exactly as returned by the API (nothing inferred). */
export interface Source {
  ref: number;
  source_type: string | null;
  source_ref: string | null;
  visibility: 'public' | 'internal' | string;
  excerpt: string;
}

const TYPE_LABEL: Record<string, string> = {
  transcript: 'Meeting transcript',
  document: 'Document',
  checkin: 'Faculty check-in',
  followup: 'Follow-up reply',
};

/**
 * Collapsible list of the evidence an AI answer was grounded in. Kept visually
 * separate from the answer so retrieved text is never confused with AI wording.
 */
export default function SourceList({ sources, warnInternal = false }: { sources: Source[]; warnInternal?: boolean }) {
  const [open, setOpen] = useState(false);
  if (!sources?.length) {
    return <p className="mt-2 text-[10px] text-slate-500">No matching indexed sources were found for this answer.</p>;
  }
  const internal = sources.filter((s) => s.visibility !== 'public').length;

  return (
    <div className="mt-2.5 border-t border-slate-800 pt-2">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 hover:text-slate-200 cursor-pointer"
        aria-expanded={open}
      >
        {open ? '▾' : '▸'} {sources.length} source{sources.length === 1 ? '' : 's'}
        {internal > 0 && <span className="ml-1.5 text-amber-400/90">· {internal} internal</span>}
      </button>
      {warnInternal && internal > 0 && (
        <p className="mt-1 text-[10px] text-amber-300/90">
          This draft uses staff-only sources. Check nothing internal is disclosed before replying to a student.
        </p>
      )}
      {open && (
        <ol className="mt-2 space-y-2">
          {sources.map((s) => (
            <li key={s.ref} className="rounded border border-slate-800 bg-slate-950/60 p-2.5">
              <div className="flex flex-wrap items-center gap-1.5 text-[10px] text-slate-400 mb-1">
                <span className="font-mono text-blue-400">[{s.ref}]</span>
                <span>{TYPE_LABEL[s.source_type ?? ''] ?? s.source_type ?? 'Source'}</span>
                {s.source_ref && <span className="font-mono text-slate-500 truncate max-w-[16rem]">{s.source_ref}</span>}
                <span
                  className={`px-1.5 py-px rounded border ${
                    s.visibility === 'public'
                      ? 'border-emerald-500/30 text-emerald-300'
                      : 'border-amber-500/30 text-amber-300'
                  }`}
                >
                  {s.visibility === 'public' ? 'Public' : 'Internal'}
                </span>
              </div>
              <p className="text-[11px] text-slate-300 leading-relaxed whitespace-pre-wrap">{s.excerpt}</p>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
