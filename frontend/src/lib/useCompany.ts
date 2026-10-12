'use client';
import { useEffect, useState } from 'react';
import { API_BASE } from '@/lib/api';

export interface Company {
  name: string;
  short_code: string;
}

// Institutional branding fallback aligned with DJSCE Institutional Brain
const DEFAULT: Company = { name: 'DJSCE Institutional Brain', short_code: 'DJSCE' };

export function useCompany(): Company {
  const [company, setCompany] = useState<Company>(DEFAULT);

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/company`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d) setCompany({ name: d.name ?? DEFAULT.name, short_code: d.short_code ?? DEFAULT.short_code });
      })
      .catch(() => {});
  }, []);

  return company;
}
