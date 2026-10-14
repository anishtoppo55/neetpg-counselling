import Link from 'next/link';
import { ApiErrorPanel } from '@/components/api-error';
import { IconArrowRight, IconSearch } from '@/components/icons';
import { PageHeader } from '@/components/shell';
import { Card, CardHeader, EmptyState, Pagination, Pill } from '@/components/ui';
import { getBranches, getColleges, getMeta, getStates, getYears } from '@/lib/api';
import { num } from '@/lib/format';
import { patchUrl, type SearchParams } from '@/lib/query';
import { first, int } from '@/lib/format';

export const dynamic = 'force-dynamic';
const PAGE = 20;

export default async function CollegesPage({ searchParams }: { searchParams: SearchParams }) {
  const q = first(searchParams.q) ?? '';
  const state = first(searchParams.state) ?? '';
  const branch = first(searchParams.branch) ?? '';
  const quota = first(searchParams.quota) ?? '';
  const offset = Math.max(0, int(searchParams.offset, 0)!);

  let years, meta, states, branches, data;
  try {
    [years, meta] = await Promise.all([getYears(), getMeta()]);
    const year = int(searchParams.year) ?? years[0]?.year;
    [states, branches, data] = await Promise.all([
      getStates({ year }),
      getBranches({ year }),
      getColleges({ year, q: q.length >= 2 ? q : undefined, state: state || undefined, branch: branch || undefined,
                    quota: quota || undefined, limit: PAGE, offset }),
    ]);
  } catch (error) {
    return (<><PageHeader title="Colleges" /><ApiErrorPanel error={error} title="Cannot load colleges" /></>);
  }

  return (
    <>
      <PageHeader title="Colleges"
                  meta={<span>{num(data.total)} institutes with allotments in {data.year}</span>} />
      <div className="space-y-5">
        <Card className="no-print card-pad">
          <form method="get" action="/colleges" className="grid items-end gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <div className="lg:col-span-2">
              <label className="label" htmlFor="q">Name contains</label>
              <div className="relative">
                <IconSearch className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-ink-faint" />
                <input className="field pl-9" id="q" name="q" type="search" defaultValue={q} minLength={2}
                       placeholder="e.g. Stanley, Kozhikode, PGIMER" />
              </div>
            </div>
            <div>
              <label className="label" htmlFor="year">Year</label>
              <select className="field" id="year" name="year" defaultValue={String(data.year)}>
                {years.map((y) => <option key={y.year} value={y.year}>{y.year}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="state">State</label>
              <select className="field" id="state" name="state" defaultValue={state}>
                <option value="">All states</option>
                {states.filter((s) => s.state).map((s) => <option key={s.state!} value={s.state!}>{s.state}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="branch">Offers branch</label>
              <select className="field" id="branch" name="branch" defaultValue={branch}>
                <option value="">Any branch</option>
                {branches.map((b) => <option key={b.branch} value={b.branch}>{b.branch}</option>)}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="quota">Quota</label>
              <select className="field" id="quota" name="quota" defaultValue={quota}>
                <option value="">All quotas</option>
                {Object.entries(meta.all_quotas).map(([k, v]) => <option key={k} value={k}>{k} – {v}</option>)}
              </select>
            </div>
            <div className="flex gap-2 lg:col-span-5">
              <button type="submit" className="btn-primary">Apply filters</button>
              <Link href="/colleges" className="btn-ghost">Clear</Link>
            </div>
          </form>
        </Card>

        <Card>
          <CardHeader title="Institutes" subtitle="Counts are allotments in the selected year and quota" />
          {data.items.length === 0 ? (
            <EmptyState title="No colleges match">Try a shorter search term or clear the filters.</EmptyState>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full border-collapse">
                  <thead className="bg-slate-50/80">
                    <tr>
                      <th scope="col" className="th">College</th>
                      <th scope="col" className="th">State</th>
                      <th scope="col" className="th">Courses</th>
                      <th scope="col" className="th">Allotments</th>
                      <th scope="col" className="th">Quotas</th>
                      <th scope="col" className="th"><span className="sr-only">Open</span></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {data.items.map((c) => (
                      <tr key={c.id} className="hover:bg-slate-50/60">
                        <td className="td">
                          <Link href={`/colleges/${c.id}?year=${data.year}`} className="font-medium hover:text-brand-700">
                            {c.short_name}
                          </Link>
                          <p className="mt-0.5 max-w-xl truncate text-xs text-ink-faint" title={c.name}>{c.name}</p>
                        </td>
                        <td className="td">{c.state ?? <span className="text-ink-faint">not in address</span>}</td>
                        <td className="td tabular-nums">{c.courses}</td>
                        <td className="td tabular-nums">{num(c.allotments)}</td>
                        <td className="td"><span className="flex flex-wrap gap-1">{c.quotas.map((qq) => <Pill key={qq}>{qq}</Pill>)}</span></td>
                        <td className="td">
                          <Link href={`/colleges/${c.id}?year=${data.year}`} className="btn-ghost">
                            Cut-offs <IconArrowRight className="h-3.5 w-3.5" />
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination total={data.total} limit={PAGE} offset={offset} label="colleges"
                          makeHref={(o) => `/colleges${patchUrl(searchParams, { offset: o })}`} />
            </>
          )}
        </Card>
      </div>
    </>
  );
}
