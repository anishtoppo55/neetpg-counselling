import Link from 'next/link';
import { ApiErrorPanel } from '@/components/api-error';
import { BranchStack, StatusDonut } from '@/components/charts';
import { IconCheck, IconClock, IconGauge, IconLayers, IconShield, IconTarget } from '@/components/icons';
import { PredictForm } from '@/components/predict-form';
import { ResultsTable } from '@/components/results-table';
import { PageHeader } from '@/components/shell';
import { Card, CardHeader, KpiCard, Notice, Pill } from '@/components/ui';
import { ACHIEVABLE, getBranches, getMeta, getStates, getYears, predict, type Status } from '@/lib/api';
import { STATUS_META, catLabel, num } from '@/lib/format';
import { parseQuery, type SearchParams } from '@/lib/query';

export const dynamic = 'force-dynamic';

export default async function DashboardPage({ searchParams }: { searchParams: SearchParams }) {
  const q = parseQuery(searchParams);
  let meta, years, branches, states;
  try {
    [meta, years] = await Promise.all([getMeta(), getYears()]);
    const year = q.body.year ?? years[0]?.year;
    [branches, states] = await Promise.all([getBranches({ year, quota: q.body.quota }), getStates({ year })]);
  } catch (error) {
    return (
      <>
        <PageHeader title="Predictor" />
        <ApiErrorPanel error={error} title="Cannot reach the predictor API" />
      </>
    );
  }
  const yearInUse = q.body.year ?? years[0]?.year ?? 0;

  let result = null;
  let error: unknown = null;
  if (q.submitted) {
    try {
      result = await predict(q.body);
    } catch (e) {
      error = e;
    }
  }

  const byStatus = result?.summary.by_status;
  const totalAll = byStatus ? Object.values(byStatus).reduce((s, n) => s + n, 0) : 0;
  const achievable = byStatus ? ACHIEVABLE.reduce((s, k) => s + (byStatus[k] ?? 0), 0) : 0;
  const share = (n: number) => (totalAll ? `${Math.round((n / totalAll) * 100)}% of ${num(totalAll)}` : undefined);

  const branchChart = result
    ? Object.entries(result.summary.by_branch)
        .map(([branch, counts]) => ({
          branch,
          total: ACHIEVABLE.reduce((s, k) => s + (counts[k] ?? 0), 0),
          ...Object.fromEntries(ACHIEVABLE.map((k) => [k, counts[k] ?? 0])),
        }))
        .filter((d) => d.total > 0)
        .sort((a, b) => b.total - a.total)
        .slice(0, 10)
    : [];

  return (
    <>
      <PageHeader
        title="Predictor"
        meta={result ? (
          <>
            <span className="inline-flex items-center gap-1.5"><IconLayers className="h-4 w-4 text-ink-faint" />
              {result.year} · {result.quota} ({result.quota_name.split('–')[0].trim()})</span>
            <span className="inline-flex items-center gap-1.5"><IconShield className="h-4 w-4 text-ink-faint" />
              {catLabel(result.category)} · AIR {num(result.rank)}</span>
            <span className="inline-flex items-center gap-1.5"><IconClock className="h-4 w-4 text-ink-faint" />
              Rounds {result.rounds.map((r) => r.code).join(' → ')}</span>
          </>
        ) : <span>Enter your rank and category to see historical options</span>}
        actions={result ? (
          <>
            <Link className="btn-ghost" href="#results">Jump to table</Link>
            <Link className="btn-primary" href="/about">How this is calculated</Link>
          </>
        ) : null}
      />

      <div className="space-y-5">
        <PredictForm q={q} meta={meta} years={years} branches={branches} states={states} yearInUse={yearInUse} />

        {error ? <ApiErrorPanel error={error} /> : null}

        {!q.submitted && !error ? (
          <Card className="card-pad">
            <h2 className="text-base font-semibold">What you get</h2>
            <ul className="mt-2 grid gap-3 text-sm text-ink-soft sm:grid-cols-2 lg:grid-cols-4">
              {[
                ['Every college × course', 'Historical opening and closing ranks for the seats your category can hold.'],
                ['A chance label', 'Safe, Good, Borderline, Later-round or Reach, based on thresholds you can change.'],
                ['A reason', 'Each row says which seat, which round and which rule produced the label.'],
                ['No guarantees', 'Cut-offs move every year; treat this as evidence, not a prediction.'],
              ].map(([t, d]) => (
                <li key={t} className="rounded-xl border border-slate-200 p-3">
                  <p className="font-medium text-ink">{t}</p>
                  <p className="mt-1">{d}</p>
                </li>
              ))}
            </ul>
          </Card>
        ) : null}

        {result ? (
          <>
            {result.notices.map((n) => (
              <Notice key={n} tone={n.includes('not been confirmed') ? 'warn' : 'info'}>{n}</Notice>
            ))}

            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <KpiCard icon={<IconTarget className="h-5 w-5" />} label="Achievable options" tone="brand"
                       value={num(achievable)} hint={share(achievable)}
                       delta={{ text: `${num(byStatus!.reach)} reach`, dir: 'flat' }} />
              <KpiCard icon={<IconCheck className="h-5 w-5" />} label="Safe" tone="green"
                       value={num(byStatus!.safe)} hint={share(byStatus!.safe)} />
              <KpiCard icon={<IconGauge className="h-5 w-5" />} label="Good chance + Borderline" tone="amber"
                       value={num(byStatus!.good + byStatus!.borderline)}
                       hint={`${num(byStatus!.good)} good · ${num(byStatus!.borderline)} borderline`} />
              <KpiCard icon={<IconClock className="h-5 w-5" />} label="Later-round opportunities" tone="violet"
                       value={num(byStatus!.later_round)}
                       hint={result.rounds.length > 1 ? `Opened in ${result.rounds.slice(1).map((r) => r.code).join(' / ')}`
                                                      : 'Add more rounds to see these'} />
            </div>

            <div className="grid gap-4 xl:grid-cols-3">
              <Card className="xl:col-span-2">
                <CardHeader title="Where your options are"
                            subtitle="Top branches by achievable options (segments are the chance labels)"
                            actions={<Pill tone="brand">{branchChart.length} branches shown</Pill>} />
                <div className="card-pad">
                  {branchChart.length ? <BranchStack data={branchChart} statuses={ACHIEVABLE as Status[]} />
                    : <p className="py-10 text-center text-sm text-ink-soft">No achievable options with these filters.</p>}
                </div>
              </Card>
              <Card>
                <CardHeader title="Chance breakdown" subtitle="All options before the classification filter" />
                <div className="card-pad">
                  <StatusDonut achievableShare={totalAll ? achievable / totalAll : 0}
                               data={(Object.keys(byStatus!) as Status[]).map((s) => ({
                                 status: s, label: STATUS_META[s].label, value: byStatus![s],
                               }))} />
                </div>
              </Card>
            </div>

            <Card className="card-pad">
              <h2 className="text-sm font-semibold">Seats you are eligible for</h2>
              <p className="mt-1 text-sm text-ink-soft">
                As a {catLabel(result.category)} candidate in {result.year}, the predictor considers{' '}
                {result.eligibility.seat_categories.map((c) => <Pill key={c} tone="brand">{catLabel(c)}</Pill>)}{' '}
                seats. Source: {result.eligibility.source ?? 'MCC information bulletin'}
                {result.eligibility.clauses.length ? ` (${result.eligibility.clauses.join('; ')})` : ''}.
                {result.eligibility.confirmed ? '' : ' These rules are still awaiting review.'}
              </p>
            </Card>

            <ResultsTable options={result.options} total={result.total} limit={q.limit} offset={q.offset}
                          sort={result.sort} sortOptions={meta.sorts} sp={searchParams} myRank={result.rank}
                          roundCodes={result.rounds.map((r) => r.code)} />
          </>
        ) : null}
      </div>
    </>
  );
}
