import Link from 'next/link';
import type { Option, Sort } from '@/lib/api';
import { catLabel, num, rank as fmtRank } from '@/lib/format';
import type { SearchParams } from '@/lib/query';
import { patchUrl } from '@/lib/query';
import { SortSelect } from './sort-select';
import { Card, CardHeader, EmptyState, MiniBar, Pagination, Pill, SortLink, StatusChip } from './ui';
import { IconDownload, IconPrint } from './icons';

export function ResultsTable({ options, total, limit, offset, sort, sortOptions, sp, myRank, roundCodes }: {
  options: Option[]; total: number; limit: number; offset: number;
  sort: Sort; sortOptions: Record<string, string>; sp: SearchParams; myRank: number; roundCodes: string[];
}) {
  const firstRound = roundCodes[0];
  return (
    <Card>
      <CardHeader
        id="results"
        title="Matching options"
        subtitle={`${num(total)} college × course options · ${sortOptions[sort] ?? sort}`}
        actions={<>
          <SortSelect sp={sp} value={sort} options={sortOptions} />
          <Link className="btn-ghost" href={`/export${patchUrl(sp, { offset: undefined, limit: undefined })}`}>
            <IconDownload className="h-4 w-4" /> Export CSV
          </Link>
        </>}
      />
      {options.length === 0 ? (
        <EmptyState title="No options match these filters">
          Try removing a branch or state filter, including more rounds, or adding the Reach classification.
        </EmptyState>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <caption className="sr-only">
                Historical college and course options for AIR {myRank}, with classification, closing ranks per round and desirability.
              </caption>
              <thead className="bg-slate-50/80">
                <tr>
                  <th scope="col" className="th">College</th>
                  <th scope="col" className="th">Course</th>
                  <th scope="col" className="th">Chance</th>
                  <th scope="col" className="th">
                    <SortLink active={sort.startsWith('closing_rank')}
                              href={patchUrl(sp, { sort: sort === 'closing_rank_desc' ? 'closing_rank_asc' : 'closing_rank_desc', offset: 0 })}>
                      {firstRound} closing
                    </SortLink>
                  </th>
                  <th scope="col" className="th">Later rounds</th>
                  <th scope="col" className="th">
                    <SortLink href={patchUrl(sp, { sort: 'desirability', offset: 0 })} active={sort === 'desirability'}>
                      Desirability
                    </SortLink>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {options.map((o) => {
                  const r1 = o.rounds[0];
                  return (
                    <tr key={`${o.institute.id}-${o.course.id}`} className="hover:bg-slate-50/60">
                      <td className="td">
                        <Link href={`/colleges/${o.institute.id}`} className="font-medium text-ink hover:text-brand-700">
                          {o.institute.short_name}
                        </Link>
                        <p className="mt-0.5 text-xs text-ink-faint">
                          {o.institute.state ?? 'State not in address'}
                          {o.institute_median_air ? ` · median AIR ${fmtRank(Math.round(o.institute_median_air))}` : ''}
                        </p>
                      </td>
                      <td className="td">
                        <p className="font-medium text-ink">{o.course.branch}</p>
                        <p className="mt-0.5 flex flex-wrap items-center gap-1 text-xs text-ink-faint">
                          <Pill>{o.course.degree}</Pill>
                          <span className="truncate" title={o.course.name}>{o.course.code}</span>
                        </p>
                      </td>
                      <td className="td">
                        <StatusChip status={o.status} withHelp />
                        <details className="mt-1 max-w-xs">
                          <summary className="cursor-pointer text-xs text-brand-700">Why?</summary>
                          <p className="mt-1 text-xs text-ink-soft">{o.reason}</p>
                        </details>
                      </td>
                      <td className="td">
                        <span className="font-medium">{fmtRank(r1?.best_close ?? null)}</span>
                        {r1?.best_category ? <p className="text-xs text-ink-faint">{catLabel(r1.best_category)} seat</p> : null}
                        {o.ratio_first_round != null ? (
                          <p className="text-xs text-ink-faint">{o.ratio_first_round.toFixed(2)}× your rank</p>
                        ) : null}
                      </td>
                      <td className="td">
                        <ul className="space-y-0.5 text-xs text-ink-soft">
                          {o.rounds.slice(1).map((rc) => (
                            <li key={rc.round}>
                              <span className="text-ink-faint">{rc.round}:</span> {fmtRank(rc.best_close)}
                              {rc.best_category ? ` (${catLabel(rc.best_category)})` : ''}
                            </li>
                          ))}
                          {o.rounds.length <= 1 ? <li className="text-ink-faint">–</li> : null}
                        </ul>
                      </td>
                      <td className="td">
                        <div className="flex items-center gap-2">
                          <MiniBar value={o.desirability} max={100} />
                          <span className="text-xs font-medium tabular-nums">{o.desirability.toFixed(0)}</span>
                        </div>
                        {o.branch_median_air ? (
                          <p className="mt-1 text-xs text-ink-faint">branch median AIR {fmtRank(Math.round(o.branch_median_air))}</p>
                        ) : null}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <Pagination total={total} limit={limit} offset={offset} label="options"
                      makeHref={(o) => `${patchUrl(sp, { offset: o })}#results`} />
          <div className="no-print flex items-center gap-2 border-t border-slate-100 px-4 py-3 text-xs text-ink-faint sm:px-5">
            <IconPrint className="h-3.5 w-3.5" />
            Use your browser&rsquo;s print function to keep a copy. This list is a personal research aid, not an official MCC choice list.
          </div>
        </>
      )}
    </Card>
  );
}
