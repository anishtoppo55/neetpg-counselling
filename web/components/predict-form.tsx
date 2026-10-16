import type { BranchInfo, Meta, Status, YearInfo } from '@/lib/api';
import { STATUS_ORDER } from '@/lib/api';
import { STATUS_META, catLabel } from '@/lib/format';
import type { Query } from '@/lib/query';
import { DEFAULT_THRESHOLDS } from '@/lib/query';
import { Card, CardHeader, Pill } from './ui';
import { IconFilter, IconTarget } from './icons';

/**
 * Plain HTML GET form: no client JavaScript needed, and the resulting URL is shareable/bookmarkable.
 * Checkbox groups submit repeated params (?branches=A&branches=B).
 */
export function PredictForm({ q, meta, years, branches, states, yearInUse }: {
  q: Query; meta: Meta; years: YearInfo[]; branches: BranchInfo[]; states: { state: string | null }[]; yearInUse: number;
}) {
  const b = q.body;
  const selected = (arr: string[] | undefined, v: string) => arr?.includes(v) ?? false;
  const yearInfo = years.find((y) => y.year === yearInUse);
  const roundsOfYear = yearInfo?.rounds ?? [];
  const chosenRounds = b.rounds ?? roundsOfYear.filter((r) => r.kind === 'regular').map((r) => r.code);

  return (
    <Card className="no-print">
      <CardHeader
        title={<span className="flex items-center gap-2"><IconTarget className="h-4 w-4 text-brand-600" /> Your profile</span>}
        subtitle="Historical cut-offs are matched to this profile. No account, and it is never saved on the server."
        actions={<>
          <button type="submit" form="predict-form" className="btn-primary">Show my options</button>
          <a href="/" className="btn-ghost">Reset</a>
        </>}
      />
      <form id="predict-form" method="get" action="/" className="card-pad space-y-4">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <label className="label" htmlFor="rank">All India Rank <span className="text-rose-600">*</span></label>
            <input className="field" id="rank" name="rank" type="number" min={1} max={1000000} required
                   inputMode="numeric" defaultValue={b.rank || ''} placeholder="e.g. 30000" />
          </div>
          <div>
            <label className="label" htmlFor="category">Category <span className="text-rose-600">*</span></label>
            <select className="field" id="category" name="category" defaultValue={b.category} required>
              {Object.keys(meta.candidate_categories).map((c) => (
                <option key={c} value={c}>{catLabel(c)}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="quota">Quota</label>
            <select className="field" id="quota" name="quota" defaultValue={b.quota}>
              {Object.entries(meta.supported_quotas).map(([k, v]) => <option key={k} value={k}>{k} – {v}</option>)}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="year">Counselling year</label>
            <select className="field" id="year" name="year" defaultValue={String(yearInUse)}>
              {years.map((y) => <option key={y.year} value={y.year}>{y.label}</option>)}
            </select>
          </div>
        </div>

        <fieldset>
          <legend className="label">Rounds to consider <span className="font-normal text-ink-faint">(status is based on the first)</span></legend>
          <div className="flex flex-wrap gap-2">
            {roundsOfYear.map((r) => (
              <label key={r.code} className="check">
                <input type="checkbox" name="rounds" value={r.code} defaultChecked={chosenRounds.includes(r.code)}
                       className="check-box" />
                {r.name}{r.kind === 'stray' ? <Pill tone="amber">stray</Pill> : null}
              </label>
            ))}
          </div>
        </fieldset>

        <details className="rounded-xl border border-slate-200 bg-slate-50/60" open={Boolean(b.branches || b.states || b.groups || b.degrees)}>
          <summary className="summary-tap">
            <span className="inline-flex flex-wrap items-center gap-2"><IconFilter className="h-4 w-4" /> Preferences
              {b.branches?.length || b.states?.length ? <Pill tone="brand">{(b.branches?.length ?? 0) + (b.states?.length ?? 0)} selected</Pill> : null}
            </span>
          </summary>
          <div className="space-y-4 border-t border-slate-200 p-3">
            <CheckGroup legend="Course group" name="groups" values={meta.groups} selected={b.groups}
                        hint="Leave empty for all. Clinical covers the patient-facing branches." />
            <CheckGroup legend="Degree" name="degrees" values={meta.degrees} selected={b.degrees} />
            <CheckGroup legend="Branch" name="branches" values={branches.map((x) => x.branch)} selected={b.branches} columns />
            <CheckGroup legend="State" name="states" values={states.map((s) => s.state).filter((s): s is string => Boolean(s))}
                        selected={b.states} columns />
          </div>
        </details>

        <details className="rounded-xl border border-slate-200 bg-slate-50/60" open={q.thresholdsChanged}>
          <summary className="summary-tap gap-2">
            Classification thresholds {q.thresholdsChanged ? <Pill tone="amber">customised</Pill> : null}
          </summary>
          <div className="border-t border-slate-200 p-3">
            <p className="mb-3 text-xs text-ink-soft">
              Multiples of your rank, compared with the first considered round&rsquo;s closing rank.
              Defaults: {DEFAULT_THRESHOLDS.safe}× / {DEFAULT_THRESHOLDS.good}× / {DEFAULT_THRESHOLDS.borderline}× / {DEFAULT_THRESHOLDS.reach}×.
            </p>
            <div className="grid gap-3 sm:grid-cols-4">
              {([['t_safe', 'Safe ≥', b.thresholds!.safe], ['t_good', 'Good ≥', b.thresholds!.good],
                 ['t_borderline', 'Borderline ≥', b.thresholds!.borderline], ['t_reach', 'Reach ≥', b.thresholds!.reach]] as const)
                .map(([name, label, val]) => (
                <div key={name}>
                  <label className="label" htmlFor={name}>{label}</label>
                  <input className="field" id={name} name={name} type="number" step="0.05" min="0.05" max="20" defaultValue={val} />
                </div>
              ))}
            </div>
            <div className="mt-3 max-w-xs">
              <label className="label" htmlFor="branch_weight">Branch vs college weight in desirability</label>
              <input className="field" id="branch_weight" name="branch_weight" type="number" step="0.1" min="0" max="1"
                     defaultValue={b.branch_weight} />
            </div>
          </div>
        </details>

        <fieldset>
          <legend className="label">Show classifications</legend>
          <div className="flex flex-wrap gap-2">
            {STATUS_ORDER.map((s) => (
              <label key={s} className="check" title={STATUS_META[s].help}>
                <input type="checkbox" name="statuses" value={s} defaultChecked={q.statuses.includes(s as Status)}
                       className="check-box" />
                <span aria-hidden="true" className="h-2 w-2 shrink-0 rounded-full" style={{ background: STATUS_META[s].color }} />
                {STATUS_META[s].label}
              </label>
            ))}
          </div>
        </fieldset>

        <input type="hidden" name="sort" value={q.sort} />
        <div className="flex flex-wrap items-center gap-2 pt-1">
          <button type="submit" className="btn-primary">Show my options</button>
          <p className="text-xs text-ink-faint">Historical estimate from official MCC results – not a guarantee of admission.</p>
        </div>
      </form>
    </Card>
  );
}

function CheckGroup({ legend, name, values, selected, hint, columns = false }: {
  legend: string; name: string; values: string[]; selected?: string[]; hint?: string; columns?: boolean;
}) {
  return (
    <fieldset>
      <legend className="label">{legend}</legend>
      {hint ? <p className="mb-1 text-xs text-ink-faint">{hint}</p> : null}
      {/* The long lists (branch, state) keep their own scroll area, taller on a phone so the rows can be
          finger-sized without the box swallowing the page. */}
      <div className={columns ? 'grid max-h-64 gap-1 overflow-y-auto overscroll-contain rounded-lg border border-slate-200 bg-white p-2 sm:max-h-48 sm:grid-cols-2 lg:grid-cols-3'
                              : 'flex flex-wrap gap-2'}>
        {values.map((v) => (
          <label key={v} className="check-row">
            <input type="checkbox" name={name} value={v} defaultChecked={selected?.includes(v) ?? false}
                   className="check-box" />
            <span className="truncate" title={v}>{v}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
