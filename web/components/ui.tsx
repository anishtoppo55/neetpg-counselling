import Link from 'next/link';
import type { ReactNode } from 'react';
import type { Status } from '@/lib/api';
import { STATUS_META, nf } from '@/lib/format';
import { IconArrowRight, IconDown, IconUp } from './icons';

/* ----------------------------------------------------------------- card */
export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`card ${className}`}>{children}</section>;
}

export function CardHeader({ title, subtitle, actions, id }:
  { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode; id?: string }) {
  return (
    <header className="flex flex-col gap-3 border-b border-slate-100 px-4 py-4 sm:flex-row sm:flex-wrap
                       sm:items-start sm:justify-between sm:px-5">
      <div className="min-w-0">
        <h2 id={id} className="text-base font-semibold text-ink">{title}</h2>
        {subtitle ? <p className="mt-0.5 text-sm text-ink-soft">{subtitle}</p> : null}
      </div>
      {/* Stacked and full width on a phone; inline from sm up. */}
      {actions ? (
        <div className="flex flex-wrap items-end gap-2 [&>*]:flex-1 sm:[&>*]:flex-none">{actions}</div>
      ) : null}
    </header>
  );
}

/* ----------------------------------------------------------------- KPI tile */
export function KpiCard({ icon, label, value, hint, delta, tone = 'brand' }: {
  icon: ReactNode; label: string; value: ReactNode; hint?: ReactNode;
  delta?: { text: string; dir: 'up' | 'down' | 'flat' }; tone?: 'brand' | 'green' | 'amber' | 'violet';
}) {
  const tones: Record<string, string> = {
    brand: 'bg-brand-600 text-white', green: 'bg-green-600 text-white',
    amber: 'bg-amber-500 text-white', violet: 'bg-violet-600 text-white',
  };
  return (
    <Card className="card-pad">
      <div className="flex items-start justify-between">
        <span className={`grid h-9 w-9 place-items-center rounded-xl sm:h-10 sm:w-10 ${tones[tone]}`}>{icon}</span>
      </div>
      {/* Two tiles fit side by side on a phone, so the label and value step down a size there. */}
      <p className="mt-3 text-xs text-ink-soft sm:mt-4 sm:text-sm">{label}</p>
      <div className="mt-1 flex flex-wrap items-center gap-2">
        <span className="text-xl font-semibold tracking-tight sm:text-2xl">{value}</span>
        {delta ? (
          <span className={`chip ${delta.dir === 'down' ? 'bg-rose-50 text-rose-600' : 'bg-green-50 text-green-700'}`}>
            {delta.dir === 'up' ? <IconUp className="h-3 w-3" /> : delta.dir === 'down' ? <IconDown className="h-3 w-3" /> : null}
            {delta.text}
          </span>
        ) : null}
      </div>
      {hint ? <p className="mt-1 text-xs text-ink-faint">{hint}</p> : null}
    </Card>
  );
}

/* ----------------------------------------------------------------- chips */
export function StatusChip({ status, withHelp = false }: { status: Status; withHelp?: boolean }) {
  const m = STATUS_META[status];
  return (
    <span className={`chip ${m.chip}`} title={withHelp ? m.help : undefined}>
      <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full" style={{ background: m.color }} />
      {m.label}
    </span>
  );
}

export function Pill({ children, tone = 'slate' }: { children: ReactNode; tone?: 'slate' | 'brand' | 'amber' }) {
  const tones = {
    slate: 'bg-slate-100 text-ink-soft', brand: 'bg-brand-50 text-brand-700', amber: 'bg-amber-50 text-amber-700',
  } as const;
  return <span className={`chip ${tones[tone]}`}>{children}</span>;
}

/* ----------------------------------------------------------------- notices */
export function Notice({ children, tone = 'info' }: { children: ReactNode; tone?: 'info' | 'warn' }) {
  const tones = {
    info: 'bg-brand-50/70 text-brand-900 border-brand-100',
    warn: 'bg-amber-50 text-amber-900 border-amber-200',
  } as const;
  return <div className={`rounded-xl border px-3 py-2 text-sm ${tones[tone]}`}>{children}</div>;
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="px-5 py-12 text-center">
      <p className="text-sm font-medium text-ink">{title}</p>
      {children ? <p className="mx-auto mt-1 max-w-prose text-sm text-ink-soft">{children}</p> : null}
    </div>
  );
}

/* ----------------------------------------------------------------- table bits */
export function SortLink({ href, active, children }: { href: string; active?: boolean; children: ReactNode }) {
  return (
    <Link href={href} className={`inline-flex items-center gap-1 hover:text-ink ${active ? 'text-brand-700' : ''}`}>
      {children}
      <svg aria-hidden="true" viewBox="0 0 24 24" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M8 10l4-4 4 4M8 14l4 4 4-4" />
      </svg>
    </Link>
  );
}

export function Pagination({ total, limit, offset, makeHref, label = 'results' }:
  { total: number; limit: number; offset: number; makeHref: (offset: number) => string; label?: string }) {
  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + limit, total);
  const prev = Math.max(0, offset - limit);
  const next = offset + limit;
  return (
    <nav aria-label="Pagination" className="flex flex-col gap-3 border-t border-slate-100 px-4 py-3
                                            sm:flex-row sm:flex-wrap sm:items-center sm:justify-between sm:px-5">
      <p className="text-xs text-ink-soft" aria-live="polite">
        {nf.format(from)}–{nf.format(to)} of {nf.format(total)} {label}
      </p>
      {/* Equal-width, thumb-sized buttons on a phone. */}
      <div className="flex items-center gap-2 [&>*]:flex-1 sm:[&>*]:flex-none">
        {offset > 0 ? <Link className="btn-ghost" href={makeHref(prev)}>Previous</Link>
          : <span className="btn-ghost pointer-events-none opacity-40" aria-hidden="true">Previous</span>}
        {next < total ? <Link className="btn-ghost" href={makeHref(next)}>Next <IconArrowRight className="h-3.5 w-3.5" /></Link>
          : <span className="btn-ghost pointer-events-none opacity-40" aria-hidden="true">Next</span>}
      </div>
    </nav>
  );
}

/* ----------------------------------------------------------------- responsive data presentation
 * These tables carry 6–8 columns of numbers. Horizontally scrolling them on a 390 px screen hides the
 * row label as soon as you scroll, which makes the numbers meaningless. So below `lg` each row is
 * re-rendered as a stacked card instead, and the real <table> is kept for wider screens where it is the
 * better tool. Pages render both and let CSS pick one, which keeps everything server-rendered.
 */

/**
 * Wraps a real <table>; visible from `lg` up only.
 *
 * `relative` is load-bearing. These tables contain `sr-only` helpers (`<span class="sr-only">Open</span>`
 * in a header cell, the table <caption>), and `sr-only` is `position: absolute`. A static-positioned
 * scroll container is not their containing block, so it cannot clip them: they resolved against the
 * document instead and sat at the table's far-right edge, stretching the page's scrollWidth by a few
 * hundred pixels and giving the whole document a horizontal scrollbar. Making this the containing block
 * keeps them inside the scroll area.
 */
export function TableView({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`relative hidden overflow-x-auto xl:block ${className}`}>{children}</div>;
}

/**
 * Wraps the stacked cards shown instead of the table below `xl`.
 *
 * The switch is at `xl` (1280px), not `lg`, because `lg` is also where the 256px desktop rail appears:
 * at 1024px that leaves 768px of content for tables that want ~1125px, so the table would scroll
 * sideways exactly where the cards are the better answer. Landscape tablets land in this band.
 */
export function CardListView({ children, label }: { children: ReactNode; label?: string }) {
  return <ul aria-label={label} className="divide-y divide-slate-100 xl:hidden">{children}</ul>;
}

export type RecordField = { label: string; value: ReactNode; wide?: boolean };

/**
 * One record as a card: a title (optionally a link), an optional subtitle and badge, then the remaining
 * columns as a two-up definition list.
 */
export function RecordCard({ title, href, external = false, subtitle, badge, fields, action, children }: {
  title: ReactNode; href?: string; external?: boolean; subtitle?: ReactNode; badge?: ReactNode;
  fields?: RecordField[]; action?: ReactNode; children?: ReactNode;
}) {
  // `.row-title` grows to a 44px touch target on coarse pointers only (see globals.css).
  const titleClass = 'row-title';
  return (
    <li className="p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          {href && external ? (
            <a href={href} target="_blank" rel="noreferrer" className={titleClass}>{title}</a>
          ) : href ? (
            <Link href={href} className={titleClass}>{title}</Link>
          ) : <p className="text-sm font-medium text-ink">{title}</p>}
          {subtitle ? <p className="mt-0.5 text-xs text-ink-faint">{subtitle}</p> : null}
        </div>
        {badge ? <div className="shrink-0">{badge}</div> : null}
      </div>
      {fields?.length ? (
        <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-3">
          {fields.map((f) => (
            <div key={f.label} className={f.wide ? 'col-span-2' : undefined}>
              <dt className="dt">{f.label}</dt>
              <dd className="dd">{f.value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      {children}
      {action ? <div className="mt-3 flex [&>*]:flex-1">{action}</div> : null}
    </li>
  );
}

/** Small horizontal bar used inside table cells and summary lists. */
export function MiniBar({ value, max, color = '#4f46e5' }: { value: number; max: number; color?: string }) {
  const w = max > 0 ? Math.max(2, Math.round((value / max) * 100)) : 0;
  return (
    <span className="inline-block h-1.5 w-full max-w-[120px] overflow-hidden rounded-full bg-slate-100 align-middle">
      <span className="block h-full rounded-full" style={{ width: `${w}%`, background: color }} />
    </span>
  );
}
