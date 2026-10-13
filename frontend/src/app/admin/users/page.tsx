'use client';
import React, { useCallback, useEffect, useState } from 'react';
import { apiFetch } from '@/lib/api';
import { ROLE_LABEL, type Role, useMe } from '@/lib/roles';
import { useInstitution } from '@/lib/useInstitution';

interface AdminUser {
  id: string;
  email: string;
  full_name: string | null;
  role: Role;
  department: string | null;
  year: number | null;
  semester: number | null;
  division: string | null;
  is_active: boolean;
}

interface Permission {
  capability: string;
  roles: Role[];
}

const ROLES: Role[] = ['student', 'employee', 'manager', 'admin'];
const EMPTY = { email: '', full_name: '', role: 'student' as Role, department: '', year: '', semester: '', division: '', password: '' };
const field =
  'bg-slate-900 border border-slate-700/80 rounded px-2 py-1 text-xs text-slate-100 focus:outline-none focus:border-blue-500';

async function call(path: string, init?: RequestInit): Promise<{ ok: boolean; data: Record<string, unknown> }> {
  const res = await apiFetch(path, init);
  const data = await res.json().catch(() => ({}));
  return { ok: res.ok, data };
}

/** Empty strings → null and numeric strings → numbers, as the API expects. */
function payload(form: Record<string, string>) {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(form)) {
    if (v === '') out[k] = k === 'password' ? undefined : null;
    else out[k] = k === 'year' || k === 'semester' ? Number(v) : v;
  }
  return out;
}

export default function AdminUsersPage() {
  const me = useMe();
  const { departments } = useInstitution();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [filters, setFilters] = useState({ q: '', role: '', department: '' });
  const [form, setForm] = useState(EMPTY);
  const [editing, setEditing] = useState<string | null>(null);
  const [edit, setEdit] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(() => {
    const qs = new URLSearchParams(Object.entries(filters).filter(([, v]) => v)).toString();
    apiFetch(`/api/v1/admin/users${qs ? `?${qs}` : ''}`)
      .then((r) => {
        if (!r.ok) throw new Error(r.status === 403 ? 'User management is available to system administrators.' : `HTTP ${r.status}`);
        return r.json();
      })
      .then((d: AdminUser[]) => {
        setUsers(d);
        setError('');
      })
      .catch((e: Error) => setError(e.message));
  }, [filters]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    apiFetch('/api/v1/admin/roles')
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => d && setPermissions(d.permissions))
      .catch(() => {});
  }, []);

  const report = (ok: boolean, data: Record<string, unknown>, success: string) => {
    if (ok) {
      setNotice(success);
      setError('');
      load();
    } else {
      setError(String(data.detail ?? 'Request failed'));
      setNotice('');
    }
  };

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    const { ok, data } = await call('/api/v1/admin/users', { method: 'POST', body: JSON.stringify(payload(form)) });
    const pw = data.temporary_password ? ` Temporary password (shown once): ${data.temporary_password}` : '';
    report(ok, data, `Created ${form.email}.${pw}`);
    if (ok) setForm(EMPTY);
  };

  const startEdit = (u: AdminUser) => {
    setEditing(u.id);
    setEdit({
      full_name: u.full_name ?? '', role: u.role, department: u.department ?? '',
      year: u.year?.toString() ?? '', semester: u.semester?.toString() ?? '', division: u.division ?? '',
    });
  };

  const save = async (u: AdminUser) => {
    const { ok, data } = await call(`/api/v1/admin/users/${u.id}`, { method: 'PATCH', body: JSON.stringify(payload(edit)) });
    report(ok, data, `Saved ${u.email}.`);
    if (ok) setEditing(null);
  };

  const toggleActive = async (u: AdminUser) => {
    const { ok, data } = await call(`/api/v1/admin/users/${u.id}`, {
      method: 'PATCH', body: JSON.stringify({ is_active: !u.is_active }),
    });
    report(ok, data, `${u.email} ${u.is_active ? 'deactivated' : 'reactivated'}.`);
  };

  const resetPassword = async (u: AdminUser) => {
    const { ok, data } = await call(`/api/v1/admin/users/${u.id}/reset-password`, { method: 'POST', body: '{}' });
    report(ok, data, `New temporary password for ${u.email} (shown once): ${data.temporary_password}`);
  };

  const importCsv = async (file: File) => {
    const body = new FormData();
    body.append('file', file);
    const { ok, data } = await call('/api/v1/admin/users/import', { method: 'POST', body });
    if (!ok) return report(ok, data, '');
    const created = (data.created as { email: string; temporary_password: string | null }[]) ?? [];
    const errors = (data.errors as { line: number; error: string }[]) ?? [];
    const pw = created.filter((c) => c.temporary_password).map((c) => `${c.email}: ${c.temporary_password}`);
    report(true, data,
      `Imported ${created.length}, skipped ${(data.skipped as string[]).length} existing, ${errors.length} errors.` +
        (errors.length ? ` ${errors.map((e) => `line ${e.line}: ${e.error}`).join('; ')}.` : '') +
        (pw.length ? ` Temporary passwords (shown once): ${pw.join(', ')}` : ''));
  };

  const deptSelect = (value: string, onChange: (v: string) => void) => (
    <select value={value} onChange={(e) => onChange(e.target.value)} className={field} aria-label="Department">
      <option value="">No department</option>
      {departments.map((d) => (
        <option key={d.code} value={d.code}>{d.code}</option>
      ))}
    </select>
  );

  return (
    <main className="p-4 sm:p-6 md:p-10 max-w-7xl mx-auto space-y-5">
      <div>
        <h1 className="text-2xl md:text-3xl font-bold text-slate-100 tracking-tight">Users</h1>
        <p className="text-slate-400 text-xs sm:text-sm mt-1">
          Create accounts, change roles and departments, deactivate accounts and reset passwords. Every change is audited.
        </p>
      </div>

      {notice && <p role="status" className="text-emerald-300 text-xs break-words">{notice}</p>}
      {error && <p role="alert" className="text-rose-400 text-xs">{error}</p>}

      <section className="glass-panel p-4 space-y-3" aria-label="Add user">
        <h2 className="text-sm font-semibold text-slate-100">Add a user</h2>
        <form onSubmit={create} className="flex flex-wrap gap-2 items-center">
          <input required type="email" placeholder="Email" value={form.email} className={field}
            onChange={(e) => setForm({ ...form, email: e.target.value })} aria-label="Email" />
          <input placeholder="Full name" value={form.full_name} className={field}
            onChange={(e) => setForm({ ...form, full_name: e.target.value })} aria-label="Full name" />
          <select value={form.role} className={field} aria-label="Role"
            onChange={(e) => setForm({ ...form, role: e.target.value as Role })}>
            {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
          </select>
          {deptSelect(form.department, (v) => setForm({ ...form, department: v }))}
          {form.role === 'student' && (
            <>
              <input placeholder="Year 1-4" value={form.year} className={`${field} w-20`} inputMode="numeric"
                onChange={(e) => setForm({ ...form, year: e.target.value })} aria-label="Year" />
              <input placeholder="Sem 1-8" value={form.semester} className={`${field} w-20`} inputMode="numeric"
                onChange={(e) => setForm({ ...form, semester: e.target.value })} aria-label="Semester" />
              <input placeholder="Div" value={form.division} className={`${field} w-16`}
                onChange={(e) => setForm({ ...form, division: e.target.value })} aria-label="Division" />
            </>
          )}
          <input type="password" placeholder="Password (blank = generate)" value={form.password} className={field}
            onChange={(e) => setForm({ ...form, password: e.target.value })} aria-label="Password" />
          <button type="submit" className="px-3 py-1 rounded bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold cursor-pointer">
            Add user
          </button>
        </form>
        <label className="block text-[11px] text-slate-400">
          Or import a CSV (columns: email, full_name, role, department, year, semester, division, password):{' '}
          <input type="file" accept=".csv,text/csv" className="text-xs"
            onChange={(e) => e.target.files?.[0] && importCsv(e.target.files[0])} />
        </label>
      </section>

      <div className="flex flex-wrap gap-2 items-center" aria-label="Filters">
        <input placeholder="Search name or email" value={filters.q} className={field}
          onChange={(e) => setFilters({ ...filters, q: e.target.value })} aria-label="Search" />
        <select value={filters.role} className={field} aria-label="Filter by role"
          onChange={(e) => setFilters({ ...filters, role: e.target.value })}>
          <option value="">All roles</option>
          {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
        </select>
        {deptSelect(filters.department, (v) => setFilters({ ...filters, department: v }))}
        <span className="text-[11px] text-slate-500">{users.length} users</span>
      </div>

      <div className="glass-panel overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="text-slate-400 text-left">
            <tr>
              {['Name / email', 'Role', 'Dept', 'Year', 'Sem', 'Div', 'Status', ''].map((h) => (
                <th key={h} className="p-2 font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="text-slate-200">
            {users.map((u) => {
              const isMe = me?.id === u.id;
              const on = editing === u.id;
              return (
                <tr key={u.id} className={`border-t border-slate-800/80 ${u.is_active ? '' : 'opacity-50'}`}>
                  <td className="p-2">
                    {on ? (
                      <input value={edit.full_name} className={field} aria-label="Full name"
                        onChange={(e) => setEdit({ ...edit, full_name: e.target.value })} />
                    ) : (
                      <span className="font-medium">{u.full_name ?? '—'}</span>
                    )}
                    <span className="block text-slate-500">{u.email}{isMe ? ' (you)' : ''}</span>
                  </td>
                  <td className="p-2">
                    {on ? (
                      <select value={edit.role} className={field} aria-label="Role"
                        onChange={(e) => setEdit({ ...edit, role: e.target.value })}>
                        {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
                      </select>
                    ) : ROLE_LABEL[u.role]}
                  </td>
                  <td className="p-2">{on ? deptSelect(edit.department, (v) => setEdit({ ...edit, department: v })) : u.department ?? '—'}</td>
                  {(['year', 'semester', 'division'] as const).map((k) => (
                    <td key={k} className="p-2">
                      {on ? (
                        <input value={edit[k]} className={`${field} w-14`} aria-label={k}
                          onChange={(e) => setEdit({ ...edit, [k]: e.target.value })} />
                      ) : u[k] ?? '—'}
                    </td>
                  ))}
                  <td className="p-2">{u.is_active ? 'Active' : 'Deactivated'}</td>
                  <td className="p-2 whitespace-nowrap space-x-1.5 text-right">
                    {on ? (
                      <>
                        <button onClick={() => save(u)} className="text-emerald-300 hover:underline cursor-pointer">Save</button>
                        <button onClick={() => setEditing(null)} className="text-slate-400 hover:underline cursor-pointer">Cancel</button>
                      </>
                    ) : (
                      <>
                        <button onClick={() => startEdit(u)} className="text-blue-300 hover:underline cursor-pointer">Edit</button>
                        <button onClick={() => resetPassword(u)} className="text-slate-300 hover:underline cursor-pointer">Reset password</button>
                        {!isMe && (
                          <button onClick={() => toggleActive(u)} className="text-rose-300 hover:underline cursor-pointer">
                            {u.is_active ? 'Deactivate' : 'Reactivate'}
                          </button>
                        )}
                      </>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {permissions.length > 0 && (
        <section className="glass-panel p-4 space-y-2" aria-label="Role permissions">
          <h2 className="text-sm font-semibold text-slate-100">What each role can do</h2>
          <p className="text-[11px] text-slate-500">Fixed in the application and enforced by the server. Assign a role to change what a user can do.</p>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="text-slate-400 text-left">
                <tr>
                  <th className="p-1.5 font-medium">Capability</th>
                  {ROLES.map((r) => <th key={r} className="p-1.5 font-medium text-center">{ROLE_LABEL[r]}</th>)}
                </tr>
              </thead>
              <tbody className="text-slate-200">
                {permissions.map((p) => (
                  <tr key={p.capability} className="border-t border-slate-800/80">
                    <td className="p-1.5">{p.capability}</td>
                    {ROLES.map((r) => (
                      <td key={r} className="p-1.5 text-center">{p.roles.includes(r) ? '✓' : '—'}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </main>
  );
}
