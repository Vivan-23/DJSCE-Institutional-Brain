'use client';
import { useEffect, useState } from 'react';
import { API_BASE } from '@/lib/api';

export interface Institution {
  name: string;
  short_code: string;
  full_name: string;
}

const DEFAULT: Institution = {
  name: 'DJSCE Institutional Brain',
  short_code: 'DJSCE',
  full_name: 'Dwarkadas J. Sanghvi College of Engineering',
};

/** Public branding from institution.yaml (served unauthenticated, so plain fetch). */
export function useInstitution(): Institution {
  const [institution, setInstitution] = useState<Institution>(DEFAULT);

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/institution`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d) setInstitution({ ...DEFAULT, ...d });
      })
      .catch(() => {});
  }, []);

  return institution;
}
