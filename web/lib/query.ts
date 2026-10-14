/** Parse the dashboard URL into a predictor request. The URL is the only state, so results are shareable. */
import type { PredictBody, Sort, Status, Thresholds } from './api';
import { ACHIEVABLE, SORTS, STATUS_ORDER } from './api';
import { first, int, list } from './format';

export type SearchParams = Record<string, string | string[] | undefined>;

export const DEFAULT_THRESHOLDS: Thresholds = { safe: 1.5, good: 1.15, borderline: 0.95, reach: 0.75 };
export const PAGE_SIZE = 25;

export type Query = {
  submitted: boolean;              // false on first visit -> show the form, no results
  body: PredictBody;
  statuses: Status[];
  sort: Sort;
  limit: number;
  offset: number;
  thresholdsChanged: boolean;
};

const numParam = (v: string | string[] | undefined, fallback: number) => {
  const n = Number(first(v));
  return Number.isFinite(n) && n > 0 ? n : fallback;
};

export function parseQuery(sp: SearchParams): Query {
  const rank = int(sp.rank);
  const category = first(sp.category);
  const submitted = Boolean(rank && category);
  const statuses = (list(sp.statuses)?.filter((s): s is Status => (STATUS_ORDER as string[]).includes(s))
    ?? ACHIEVABLE.concat('reach')) as Status[];
  const thresholds: Thresholds = {
    safe: numParam(sp.t_safe, DEFAULT_THRESHOLDS.safe),
    good: numParam(sp.t_good, DEFAULT_THRESHOLDS.good),
    borderline: numParam(sp.t_borderline, DEFAULT_THRESHOLDS.borderline),
    reach: numParam(sp.t_reach, DEFAULT_THRESHOLDS.reach),
  };
  const rawSort = first(sp.sort) === 'closing_rank' ? 'closing_rank_desc' : first(sp.sort);   // legacy alias
  const sort: Sort = SORTS.includes(rawSort as Sort) ? (rawSort as Sort) : 'desirability';
  const limit = Math.min(200, Math.max(5, int(sp.limit, PAGE_SIZE)!));
  const offset = Math.max(0, int(sp.offset, 0)!);
  return {
    submitted,
    statuses,
    sort,
    limit,
    offset,
    thresholdsChanged: JSON.stringify(thresholds) !== JSON.stringify(DEFAULT_THRESHOLDS),
    body: {
      rank: rank ?? 0,
      category: category ?? 'GEN',
      quota: first(sp.quota) ?? 'AI',
      year: int(sp.year),
      rounds: list(sp.rounds),
      branches: list(sp.branches),
      states: list(sp.states),
      groups: list(sp.groups),
      degrees: list(sp.degrees),
      statuses,
      thresholds,
      branch_weight: Math.min(1, Math.max(0, numParam(sp.branch_weight, 0.6))),
      sort,
      limit,
      offset,
    },
  };
}

/** Same URL, different offset/sort – used by pagination and sortable headers. */
export function patchUrl(sp: SearchParams, patch: Record<string, string | number | undefined>) {
  const out = new URLSearchParams();
  for (const [k, v] of Object.entries(sp)) {
    if (v === undefined) continue;
    for (const one of Array.isArray(v) ? v : [v]) out.append(k, one);
  }
  for (const [k, v] of Object.entries(patch)) {
    out.delete(k);
    if (v !== undefined && v !== '') out.set(k, String(v));
  }
  const s = out.toString();
  return s ? `?${s}` : '';
}
