import type { Institution } from '@/lib/useInstitution';

/** The institution's logo (institution.yaml `logo`) on a white tile, or its short code as a text badge. */
export default function InstitutionMark({ institution, size }: { institution: Institution; size: 'sm' | 'lg' }) {
  const box = size === 'lg' ? 'w-24 h-20 rounded-xl p-1.5' : 'w-10 h-9 rounded-md p-0.5';
  if (institution.logo) {
    return (
      <div className={`${box} bg-white flex items-center justify-center shrink-0`}>
        {/* eslint-disable-next-line @next/next/no-img-element -- small static asset whose path comes from config */}
        <img src={institution.logo} alt={`${institution.full_name} logo`} className="max-w-full max-h-full object-contain" />
      </div>
    );
  }
  return (
    <div className={`${size === 'lg' ? 'w-11 h-11 rounded-xl' : 'w-6 h-6 rounded-md'} bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center shrink-0`}>
      <span className={`text-white font-semibold ${size === 'lg' ? 'text-[0.6875rem]' : 'text-[8px]'}`}>{institution.short_code}</span>
    </div>
  );
}
