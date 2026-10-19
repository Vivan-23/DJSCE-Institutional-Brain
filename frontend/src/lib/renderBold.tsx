import React from 'react';

// LLM text uses **bold** markdown; render just that, everything else stays plain text.
export function renderBold(text: string) {
  return text.split(/\*\*(.+?)\*\*/g).map((part, i) =>
    i % 2 ? <strong key={i} className="font-semibold text-slate-100">{part}</strong> : part,
  );
}
