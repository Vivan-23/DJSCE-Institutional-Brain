'use client';
import { useEffect, useState } from 'react';
import { API_BASE } from '@/lib/api';

export interface Department {
  code: string;
  name: string;
}

export interface Institution {
  name: string;
  short_code: string;
  full_name: string;
  logo?: string | null;
  departments: Department[];
  /** Production turns these off (backend settings ALLOW_SELF_REGISTRATION / SHOW_DEMO_LOGINS). */
  allow_registration: boolean;
  show_demo_logins: boolean;
}

const DEFAULT: Institution = {
  name: 'DJSCE Institutional Brain',
  short_code: 'DJSCE',
  full_name: 'Dwarkadas J. Sanghvi College of Engineering',
  departments: [],
  allow_registration: false,
  show_demo_logins: false,
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
