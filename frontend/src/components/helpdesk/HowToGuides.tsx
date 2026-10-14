'use client';
import React, { useEffect, useState } from 'react';
import { apiFetch } from '@/lib/api';

interface Guide {
  id: string;
  name: string;
  summary: string;
  owner_office: string | null;
  version: number;
}

/** Approved, student-facing procedures: the plain "what you need to do" summary only. */
export default function HowToGuides() {
  const [guides, setGuides] = useState<Guide[]>([]);
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    apiFetch('/api/v1/skills/student')
      .then((r) => (r.ok ? r.json() : []))
      .then(setGuides)
      .catch(() => {});
  }, []);

  if (!guides.length) return null;
  return (
    <section className="glass-panel p-5 space-y-3" aria-labelledby="guides-heading">
      <h2 id="guides-heading" className="text-sm font-semibold text-slate-200 uppercase tracking-wider">How-to guides</h2>
      <p className="text-[11px] text-slate-500">Procedures approved in this demonstration (synthetic content, not official DJSCE rules), written for students.</p>
      <ul className="space-y-1.5">
        {guides.map((g) => (
          <li key={g.id} className="rounded border border-slate-800">
            <button type="button" onClick={() => setOpen(open === g.id ? null : g.id)} aria-expanded={open === g.id}
              className="w-full text-left px-3 py-2 text-sm text-slate-100 hover:bg-slate-900/60 cursor-pointer">
              {g.name}
            </button>
            {open === g.id && (
              <div className="px-3 pb-3 text-xs text-slate-300 space-y-1">
                <p className="whitespace-pre-wrap">{g.summary}</p>
                <p className="text-[10px] text-slate-500">{g.owner_office ? `${g.owner_office} · ` : ''}version {g.version}</p>
              </div>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
