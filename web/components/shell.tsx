'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import type { ReactNode } from 'react';
import {
  IconBranch, IconBuilding, IconDatabase, IconInfo, IconLayers, IconSearch, IconTable, IconTarget,
} from './icons';

const NAV = [
  { href: '/', label: 'Predictor', icon: IconTarget, hint: 'Your chances by college and course' },
  { href: '/colleges', label: 'Colleges', icon: IconBuilding, hint: 'Browse institutes' },
  { href: '/cutoffs', label: 'Cut-offs', icon: IconTable, hint: 'Raw round-wise cut-offs' },
  { href: '/branches', label: 'Branches', icon: IconBranch, hint: 'Demand per branch' },
  { href: '/about', label: 'Data & limits', icon: IconInfo, hint: 'Sources and caveats' },
];

function NavLinks({ pathname, onNavigate }: { pathname: string; onNavigate?: () => void }) {
  return (
    <ul className="space-y-1">
      {NAV.map(({ href, label, icon: Icon, hint }) => {
        const active = href === '/' ? pathname === '/' : pathname.startsWith(href);
        return (
          <li key={href}>
            <Link href={href} onClick={onNavigate} aria-current={active ? 'page' : undefined}
                  className={`nav-item ${active ? 'nav-item-active' : ''}`}>
              <Icon className="h-4 w-4 shrink-0" />
              <span className="flex-1">{label}</span>
              {active ? <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-brand-600" /> : null}
            </Link>
            <span className="sr-only">{hint}</span>
          </li>
        );
      })}
    </ul>
  );
}

export function Sidebar({ year, years, dataVersion }: { year: number; years: number[]; dataVersion: number }) {
  const pathname = usePathname();
  return (
    <>
      {/* desktop rail */}
      <aside className="no-print sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-slate-200 bg-white p-4 lg:flex">
        <Link href="/" className="flex items-center gap-2 px-1 py-1">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-brand-600 text-white">
            <IconLayers className="h-5 w-5" />
          </span>
          <span className="text-sm font-semibold leading-tight">
            NEET PG<br /><span className="text-ink-faint">Counselling Intelligence</span>
          </span>
        </Link>

        <form action="/colleges" className="mt-4">
          <label className="sr-only" htmlFor="sidebar-search">Search colleges</label>
          <div className="relative">
            <IconSearch className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-ink-faint" />
            <input id="sidebar-search" name="q" type="search" placeholder="Search colleges"
                   className="field pl-9" minLength={2} />
          </div>
        </form>

        <nav aria-label="Main" className="mt-4 flex-1">
          <NavLinks pathname={pathname} />
        </nav>

        <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50/80 p-3">
          <p className="flex items-center gap-2 text-xs font-semibold text-ink">
            <IconDatabase className="h-4 w-4 text-brand-600" /> Dataset
          </p>
          <p className="mt-1 text-xs text-ink-soft">
            Official MCC allotment results
            <br />Years loaded: {years.join(', ')}
            <br />Viewing: <strong className="text-ink">{year}</strong>
            <br />Import #{dataVersion}
          </p>
          <Link href="/about" className="mt-2 inline-block text-xs font-medium text-brand-700 hover:underline">
            Sources &amp; limitations
          </Link>
        </div>
      </aside>

      {/* mobile / tablet top bar */}
      <div className="no-print sticky top-0 z-20 border-b border-slate-200 bg-white/95 backdrop-blur lg:hidden">
        <div className="flex items-center gap-2 px-4 py-3">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand-600 text-white">
            <IconLayers className="h-4 w-4" />
          </span>
          <span className="text-sm font-semibold">NEET PG Counselling</span>
          <span className="ml-auto text-xs text-ink-faint">{year}</span>
        </div>
        <nav aria-label="Main" className="flex gap-1 overflow-x-auto px-2 pb-2">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = href === '/' ? pathname === '/' : pathname.startsWith(href);
            return (
              <Link key={href} href={href} aria-current={active ? 'page' : undefined}
                    className={`nav-item shrink-0 ${active ? 'nav-item-active' : ''}`}>
                <Icon className="h-4 w-4" />{label}
              </Link>
            );
          })}
        </nav>
      </div>
    </>
  );
}

export function PageHeader({ title, meta, actions, children }:
  { title: string; meta?: ReactNode; actions?: ReactNode; children?: ReactNode }) {
  return (
    <header className="mb-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          {meta ? <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-ink-soft">{meta}</div> : null}
        </div>
        {actions ? <div className="no-print flex flex-wrap items-center gap-2">{actions}</div> : null}
      </div>
      {children}
    </header>
  );
}
