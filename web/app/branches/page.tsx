import Link from 'next/link';
import { ApiErrorPanel } from '@/components/api-error';
import { DemandBars } from '@/components/charts';
import { PageHeader } from '@/components/shell';
import { Card, CardHeader, CardListView, Pill, RecordCard, TableView } from '@/components/ui';
import { getBranches, getMeta, getYears } from '@/lib/api';
import { first, int, num, rank as fmtRank } from '@/lib/format';
import type { SearchParams } from '@/lib/query';

export const dynamic = 'force-dynamic';

export default async function BranchesPage({ searchParams }: { searchParams: SearchParams }) {
  const quota = first(searchParams.quota) ?? 'AI';
  let years, meta, branches;
  try {
    [years, meta] = await Promise.all([getYears(), getMeta()]);
    const year = int(searchParams.year) ?? years[0]?.year;
    branches = await getBranches({ year, quota });
  } catch (error) {
    return (<><PageHeader title="Branches" /><ApiErrorPanel error={error} title="Cannot load branches" /></>);
  }
  const yearShown = int(searchParams.year) ?? years[0]?.year ?? 0;
  const group = first(searchParams.group) ?? '';
  const shown = branches.filter((b) => (group ? b.group === group : true));
  const withDemand = shown.filter((b) => b.demand).map((b) => ({
    branch: b.branch, median: Math.round(b.demand!.median_air), p25: Math.round(b.demand!.p25_air),
  }));

  return (
    <>
      <PageHeader title="Branch demand"
                  meta={<span>Median rank of everyone allotted each branch in Round 1, {yearShown}, {quota} quota (all categories)</span>} />
      <div className="space-y-5">
        <Card className="no-print card-pad">
          <form method="get" className="flex flex-wrap items-end gap-3">
            <div>
              <label className="label" htmlFor="year">Year</label>
              <select className="field" id="year" name="year" defaultValue={String(yearShown)}>
                {years.map((y) => <option key={y.year} value={y.year}>{y.year}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="quota">Quota</label>
              <select className="field" id="quota" name="quota" defaultValue={quota}>
                {Object.entries(meta.supported_quotas).map(([k, v]) => <option key={k} value={k}>{k} – {v}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="group">Group</label>
              <select className="field" id="group" name="group" defaultValue={group}>
                <option value="">All groups</option>
                {meta.groups.map((g) => <option key={g} value={g}>{g}</option>)}
              </select>
            </div>
            <button type="submit" className="btn-primary">Update</button>
          </form>
        </Card>

        <Card>
          <CardHeader title="How early each branch fills"
                      subtitle="Lower median AIR = chosen earlier by higher ranks. This drives the branch half of the desirability score."
                      actions={<Pill tone="brand">{withDemand.length} branches</Pill>} />
          <div className="card-pad">
            {withDemand.length ? <DemandBars data={withDemand} />
              : <p className="py-8 text-center text-sm text-ink-soft">No Round-1 allotments for this quota.</p>}
          </div>
        </Card>

        <Card>
          <CardHeader title="All branches" subtitle="Seats are Round-1 allotments in the selected quota" />
          <CardListView label="All branches">
            {shown.map((b) => (
              <RecordCard
                key={`m-${b.branch}`}
                title={b.branch}
                subtitle={b.group}
                fields={[
                  { label: 'Degrees', wide: true, value: <span className="flex flex-wrap gap-1">{b.degrees.map((d) => <Pill key={d}>{d}</Pill>)}</span> },
                  { label: 'R1 seats', value: <span className="tabular-nums">{b.demand ? num(b.demand.seats) : '–'}</span> },
                  { label: 'Median AIR', value: <span className="tabular-nums">{b.demand ? fmtRank(Math.round(b.demand.median_air)) : '–'}</span> },
                  { label: '25th pct AIR', value: <span className="tabular-nums">{b.demand ? fmtRank(Math.round(b.demand.p25_air)) : '–'}</span> },
                ]}
                action={
                  <Link className="btn-ghost" href={`/cutoffs?year=${yearShown}&quota=${quota}&branch=${encodeURIComponent(b.branch)}`}>
                    Cut-offs
                  </Link>
                }
              />
            ))}
          </CardListView>

          <TableView>
            <table className="w-full border-collapse">
              <thead className="bg-slate-50/80">
                <tr>
                  <th scope="col" className="th">Branch</th>
                  <th scope="col" className="th">Group</th>
                  <th scope="col" className="th">Degrees</th>
                  <th scope="col" className="th">R1 seats</th>
                  <th scope="col" className="th">Median AIR</th>
                  <th scope="col" className="th">25th pct AIR</th>
                  <th scope="col" className="th"><span className="sr-only">Cut-offs</span></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {shown.map((b) => (
                  <tr key={b.branch} className="hover:bg-slate-50/60">
                    <td className="td font-medium">{b.branch}</td>
                    <td className="td text-ink-soft">{b.group}</td>
                    <td className="td"><span className="flex flex-wrap gap-1">{b.degrees.map((d) => <Pill key={d}>{d}</Pill>)}</span></td>
                    <td className="td tabular-nums">{b.demand ? num(b.demand.seats) : '–'}</td>
                    <td className="td tabular-nums">{b.demand ? fmtRank(Math.round(b.demand.median_air)) : '–'}</td>
                    <td className="td tabular-nums">{b.demand ? fmtRank(Math.round(b.demand.p25_air)) : '–'}</td>
                    <td className="td">
                      <Link className="btn-ghost" href={`/cutoffs?year=${yearShown}&quota=${quota}&branch=${encodeURIComponent(b.branch)}`}>
                        Cut-offs
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableView>
        </Card>
      </div>
    </>
  );
}
