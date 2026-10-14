import Link from 'next/link';
import type { Option, Sort } from '@/lib/api';
import { catLabel, num, rank as fmtRank } from '@/lib/format';
import type { SearchParams } from '@/lib/query';
import { patchUrl } from '@/lib/query';
import { SortSelect } from './sort-select';
import {
  Card, CardHeader, CardListView, EmptyState, MiniBar, Pagination, Pill, RecordCard, SortLink, StatusChip,
  TableView,
} from './ui';
import { IconDownload, IconPrint } from './icons';

/** Closing ranks for the rounds after the first, as used in both the table cell and the mobile card. */
function LaterRounds({ option }: { option: Option }) {
  if (option.rounds.length <= 1) return <span className="text-ink-faint">–</span>;
  return (
    <ul className="space-y-0.5 text-xs text-ink-soft">
      {option.rounds.slice(1).map((rc) => (
        <li key={rc.round}>
          <span className="text-ink-faint">{rc.round}:</span> {fmtRank(rc.best_close)}
          {rc.best_category ? ` (${catLabel(rc.best_category)})` : ''}
        </li>
      ))}
    </ul>
  );
}

function Desirability({ option }: { option: Option }) {
  return (
    <>
      <div className="flex items-center gap-2">
        <MiniBar value={option.desirability} max={100} />
        <span className="text-xs font-medium tabular-nums">{option.desirability.toFixed(0)}</span>
      </div>
      {option.branch_median_air ? (
        <p className="mt-1 text-xs text-ink-faint">branch median AIR {fmtRank(Math.round(option.branch_median_air))}</p>
      ) : null}
    </>
  );
}

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
        /* Stacked on a phone: sharing one row truncated the sort labels to "Most in-deman…". */
        actions={
          <div className="flex w-full flex-col gap-2 sm:flex-row sm:items-end">
            <SortSelect sp={sp} value={sort} options={sortOptions} />
            <Link className="btn-ghost" href={`/export${patchUrl(sp, { offset: undefined, limit: undefined })}`}>
              <IconDownload className="h-4 w-4" /> Export CSV
            </Link>
          </div>
        }
      />
      {options.length === 0 ? (
        <EmptyState title="No options match these filters">
          Try removing a branch or state filter, including more rounds, or adding the Reach classification.
        </EmptyState>
      ) : (
        <>
          {/* Phones and small tablets: one card per option. Same data, no sideways scrolling. */}
          <CardListView label={`Matching options for AIR ${myRank}`}>
            {options.map((o) => (
              <RecordCard
                key={`m-${o.institute.id}-${o.course.id}`}
                title={o.institute.short_name}
                href={`/colleges/${o.institute.id}`}
                subtitle={`${o.institute.state ?? 'State not in address'}${
                  o.institute_median_air ? ` · median AIR ${fmtRank(Math.round(o.institute_median_air))}` : ''}`}
                badge={<StatusChip status={o.status} withHelp />}
                fields={[
                  {
                    label: 'Course', wide: true,
                    value: (
                      <>
                        <span className="font-medium">{o.course.branch}</span>
                        <span className="ml-2 inline-flex flex-wrap items-center gap-1 text-xs text-ink-faint">
                          <Pill>{o.course.degree}</Pill>
                          <span title={o.course.name}>{o.course.code}</span>
                        </span>
                      </>
                    ),
                  },
                  {
                    label: `${firstRound} closing`,
                    value: (
                      <>
                        <span className="font-medium tabular-nums">{fmtRank(o.rounds[0]?.best_close ?? null)}</span>
                        {o.rounds[0]?.best_category ? (
                          <p className="text-xs text-ink-faint">{catLabel(o.rounds[0].best_category!)} seat</p>
                        ) : null}
                        {o.ratio_first_round != null ? (
                          <p className="text-xs text-ink-faint">{o.ratio_first_round.toFixed(2)}× your rank</p>
                        ) : null}
                      </>
                    ),
                  },
                  { label: 'Later rounds', value: <LaterRounds option={o} /> },
                  { label: 'Desirability', value: <Desirability option={o} />, wide: true },
                ]}
              >
                <details className="mt-2">
                  <summary className="summary-tap px-0 text-xs font-medium text-brand-700">Why this label?</summary>
                  <p className="text-xs text-ink-soft">{o.reason}</p>
                </details>
              </RecordCard>
            ))}
          </CardListView>

          <TableView>
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
                      <td className="td"><LaterRounds option={o} /></td>
                      <td className="td"><Desirability option={o} /></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </TableView>
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
