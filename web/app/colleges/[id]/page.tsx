import Link from 'next/link';
import { notFound } from 'next/navigation';
import { ApiErrorPanel } from '@/components/api-error';
import { RoundTrend } from '@/components/charts';
import { IconArrowRight } from '@/components/icons';
import { PageHeader } from '@/components/shell';
import { Card, CardHeader, EmptyState, Pill } from '@/components/ui';
import { ApiError, getCollege, getYears, type CollegeCourse } from '@/lib/api';
import { catLabel, first, int, num, rank as fmtRank } from '@/lib/format';
import type { SearchParams } from '@/lib/query';

export const dynamic = 'force-dynamic';

const CAT_COLORS: Record<string, string> = {
  OPEN: '#4f46e5', OPEN_PWD: '#818cf8', OBC: '#0ea5e9', OBC_PWD: '#38bdf8', SC: '#16a34a', SC_PWD: '#4ade80',
  ST: '#f59e0b', ST_PWD: '#fbbf24', EWS: '#db2777', EWS_PWD: '#f472b6',
};

export default async function CollegePage({ params, searchParams }:
  { params: { id: string }; searchParams: SearchParams }) {
  const id = Number(params.id);
  if (!Number.isFinite(id)) notFound();

  let years, data;
  try {
    years = await getYears();
    data = await getCollege(id, { year: int(searchParams.year) });
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    return (<><PageHeader title="College" /><ApiErrorPanel error={error} title="Cannot load this college" /></>);
  }

  const yearShown = int(searchParams.year) ?? Math.max(...data.years);
  const courses = data.courses.filter((c) => c.year === yearShown);
  const quotas = Array.from(new Set(courses.flatMap((c) => c.cutoffs.map((x) => x.quota)))).sort();
  const quota = first(searchParams.quota) ?? (quotas.includes('AI') ? 'AI' : quotas[0]);
  const inQuota = courses
    .map((c) => ({ ...c, cutoffs: c.cutoffs.filter((x) => x.quota === quota) }))
    .filter((c) => c.cutoffs.length || c.seat_matrix_round1.some((s) => s.quota === quota));
  const roundCodes = Array.from(new Set(inQuota.flatMap((c) => c.cutoffs.map((x) => x.round))))
    .sort((a, b) => ['R1', 'R2', 'R3', 'STRAY', 'SPECIAL_STRAY'].indexOf(a) - ['R1', 'R2', 'R3', 'STRAY', 'SPECIAL_STRAY'].indexOf(b));

  const selectedCode = first(searchParams.course) ?? inQuota[0]?.course.code;
  const selected = inQuota.find((c) => c.course.code === selectedCode) ?? inQuota[0];
  const catsOfSelected = selected ? Array.from(new Set(selected.cutoffs.map((x) => x.seat_category))).sort() : [];
  const trendData = selected
    ? roundCodes.map((r) => ({
        round: r,
        ...Object.fromEntries(catsOfSelected.map((cat) => [
          cat, selected.cutoffs.find((x) => x.round === r && x.seat_category === cat)?.closing_rank ?? null,
        ])),
      }))
    : [];

  const tableCats = Array.from(new Set(inQuota.flatMap((c) => c.cutoffs.map((x) => x.seat_category)))).sort();
  const tableCat = first(searchParams.seat_category) ?? (tableCats.includes('OPEN') ? 'OPEN' : tableCats[0]);

  return (
    <>
      <PageHeader
        title={data.institute.short_name}
        meta={<>
          <span>{data.institute.state ?? 'State not in address'}</span>
          {data.institute.mcc_code ? <span>MCC code {data.institute.mcc_code}</span> : null}
          <span>{courses.length} courses in {yearShown}</span>
        </>}
        actions={<Link href="/colleges" className="btn-ghost">All colleges</Link>}
      />

      <div className="space-y-5">
        <Card className="card-pad">
          <p className="text-sm text-ink-soft">{data.institute.name}</p>
          <form method="get" className="mt-3 flex flex-wrap items-end gap-3">
            <div>
              <label className="label" htmlFor="year">Year</label>
              <select className="field" id="year" name="year" defaultValue={String(yearShown)}>
                {years.map((y) => <option key={y.year} value={y.year}>{y.year}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="quota">Quota</label>
              <select className="field" id="quota" name="quota" defaultValue={quota}>
                {quotas.map((qq) => <option key={qq} value={qq}>{qq}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="seat_category">Seat category in table</label>
              <select className="field" id="seat_category" name="seat_category" defaultValue={tableCat}>
                {tableCats.map((c) => <option key={c} value={c}>{catLabel(c)}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="course">Course in chart</label>
              <select className="field" id="course" name="course" defaultValue={selected?.course.code}>
                {inQuota.map((c) => <option key={c.course.code} value={c.course.code}>{c.course.branch} ({c.course.degree})</option>)}
              </select>
            </div>
            <button type="submit" className="btn-primary">Update</button>
          </form>
        </Card>

        {inQuota.length === 0 ? (
          <Card><EmptyState title={`No ${quota} allotments recorded here in ${yearShown}`}>
            Try another quota or year.
          </EmptyState></Card>
        ) : (
          <>
            <Card>
              <CardHeader
                title={selected ? `${selected.course.branch} – closing rank by round` : 'Closing rank by round'}
                subtitle={selected ? `${selected.course.name} · ${quota} quota · ${yearShown}` : undefined}
                actions={<Pill tone="brand">{catsOfSelected.map(catLabel).join(', ')}</Pill>}
              />
              <div className="card-pad">
                {catsOfSelected.length ? (
                  <RoundTrend data={trendData}
                              series={catsOfSelected.map((c) => ({ key: c, name: catLabel(c), color: CAT_COLORS[c] ?? '#64748b' }))} />
                ) : <p className="py-8 text-center text-sm text-ink-soft">No cut-offs for this course in {quota}.</p>}
                <p className="mt-2 text-xs text-ink-faint">
                  A later round is usually easier because candidates ahead of you have settled or upgraded. Each point is the
                  last rank allotted on that seat category in that round.
                </p>
              </div>
            </Card>

            <Card>
              <CardHeader title={`All courses – ${catLabel(tableCat)} seats`}
                          subtitle={`Closing rank per round (${quota} quota, ${yearShown}). “–” means no such seat was allotted in that round.`} />
              <div className="overflow-x-auto">
                <table className="w-full border-collapse">
                  <thead className="bg-slate-50/80">
                    <tr>
                      <th scope="col" className="th">Course</th>
                      <th scope="col" className="th">Group</th>
                      {roundCodes.map((r) => <th key={r} scope="col" className="th">{r}</th>)}
                      <th scope="col" className="th">R1 seats offered</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {inQuota.map((c) => {
                      const seats = c.seat_matrix_round1
                        .filter((s) => s.quota === quota && (s.seat_category === tableCat || s.seat_category === null))
                        .reduce((sum, s) => sum + s.seats, 0);
                      return (
                        <tr key={c.course.code} className="hover:bg-slate-50/60">
                          <td className="td">
                            <p className="font-medium">{c.course.branch}</p>
                            <p className="text-xs text-ink-faint">{c.course.degree} · {c.course.code}</p>
                          </td>
                          <td className="td text-sm text-ink-soft">{c.course.group}</td>
                          {roundCodes.map((r) => {
                            const cut = c.cutoffs.find((x) => x.round === r && x.seat_category === tableCat);
                            return (
                              <td key={r} className="td tabular-nums">
                                {cut ? (
                                  <>
                                    <span className="font-medium">{fmtRank(cut.closing_rank)}</span>
                                    <p className="text-xs text-ink-faint">opened {fmtRank(cut.opening_rank)} · {cut.seats_allotted} seat{cut.seats_allotted === 1 ? '' : 's'}</p>
                                  </>
                                ) : <span className="text-ink-faint">–</span>}
                              </td>
                            );
                          })}
                          <td className="td tabular-nums">{seats ? num(seats) : <span className="text-ink-faint">–</span>}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <p className="border-t border-slate-100 px-4 py-3 text-xs text-ink-faint sm:px-5">
                Seats offered come from the Round-1 seat matrix and are only shown where that matrix could be linked to this
                institute. Use the <Link className="text-brand-700 hover:underline" href="/cutoffs">cut-off explorer <IconArrowRight className="inline h-3 w-3" /></Link> for
                raw rows across colleges.
              </p>
            </Card>
          </>
        )}
      </div>
    </>
  );
}
