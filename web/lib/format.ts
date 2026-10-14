import type { Status } from './api';

export const nf = new Intl.NumberFormat('en-IN');
export const rank = (n: number | null | undefined) => (n == null ? '–' : nf.format(n));
export const num = (n: number | null | undefined, digits = 0) =>
  n == null ? '–' : n.toLocaleString('en-IN', { maximumFractionDigits: digits });
export const pct = (x: number) => `${Math.round(x * 100)}%`;

/** Colour + label per classification, used by chips, charts and legends. */
export const STATUS_META: Record<Status, { label: string; short: string; color: string; chip: string; help: string }> = {
  safe: { label: 'Safe', short: 'Safe', color: '#16a34a', chip: 'bg-green-50 text-green-700 ring-1 ring-green-200',
    help: 'First considered round closed far behind your rank.' },
  good: { label: 'Good chance', short: 'Good', color: '#65a30d', chip: 'bg-lime-50 text-lime-700 ring-1 ring-lime-200',
    help: 'Comfortable margin in the first considered round.' },
  borderline: { label: 'Borderline', short: 'Border', color: '#f59e0b', chip: 'bg-amber-50 text-amber-700 ring-1 ring-amber-200',
    help: 'Closed around your rank – may or may not come.' },
  later_round: { label: 'Later-round opportunity', short: 'Later', color: '#7c3aed', chip: 'bg-violet-50 text-violet-700 ring-1 ring-violet-200',
    help: 'Out of reach in the first round, but a later round reached ranks like yours.' },
  reach: { label: 'Reach', short: 'Reach', color: '#0ea5e9', chip: 'bg-sky-50 text-sky-700 ring-1 ring-sky-200',
    help: 'Closed somewhat ahead of your rank – low chance, worth listing high.' },
  unlikely: { label: 'Unlikely', short: 'Unlikely', color: '#94a3b8', chip: 'bg-slate-100 text-slate-600 ring-1 ring-slate-200',
    help: 'Closed well ahead of your rank.' },
};

export const CATEGORY_LABEL: Record<string, string> = {
  GEN: 'General', GEN_PWD: 'General (PwD)', OBC: 'OBC-NCL', OBC_PWD: 'OBC-NCL (PwD)', SC: 'SC', SC_PWD: 'SC (PwD)',
  ST: 'ST', ST_PWD: 'ST (PwD)', EWS: 'EWS', EWS_PWD: 'EWS (PwD)',
  OPEN: 'Open', OPEN_PWD: 'Open (PwD)',
};
export const catLabel = (code: string) => CATEGORY_LABEL[code] ?? code;

/** Build a querystring from the current params plus patches (used by links that change one filter). */
export function withParams(current: URLSearchParams | Record<string, string | undefined>, patch: Record<string, string | number | undefined | null>) {
  const sp = current instanceof URLSearchParams ? new URLSearchParams(current) : new URLSearchParams(
    Object.entries(current).filter(([, v]) => v != null) as [string, string][]);
  for (const [k, v] of Object.entries(patch)) {
    if (v === undefined || v === null || v === '') sp.delete(k);
    else sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : '';
}

export const first = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v);
/** Accepts repeated params (?b=X&b=Y) and comma lists (?b=X,Y). */
export const list = (v: string | string[] | undefined): string[] | undefined => {
  const raw = Array.isArray(v) ? v : v ? [v] : [];
  const parts = raw.flatMap((s) => s.split(',')).map((x) => x.trim()).filter(Boolean);
  return parts.length ? Array.from(new Set(parts)) : undefined;
};
export const int = (v: string | string[] | undefined, fallback?: number) => {
  const n = Number(first(v));
  return Number.isFinite(n) ? Math.trunc(n) : fallback;
};
