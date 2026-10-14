import { NextResponse } from 'next/server';
import { predict } from '@/lib/api';
import { parseQuery, type SearchParams } from '@/lib/query';

/** CSV of the current prediction (all matching options, not just the visible page). */
export async function GET(request: Request) {
  const sp: SearchParams = {};
  new URL(request.url).searchParams.forEach((v, k) => {
    const cur = sp[k];
    sp[k] = cur === undefined ? v : Array.isArray(cur) ? [...cur, v] : [cur, v];
  });
  const q = parseQuery(sp);
  if (!q.submitted) return NextResponse.json({ error: 'rank and category are required' }, { status: 400 });

  const result = await predict({ ...q.body, limit: 5000, offset: 0 });
  const rounds = result.rounds.map((r) => r.code);
  const header = ['college', 'state', 'branch', 'course', 'course_code', 'degree', 'chance', 'desirability',
    ...rounds.map((r) => `${r}_closing_rank`), ...rounds.map((r) => `${r}_seat_category`),
    'ratio_first_round', 'institute_median_air', 'branch_median_air', 'reason'];
  const cell = (v: unknown) => {
    const s = v == null ? '' : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = [
    `# NEET PG counselling – historical options (personal shortlist, NOT an official MCC choice list)`,
    `# year=${result.year} quota=${result.quota} category=${result.category} rank=${result.rank} rounds=${rounds.join('|')}`,
    `# eligible seat categories=${result.eligibility.seat_categories.join('|')} source=${result.eligibility.source ?? ''}`,
    `# thresholds safe=${result.thresholds.safe} good=${result.thresholds.good} borderline=${result.thresholds.borderline} reach=${result.thresholds.reach}`,
    header.join(','),
    ...result.options.map((o) => [
      o.institute.short_name, o.institute.state, o.course.branch, o.course.name, o.course.code, o.course.degree,
      o.status_label, o.desirability,
      ...rounds.map((r) => o.rounds.find((x) => x.round === r)?.best_close ?? ''),
      ...rounds.map((r) => o.rounds.find((x) => x.round === r)?.best_category ?? ''),
      o.ratio_first_round ?? '', o.institute_median_air ?? '', o.branch_median_air ?? '', o.reason,
    ].map(cell).join(',')),
  ];
  const name = `neetpg_${result.year}_${result.category}_AIR${result.rank}_${result.quota}.csv`;
  return new NextResponse(lines.join('\n'), {
    headers: {
      'Content-Type': 'text/csv; charset=utf-8',
      'Content-Disposition': `attachment; filename="${name}"`,
    },
  });
}
