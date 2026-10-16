/**
 * Typed client for the predictor API.
 *
 * Server components call the API over the Docker network (API_BASE_INTERNAL, e.g. http://api:8000);
 * anything running in the browser uses NEXT_PUBLIC_API_BASE (e.g. http://127.0.0.1:8000).
 */
const serverBase = () => process.env.API_BASE_INTERNAL ?? 'http://api:8000';
export const PUBLIC_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://127.0.0.1:8000';

const base = () => (typeof window === 'undefined' ? serverBase() : PUBLIC_BASE);

/**
 * Shared secret for a publicly reachable API. Read only on the server – the variable has no NEXT_PUBLIC_
 * prefix, so it is never bundled into the browser build.
 */
const authHeaders = (): Record<string, string> => {
  if (typeof window !== 'undefined') return {};
  const token = process.env.API_TOKEN;
  return token ? { 'X-API-Token': token } : {};
};

export class ApiError extends Error {
  constructor(readonly status: number, readonly detail: ApiErrorDetail) {
    super(detail.message ?? `API error ${status}`);
  }
}
export type ApiErrorDetail = { message?: string; field?: string; allowed?: unknown };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${base()}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...authHeaders(), ...(init?.headers ?? {}) },
    cache: 'no-store',
  });
  if (!res.ok) {
    let detail: ApiErrorDetail = { message: `${res.status} ${res.statusText}` };
    try {
      const body = await res.json();
      detail = typeof body?.detail === 'object' ? body.detail : { message: JSON.stringify(body?.detail ?? body) };
    } catch {
      /* keep the status-line message */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

const qs = (params: Record<string, string | number | undefined | null>) => {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== '') sp.set(k, String(v));
  const s = sp.toString();
  return s ? `?${s}` : '';
};

/* ----------------------------------------------------------------- types */
export type Status = 'safe' | 'good' | 'borderline' | 'later_round' | 'reach' | 'unlikely';
export type Sort = 'desirability' | 'chance' | 'closing_rank_desc' | 'closing_rank_asc'
  | 'branch_demand' | 'college_demand' | 'college' | 'branch';
export const SORTS: Sort[] = ['desirability', 'chance', 'closing_rank_desc', 'closing_rank_asc',
  'branch_demand', 'college_demand', 'college', 'branch'];
export const STATUS_ORDER: Status[] = ['safe', 'good', 'borderline', 'later_round', 'reach', 'unlikely'];
export const ACHIEVABLE: Status[] = ['safe', 'good', 'borderline', 'later_round'];

export type Round = { code: string; name: string; kind: 'regular' | 'stray'; seq?: number };
export type Institute = { id: number; name: string; short_name: string; state: string | null; mcc_code: string | null };
export type Course = { id: number; code: string; name: string; branch: string; group: string; degree: string };
export type CategoryCutoff = { seats: number; opening_rank: number; closing_rank: number };
export type RoundCutoff = {
  round: string; round_name: string; best_close: number | null; best_category: string | null;
  by_category: Record<string, CategoryCutoff>;
};
export type Option = {
  institute: Institute; course: Course; status: Status; status_label: string; desirability: number;
  ratio_first_round: number | null; best_close_later_rounds: number | null; rounds: RoundCutoff[];
  institute_median_air: number | null; branch_median_air: number | null; reason: string;
};
export type Thresholds = { safe: number; good: number; borderline: number; reach: number };
export type Eligibility = { seat_categories: string[]; confirmed: boolean; source: string | null; clauses: string[] };
export type PredictResponse = {
  year: number; quota: string; quota_name: string; category: string; rank: number; rounds: Round[];
  eligibility: Eligibility; thresholds: Thresholds;
  sort: Sort;
  summary: { by_status: Record<Status, number>; by_branch: Record<string, Record<Status, number>> };
  total: number; options: Option[]; notices: string[];
};
export type PredictBody = {
  rank: number; category: string; quota?: string; year?: number; rounds?: string[]; branches?: string[];
  states?: string[]; groups?: string[]; degrees?: string[]; statuses?: Status[]; thresholds?: Thresholds;
  branch_weight?: number; sort?: Sort; limit?: number; offset?: number;
};
export type YearInfo = {
  year: number; label: string; rounds: Round[];
  eligibility: Record<string, { seat_categories: string[]; confirmed: boolean; source: string | null; clauses: string[] }>;
};
export type BranchInfo = {
  branch: string; group: string; degrees: string[]; course_codes: string[];
  demand: { seats: number; median_air: number; p25_air: number } | null;
};
export type Meta = {
  supported_quotas: Record<string, string>; all_quotas: Record<string, string>;
  candidate_categories: Record<string, string>; seat_categories: Record<string, string>;
  statuses: Record<Status, string>; default_statuses: Status[]; default_thresholds: Thresholds;
  sorts: Record<Sort, string>; default_sort: Sort;
  groups: string[]; degrees: string[]; limitations: string[];
  sources: { year: number | null; path: string; kind: string; title: string | null; url: string | null; sha256: string }[];
  data_version: number;
};
export type CollegeListItem = Institute & { allotments: number; courses: number; quotas: string[] };
export type CollegeCourse = {
  year: number; course: Course;
  cutoffs: { round: string; quota: string; seat_category: string; seats_allotted: number; opening_rank: number; closing_rank: number }[];
  seat_matrix_round1: { quota: string; seat_category: string | null; seats: number }[];
};
export type CutoffRow = {
  year: number; round_code: string; quota_code: string; seat_category_code: string; seats_allotted: number;
  opening_rank: number; closing_rank: number; college_id: number; college: string; state: string | null;
  course_code: string; course: string; branch: string; degree: string;
};

/* ----------------------------------------------------------------- calls */
export const predict = (body: PredictBody) =>
  request<PredictResponse>('/api/predict', { method: 'POST', body: JSON.stringify(body) });

export const getYears = () => request<YearInfo[]>('/api/years');
export const getMeta = () => request<Meta>('/api/meta');
export const getBranches = (p: { year?: number; quota?: string } = {}) => request<BranchInfo[]>(`/api/branches${qs(p)}`);
export const getStates = (p: { year?: number } = {}) =>
  request<{ state: string | null; institutes: number }[]>(`/api/states${qs(p)}`);
export const getColleges = (p: {
  year?: number; quota?: string; state?: string; q?: string; branch?: string; limit?: number; offset?: number;
}) => request<{ year: number; total: number; items: CollegeListItem[] }>(`/api/colleges${qs(p)}`);
export const getCollege = (id: number, p: { year?: number } = {}) =>
  request<{ institute: Institute; years: number[]; courses: CollegeCourse[] }>(`/api/colleges/${id}${qs(p)}`);
export const getCutoffs = (p: Record<string, string | number | undefined>) =>
  request<{ year: number; total: number; items: CutoffRow[] }>(`/api/cutoffs${qs(p)}`);
export const getHealth = () => request<{ status: string; data_version: number }>('/api/health');
