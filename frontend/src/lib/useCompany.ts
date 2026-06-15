'use client';
import { useEffect, useState } from 'react';
import { API_BASE } from '@/lib/api';

export interface Company {
  name: string;
  short_code: string;
}

// Branding comes from the backend (driven by company.yaml). Defaults keep the UI
// sensible before the fetch resolves or if the API is unreachable.
const DEFAULT: Company = { name: 'Company Brain', short_code: 'CB' };

export function useCompany(): Company {
  const [company, setCompany] = useState<Company>(DEFAULT);

  useEffect(() => {
    // State is only set inside the async callback (never synchronously in the
    // effect body), per the project's React 19 lint rule.
    fetch(`${API_BASE}/api/v1/company`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d) setCompany({ name: d.name ?? DEFAULT.name, short_code: d.short_code ?? DEFAULT.short_code });
      })
      .catch(() => {});
  }, []);

  return company;
}
