'use client';

import { useEffect, useState } from 'react';
import type { Sort } from '@/lib/api';
import type { SearchParams } from '@/lib/query';

/**
 * Sort dropdown for the results table.
 *
 * It is a real GET form carrying the current filters as hidden fields, so it works without JavaScript
 * (the "Apply" button submits it). When JavaScript is available the button is dropped and changing the
 * dropdown submits immediately.
 */
export function SortSelect({ sp, value, options }:
  { sp: SearchParams; value: Sort; options: Record<string, string> }) {
  const [enhanced, setEnhanced] = useState(false);
  useEffect(() => setEnhanced(true), []);

  // every current param except the ones this form owns
  const hidden: [string, string][] = [];
  for (const [k, v] of Object.entries(sp)) {
    if (k === 'sort' || k === 'offset') continue;
    for (const one of Array.isArray(v) ? v : v === undefined ? [] : [v]) hidden.push([k, one]);
  }

  return (
    <form method="get" action="/" className="flex items-end gap-2">
      {hidden.map(([k, v], i) => <input key={`${k}-${i}`} type="hidden" name={k} value={v} />)}
      <div>
        <label className="label" htmlFor="sort">Sort by</label>
        <select
          id="sort"
          name="sort"
          defaultValue={value}
          className="field min-w-[15rem] py-1.5"
          onChange={(e) => { if (enhanced) e.currentTarget.form?.requestSubmit(); }}
        >
          {Object.entries(options).map(([k, label]) => <option key={k} value={k}>{label}</option>)}
        </select>
      </div>
      {!enhanced ? <button type="submit" className="btn-ghost">Apply</button> : null}
    </form>
  );
}
