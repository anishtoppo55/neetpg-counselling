import Link from 'next/link';
import { ApiErrorPanel } from '@/components/api-error';
import { PageHeader } from '@/components/shell';
import {
  Card, CardHeader, CardListView, EmptyState, Pagination, Pill, RecordCard, TableView,
} from '@/components/ui';
import { getBranches, getCutoffs, getMeta, getStates, getYears } from '@/lib/api';
import { catLabel, first, int, num, rank as fmtRank } from '@/lib/format';
import { patchUrl, type SearchParams } from '@/lib/query';

export const dynamic = 'force-dynamic';
const PAGE = 50;

export default async function CutoffsPage({ searchParams }: { searchParams: SearchParams }) {
  const offset = Math.max(0, int(searchParams.offset, 0)!);
  const sel = {
    quota: first(searchParams.quota) ?? 'AI',
    round: first(searchParams.round) ?? '',
    seat_category: first(searchParams.seat_category) ?? '',
    branch: first(searchParams.branch) ?? '',
    state: first(searchParams.state) ?? '',
    course_code: first(searchParams.course_code) ?? '',
    min_closing_rank: first(searchParams.min_closing_rank) ?? '',
    max_closing_rank: first(searchParams.max_closing_rank) ?? '',
  };

  let years, meta, branches, states, data;
  try {
    [years, meta] = await Promise.all([getYears(), getMeta()]);
    const year = int(searchParams.year) ?? years[0]?.year;
    [branches, states, data] = await Promise.all([
      getBranches({ year }),
      getStates({ year }),
      getCutoffs({ year, limit: PAGE, offset, ...Object.fromEntries(Object.entries(sel).filter(([, v]) => v !== '')) }),
    ]);
  } catch (error) {
    return (<><PageHeader title="Cut-offs" /><ApiErrorPanel error={error} title="Cannot load cut-offs" /></>);
  }
  const yearShown = data.year;
  const rounds = years.find((y) => y.year === yearShown)?.rounds ?? [];

  return (
    <>
      <PageHeader title="Cut-off explorer"
                  meta={<span>{num(data.total)} rows · one per round × quota × college × course × seat category</span>} />
      <div className="space-y-5">
        <Card className="no-print card-pad">
          <form method="get" className="grid items-end gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <label className="label" htmlFor="year">Year</label>
              <select className="field" id="year" name="year" defaultValue={String(yearShown)}>
                {years.map((y) => <option key={y.year} value={y.year}>{y.year}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="quota">Quota</label>
              <select className="field" id="quota" name="quota" defaultValue={sel.quota}>
                {Object.entries(meta.all_quotas).map(([k, v]) => <option key={k} value={k}>{k} – {v}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="round">Round</label>
              <select className="field" id="round" name="round" defaultValue={sel.round}>
                <option value="">All rounds</option>
                {rounds.map((r) => <option key={r.code} value={r.code}>{r.name}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="seat_category">Seat category</label>
              <select className="field" id="seat_category" name="seat_category" defaultValue={sel.seat_category}>
                <option value="">All categories</option>
                {Object.keys(meta.seat_categories).map((c) => <option key={c} value={c}>{catLabel(c)}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="branch">Branch</label>
              <select className="field" id="branch" name="branch" defaultValue={sel.branch}>
                <option value="">All branches</option>
                {branches.map((b) => <option key={b.branch} value={b.branch}>{b.branch}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="state">State</label>
              <select className="field" id="state" name="state" defaultValue={sel.state}>
                <option value="">All states</option>
                {states.filter((s) => s.state).map((s) => <option key={s.state!} value={s.state!}>{s.state}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="min_closing_rank">Closing rank from</label>
              <input className="field" id="min_closing_rank" name="min_closing_rank" type="number" min={1}
                     defaultValue={sel.min_closing_rank} placeholder="e.g. 20000" />
            </div>
            <div>
              <label className="label" htmlFor="max_closing_rank">to</label>
              <input className="field" id="max_closing_rank" name="max_closing_rank" type="number" min={1}
                     defaultValue={sel.max_closing_rank} placeholder="e.g. 40000" />
            </div>
            <div className="flex gap-2 lg:col-span-4">
              <button type="submit" className="btn-primary">Apply filters</button>
              <Link href="/cutoffs" className="btn-ghost">Clear</Link>
            </div>
          </form>
        </Card>

        <Card>
          <CardHeader title="Cut-off rows" subtitle="Sorted by round, then closing rank" />
          {data.items.length === 0 ? (
            <EmptyState title="No rows match these filters">Widen the rank range or clear a filter.</EmptyState>
          ) : (
            <>
              <CardListView label="Cut-off rows">
                {data.items.map((r, i) => (
                  <RecordCard
                    key={`m-${r.round_code}-${r.college_id}-${r.course_code}-${r.seat_category_code}-${i}`}
                    title={r.college}
                    href={`/colleges/${r.college_id}?year=${r.year}`}
                    subtitle={r.state ?? 'State not in address'}
                    badge={<Pill>{r.round_code}</Pill>}
                    fields={[
                      { label: 'Course', wide: true, value: <>{r.branch} <span className="text-xs text-ink-faint">{r.degree} · {r.course_code}</span></> },
                      { label: 'Seat category', value: catLabel(r.seat_category_code) },
                      { label: 'Seats allotted', value: <span className="tabular-nums">{r.seats_allotted}</span> },
                      { label: 'Opening rank', value: <span className="tabular-nums">{fmtRank(r.opening_rank)}</span> },
                      { label: 'Closing rank', value: <span className="font-medium tabular-nums">{fmtRank(r.closing_rank)}</span> },
                    ]}
                  />
                ))}
              </CardListView>

              <TableView>
                <table className="w-full border-collapse">
                  <thead className="bg-slate-50/80">
                    <tr>
                      <th scope="col" className="th">Round</th>
                      <th scope="col" className="th">College</th>
                      <th scope="col" className="th">Course</th>
                      <th scope="col" className="th">Seat category</th>
                      <th scope="col" className="th">Seats</th>
                      <th scope="col" className="th">Opening</th>
                      <th scope="col" className="th">Closing</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {data.items.map((r, i) => (
                      <tr key={`${r.round_code}-${r.college_id}-${r.course_code}-${r.seat_category_code}-${i}`}
                          className="hover:bg-slate-50/60">
                        <td className="td"><Pill>{r.round_code}</Pill></td>
                        <td className="td">
                          <Link href={`/colleges/${r.college_id}?year=${r.year}`} className="font-medium hover:text-brand-700">
                            {r.college}
                          </Link>
                          <p className="text-xs text-ink-faint">{r.state ?? '—'}</p>
                        </td>
                        <td className="td">
                          <p>{r.branch}</p>
                          <p className="text-xs text-ink-faint">{r.degree} · {r.course_code}</p>
                        </td>
                        <td className="td">{catLabel(r.seat_category_code)}</td>
                        <td className="td tabular-nums">{r.seats_allotted}</td>
                        <td className="td tabular-nums">{fmtRank(r.opening_rank)}</td>
                        <td className="td font-medium tabular-nums">{fmtRank(r.closing_rank)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableView>
              <Pagination total={data.total} limit={PAGE} offset={offset} label="rows"
                          makeHref={(o) => `/cutoffs${patchUrl(searchParams, { offset: o })}`} />
            </>
          )}
        </Card>
      </div>
    </>
  );
}
