import { apiFetch } from '@/lib/api';
import type { Tone } from '@/components/ui/Badge';

/** One dated occurrence from GET /api/v1/schedule/mine (recurring entry + date-specific changes). */
export interface Lecture {
  date: string; // YYYY-MM-DD (institution timezone)
  start_time: string | null; // HH:MM
  end_time: string | null;
  subject: string | null;
  room: string | null;
  class_label: string | null;
  kind: string; // lecture / lab / tutorial
  batch: string | null;
  status: 'scheduled' | 'cancelled' | 'rescheduled' | 'holiday' | 'extra';
  note: string | null;
  entry_id: string | null;
  exception_id: string | null;
  original?: { start_time: string; end_time: string; room: string | null };
  source: { import_id: string; filename: string; version: number } | null;
}

export interface ScheduleResponse {
  start: string;
  days: number;
  today: string;
  has_timetable: boolean;
  items: Lecture[];
}

/** An item from GET /api/v1/calendar (academic dates + the user's task deadlines). */
export interface CalendarItem {
  date: string;
  end: string | null;
  title: string;
  kind: string;
  department: string;
  source: 'calendar' | 'commitment';
  meeting?: string | null;
  commitment_id?: string;
  status?: string;
  days_left: number;
  urgency: 'overdue' | 'today' | 'soon' | 'upcoming';
}

// Status is always shown as text; colour only reinforces it.
export const LECTURE_STATUS: Record<Lecture['status'], { label: string; tone: Tone }> = {
  scheduled: { label: 'Scheduled', tone: 'neutral' },
  cancelled: { label: 'Cancelled', tone: 'danger' },
  rescheduled: { label: 'Rescheduled', tone: 'warning' },
  holiday: { label: 'Holiday · no class', tone: 'success' },
  extra: { label: 'Extra lecture', tone: 'accent' },
};

export const KIND_LABEL: Record<string, string> = { lecture: 'Lecture', lab: 'Lab', tutorial: 'Tutorial' };

export const CAL_KIND_LABEL: Record<string, string> = {
  commitment: 'Task deadline', exam: 'Exam', deadline: 'Deadline', holiday: 'Holiday', term: 'Term', event: 'Event',
};

/** YYYY-MM-DD for a local Date (no UTC shift). */
export function isoDay(d: Date): string {
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export function parseDay(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(y, m - 1, d);
}

export function addDays(iso: string, n: number): string {
  const d = parseDay(iso);
  d.setDate(d.getDate() + n);
  return isoDay(d);
}

/** Monday of the week containing ``iso``. */
export function weekStart(iso: string): string {
  const d = parseDay(iso);
  return addDays(iso, -((d.getDay() + 6) % 7));
}

export function dayHeading(iso: string, opts: Intl.DateTimeFormatOptions = { weekday: 'long', day: 'numeric', month: 'long' }): string {
  return parseDay(iso).toLocaleDateString('en-IN', opts);
}

export function timeRange(l: { start_time: string | null; end_time: string | null }): string {
  if (!l.start_time) return 'Time not set';
  return l.end_time ? `${l.start_time}–${l.end_time}` : l.start_time;
}

/** ``start`` null = today in the institution's timezone (decided by the server). */
export async function fetchSchedule(start: string | null, days: number): Promise<ScheduleResponse> {
  const res = await apiFetch(`/api/v1/schedule/mine?days=${days}${start ? `&start=${start}` : ''}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

/** Calendar items between start and start+days-1 (inclusive). The calendar API counts from today. */
export async function fetchCalendarRange(today: string, start: string, days: number): Promise<CalendarItem[]> {
  const end = addDays(start, days - 1);
  const horizon = Math.max(1, Math.round((parseDay(end).getTime() - parseDay(today).getTime()) / 86_400_000) + 1);
  if (end < today) return [];
  const res = await apiFetch(`/api/v1/calendar?days=${Math.min(366, horizon)}`);
  if (!res.ok) return [];
  const data: { items: CalendarItem[] } = await res.json();
  return data.items.filter((i) => {
    const last = i.end ?? i.date;
    return last >= start && i.date <= end && i.urgency !== 'overdue';
  });
}
