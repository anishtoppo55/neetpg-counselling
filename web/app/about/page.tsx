import { ApiErrorPanel } from '@/components/api-error';
import { PageHeader } from '@/components/shell';
import {
  Card, CardHeader, CardListView, Notice, Pill, RecordCard, StatusChip, TableView,
} from '@/components/ui';
import { STATUS_ORDER, getMeta, getYears } from '@/lib/api';
import { STATUS_META, catLabel } from '@/lib/format';

export const dynamic = 'force-dynamic';

export default async function AboutPage() {
  let meta, years;
  try {
    [meta, years] = await Promise.all([getMeta(), getYears()]);
  } catch (error) {
    return (<><PageHeader title="Data & limits" /><ApiErrorPanel error={error} title="Cannot load metadata" /></>);
  }
  const unconfirmed = years.filter((y) => Object.values(y.eligibility).some((e) => !e.confirmed)).map((y) => y.year);

  return (
    <>
      <PageHeader title="Data & limits"
                  meta={<span>Everything here comes from official MCC and NBEMS documents · import #{meta.data_version}</span>} />

      <div className="space-y-5">
        <Notice tone="warn">
          These are historical cut-offs, not predictions or admission probabilities. Seat matrices, rules and cut-offs
          change every year – always check the current MCC information bulletin and seat matrix before filling choices.
          This site is a personal research aid and is not affiliated with MCC.
        </Notice>

        <Card>
          <CardHeader title="Privacy" subtitle="What this site does and does not keep about you" />
          <div className="card-pad space-y-2 text-sm text-ink-soft">
            <p>
              There are no accounts and no login. Your rank, category and filters are never written to the
              database – they travel in the page URL, which is why a result is shareable and bookmarkable, and the
              server answers each request without remembering it.
            </p>
            <p>
              This site does use <strong className="text-ink">Google Analytics</strong> to count visits and see which
              pages get used. Analytics sets cookies in your browser and sends Google the address of each page you
              view. On the predictor that address includes your rank and category, because they are part of the URL.
            </p>
            <p>
              To avoid that, use your browser&rsquo;s private window, an ad/tracker blocker, or the
              &ldquo;Do Not Track&rdquo; / tracking-protection setting. Nothing on this site requires analytics to work.
            </p>
          </div>
        </Card>

        <Card>
          <CardHeader title="How a chance label is decided"
                      subtitle="The label compares the first considered round's closing rank with your rank" />
          <div className="card-pad space-y-3">
            <ul className="space-y-2">
              {STATUS_ORDER.map((s) => (
                <li key={s} className="flex flex-wrap items-center gap-2 text-sm">
                  <StatusChip status={s} />
                  <span className="text-ink-soft">{STATUS_META[s].help}</span>
                </li>
              ))}
            </ul>
            <p className="text-sm text-ink-soft">
              Default thresholds (multiples of your rank):{' '}
              {Object.entries(meta.default_thresholds).map(([k, v]) => <Pill key={k}>{k} ≥ {v}×</Pill>)}.
              You can change them in the profile form.
            </p>
            <p className="text-sm text-ink-soft">
              <strong className="text-ink">Desirability</strong> mixes how early a branch and a college fill up
              (median Round-1 rank, all categories). It is a demand proxy – not teaching quality, workload, bond or fees.
            </p>
          </div>
        </Card>

        <Card>
          <CardHeader title="Eligibility rules used" subtitle="Which seat categories each candidate category can hold" />
          <div className="card-pad space-y-4">
            {years.map((y) => (
              <div key={y.year}>
                <h3 className="text-sm font-semibold">{y.label}</h3>
                <div className="mt-2 overflow-x-auto">
                  <table className="w-full border-collapse text-sm">
                    <thead className="bg-slate-50/80">
                      <tr>
                        <th scope="col" className="th">Candidate</th>
                        <th scope="col" className="th">Eligible seats</th>
                        <th scope="col" className="th">Source clause</th>
                        <th scope="col" className="th">Reviewed</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {Object.entries(y.eligibility).map(([cand, e]) => (
                        <tr key={cand}>
                          <td className="td font-medium">{catLabel(cand)}</td>
                          <td className="td"><span className="flex flex-wrap gap-1">{e.seat_categories.map((c) => <Pill key={c} tone="brand">{catLabel(c)}</Pill>)}</span></td>
                          <td className="td text-xs text-ink-soft">{e.clauses.join('; ')}<br />{e.source}</td>
                          <td className="td">{e.confirmed ? <Pill tone="brand">confirmed</Pill> : <Pill tone="amber">awaiting review</Pill>}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
            {unconfirmed.length ? (
              <Notice tone="warn">
                The rules for {unconfirmed.join(', ')} are drafted from the bulletins and match every allotment in the data,
                but they have not been reviewed yet. Predictions carry the same warning.
              </Notice>
            ) : null}
          </div>
        </Card>

        <Card>
          <CardHeader title="Quotas" subtitle="Only quotas with modelled eligibility can be predicted" />
          <div className="card-pad grid gap-3 sm:grid-cols-2">
            <div>
              <p className="text-sm font-medium">Supported in the predictor</p>
              <ul className="mt-1 space-y-1 text-sm text-ink-soft">
                {Object.entries(meta.supported_quotas).map(([k, v]) => <li key={k}><Pill tone="brand">{k}</Pill> {v}</li>)}
              </ul>
            </div>
            <div>
              <p className="text-sm font-medium">Data only (not predicted)</p>
              <ul className="mt-1 space-y-1 text-sm text-ink-soft">
                {Object.entries(meta.all_quotas).filter(([k]) => !(k in meta.supported_quotas))
                  .map(([k, v]) => <li key={k}><Pill>{k}</Pill> {v}</li>)}
              </ul>
              <p className="mt-2 text-xs text-ink-faint">
                These have extra conditions (NRI status, minority, Armed Forces, internal university quotas) that are not
                modelled, so the predictor refuses them instead of guessing. Their cut-offs are still browsable.
              </p>
            </div>
          </div>
        </Card>

        <Card>
          <CardHeader title="Limitations" />
          <ul className="card-pad list-disc space-y-2 pl-5 text-sm text-ink-soft">
            {meta.limitations.map((l) => <li key={l}>{l}</li>)}
          </ul>
        </Card>

        <Card>
          <CardHeader title="Source documents" subtitle={`${meta.sources.length} official PDFs, verified by SHA-256 checksum`} />
          <CardListView label="Source documents">
            {meta.sources.map((s) => (
              <RecordCard
                key={`m-${s.path}`}
                title={s.url ? (
                  <span className="text-brand-700">{s.title ?? s.path}</span>
                ) : (s.title ?? s.path)}
                href={s.url ?? undefined}
                external
                subtitle={s.path}
                badge={<Pill>{s.kind}</Pill>}
                fields={[
                  { label: 'Year', value: s.year ?? 'all years' },
                  { label: 'SHA-256', value: <span className="font-mono text-xs text-ink-faint">{s.sha256.slice(0, 12)}…</span> },
                ]}
              />
            ))}
          </CardListView>

          <TableView>
            <table className="w-full border-collapse">
              <thead className="bg-slate-50/80">
                <tr>
                  <th scope="col" className="th">Year</th>
                  <th scope="col" className="th">Kind</th>
                  <th scope="col" className="th">Document</th>
                  <th scope="col" className="th">Checksum</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {meta.sources.map((s) => (
                  <tr key={s.path}>
                    <td className="td">{s.year ?? 'all'}</td>
                    <td className="td"><Pill>{s.kind}</Pill></td>
                    <td className="td">
                      {s.url ? <a className="font-medium text-brand-700 hover:underline" href={s.url} target="_blank" rel="noreferrer">
                        {s.title ?? s.path}</a> : <span className="font-medium">{s.title ?? s.path}</span>}
                      <p className="text-xs text-ink-faint">{s.path}</p>
                    </td>
                    <td className="td font-mono text-xs text-ink-faint">{s.sha256.slice(0, 12)}…</td>
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
