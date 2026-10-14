'use client';

import { useEffect, useState } from 'react';
import {
  Bar, BarChart, Cell, Legend, Line, LineChart, Pie, PieChart, ReferenceLine, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts';
import { STATUS_META, nf } from '@/lib/format';
import type { Status } from '@/lib/api';

const axis = { stroke: '#94a3b8', fontSize: 11 };

/**
 * Recharts needs pixel numbers for axis widths, which CSS breakpoints cannot supply. A 150 px category
 * axis on a 390 px screen left under 200 px for the bars themselves, so the widths are chosen here.
 *
 * Starts `false` so the server-rendered markup is the narrow layout, then upgrades after mount; that keeps
 * hydration consistent and means a phone never briefly renders the desktop sizing.
 */
function useIsWide(query = '(min-width: 640px)') {
  const [wide, setWide] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia(query);
    setWide(mq.matches);
    const onChange = (e: MediaQueryListEvent) => setWide(e.matches);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, [query]);
  return wide;
}

/** Keeps long branch names from being clipped to nothing on a narrow category axis. */
const clip = (max: number) => (v: string) => (v.length > max ? `${v.slice(0, max - 1)}…` : v);

const compactRank = (v: number) => (v >= 1000 ? `${Math.round(v / 1000)}k` : String(v));
const tooltipStyle = {
  contentStyle: { borderRadius: 12, border: '1px solid #e2e8f0', boxShadow: '0 12px 32px -12px rgba(15,23,42,.28)', fontSize: 12 },
  labelStyle: { color: '#0f172a', fontWeight: 600 },
};

/** Donut of options per classification, with the achievable share in the middle. */
export function StatusDonut({ data, achievableShare }:
  { data: { status: Status; label: string; value: number }[]; achievableShare: number }) {
  const total = data.reduce((s, d) => s + d.value, 0);
  return (
    <div className="flex flex-col items-center gap-4 sm:flex-row">
      <div className="h-52 w-full sm:w-1/2">
        <ResponsiveContainer>
          <PieChart>
            <Pie data={data} dataKey="value" nameKey="label" innerRadius="62%" outerRadius="100%" paddingAngle={2}
                 strokeWidth={0} isAnimationActive={false}>
              {data.map((d) => <Cell key={d.status} fill={STATUS_META[d.status].color} />)}
            </Pie>
            <Tooltip {...tooltipStyle} formatter={(v: number, n) => [`${nf.format(v)} options`, n as string]} />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <ul className="w-full space-y-2 sm:w-1/2">
        <li className="mb-3">
          <p className="text-2xl font-semibold">{Math.round(achievableShare * 100)}%</p>
          <p className="text-xs text-ink-soft">of {nf.format(total)} options are Safe, Good, Borderline or Later-round</p>
        </li>
        {data.filter((d) => d.value > 0).map((d) => (
          <li key={d.status} className="flex items-center gap-2 text-sm">
            <span aria-hidden="true" className="h-2.5 w-2.5 rounded-sm" style={{ background: STATUS_META[d.status].color }} />
            <span className="flex-1 text-ink-soft">{d.label}</span>
            <span className="font-medium">{nf.format(d.value)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Stacked bars: achievable options per branch (one bar per branch, segments per classification). */
export function BranchStack({ data, statuses }:
  { data: { branch: string; [k: string]: number | string }[]; statuses: Status[] }) {
  const wide = useIsWide();
  return (
    <div className="h-80 w-full sm:h-72">
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" margin={{ left: 0, right: 12, top: 4, bottom: 4 }}>
          <XAxis type="number" {...axis} allowDecimals={false} />
          <YAxis type="category" dataKey="branch" width={wide ? 150 : 88} {...axis} interval={0}
                 tickFormatter={wide ? undefined : clip(13)} />
          <Tooltip {...tooltipStyle} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          {statuses.map((s) => (
            <Bar key={s} dataKey={s} name={STATUS_META[s].label} stackId="a" fill={STATUS_META[s].color}
                 radius={[0, 4, 4, 0]} isAnimationActive={false} maxBarSize={18} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Closing rank per round for one seat group, with the candidate's rank as a reference line. */
export function RoundTrend({ data, myRank, series }:
  { data: Record<string, number | string | null>[]; myRank?: number; series: { key: string; name: string; color: string }[] }) {
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ left: 0, right: 12, top: 8, bottom: 4 }}>
          <XAxis dataKey="round" {...axis} />
          <YAxis {...axis} width={44} tickFormatter={compactRank} />
          <Tooltip {...tooltipStyle} formatter={(v: number) => nf.format(v)} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          {myRank ? (
            <ReferenceLine y={myRank} stroke="#e11d48" strokeDasharray="4 4"
                           label={{ value: `Your rank ${nf.format(myRank)}`, fontSize: 11, fill: '#e11d48', position: 'insideTopRight' }} />
          ) : null}
          {series.map((s) => (
            <Line key={s.key} type="monotone" dataKey={s.key} name={s.name} stroke={s.color} strokeWidth={2}
                  dot={{ r: 3 }} connectNulls isAnimationActive={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Horizontal bars of branch demand (median AIR in round 1). */
export function DemandBars({ data }: { data: { branch: string; median: number; p25: number }[] }) {
  const wide = useIsWide();
  return (
    <div style={{ height: Math.max(240, data.length * (wide ? 22 : 26)) }} className="w-full">
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" margin={{ left: 0, right: wide ? 24 : 12, top: 4, bottom: 4 }}>
          <XAxis type="number" {...axis} tickFormatter={compactRank} />
          <YAxis type="category" dataKey="branch" width={wide ? 170 : 96} {...axis} interval={0}
                 tickFormatter={wide ? undefined : clip(14)} />
          <Tooltip {...tooltipStyle} formatter={(v: number, n) => [nf.format(v), n === 'median' ? 'Median AIR' : '25th percentile AIR']} />
          <Bar dataKey="median" name="median" fill="#4f46e5" radius={[0, 4, 4, 0]} isAnimationActive={false} maxBarSize={14} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
