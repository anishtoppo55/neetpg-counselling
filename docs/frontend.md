# Frontend (Milestone 3)

Next.js 14 (App Router) + TypeScript + Tailwind, served by the `web` service at **http://127.0.0.1:3000**.
It reads the predictor API only — it never touches PostgreSQL.

```bash
docker compose up -d web            # starts db + api too
docker compose exec -T web npx tsc --noEmit     # type check
docker compose exec -T web npx next lint        # lint
docker compose exec -T web npx next build       # production build check
```

Note: `next build` overwrites the `.next` cache the dev server is using, so run
`docker compose restart web` afterwards.

## Pages

| Route | Purpose |
|---|---|
| `/` | **Predictor dashboard.** Profile form, KPI row, charts, and the classified options table |
| `/colleges` | Searchable institute list (name, state, branch, quota, year) |
| `/colleges/[id]` | One college: closing rank per round chart, all courses × rounds table, Round-1 seats offered |
| `/cutoffs` | Raw cut-off explorer with filters and a closing-rank range |
| `/branches` | Branch demand: median and 25th-percentile Round-1 rank, seats, degrees |
| `/about` | Chance-label rules, eligibility rules per year with sources, quotas, limitations, source PDFs with checksums |
| `/export?…` | CSV of the current prediction (all matching options, with a provenance header) |
| `/api/ping` | Liveness probe for the container healthcheck |

## Design

The layout follows the supplied reference dashboard:

* **Left rail** (desktop) with logo tile, college search, nav with the active item highlighted, and a dataset card
  showing the years loaded and the import number. On smaller screens it collapses into a scrollable top nav.
* **Page header** with the title, a meta row (year · quota · category · rounds) and actions on the right.
* **KPI cards**: coloured icon tile, label, large value, and a hint line — Achievable options, Safe,
  Good + Borderline, Later-round.
* **Two-panel row**: a stacked horizontal bar chart of branches by chance label, and a donut of the chance
  breakdown with the achievable share in the middle.
* **Card table** with a **sort dropdown** (eight orderings), sortable column headers, chance chips, per-round
  closing ranks, a desirability bar and an expandable *Why?* row.

Tailwind theme: light slate page (`#eef1f6`), white cards with soft shadows, indigo primary, and a fixed colour per
chance label (`lib/format.ts` → `STATUS_META`) that is reused by chips, charts and legends.

## How state works

**The URL is the only state.** The profile form is a plain HTML `GET` form, so:

* results are shareable and bookmarkable, e.g.
  `/?rank=30000&category=ST&quota=AI&year=2025&groups=Clinical&degrees=MD%2FMS`
* the back button, pagination and the sort dropdown work without client-side state
* the page renders on the server and works with JavaScript disabled (except the two charts)

`lib/query.ts` parses search params into a predictor request; `lib/api.ts` is the typed API client. Server components
call the API over the Docker network (`API_BASE_INTERNAL`), the browser uses `NEXT_PUBLIC_API_BASE`.

## Sorting

The results card has a **Sort by** dropdown with the orderings the API supports: desirability, best chance,
closing rank (relaxed or competitive first), branch demand, college demand, college A–Z and branch A–Z.

It is a real `GET` form that carries the current filters as hidden fields, so it works with JavaScript disabled
(an *Apply* button submits it). When JavaScript is available the button is dropped and changing the dropdown
submits immediately. The chosen order is part of the URL, and the card subtitle names the order in use. The
*closing* column header still toggles between the two closing-rank directions.

## Honesty in the UI

* Every prediction shows the API's `notices`, including the warning that the eligibility rules are awaiting review.
* A panel lists the seat categories used, with the bulletin clause they come from.
* Each row explains its label in words ("…went to AIR 31,354, 1.05× your rank … Rule: between 0.95× and 1.15×").
* The table footer and the CSV header both state this is a personal research aid, **not an official MCC choice list**.
* 422 responses from the API are rendered as a readable panel with the field and the allowed values, never a stack trace.

## Phones and tablets

Three decisions shape the small-screen layout.

**Tables become cards below `xl`.** Each list page renders both a real `<table>` (`TableView`) and a stacked
card list (`CardListView` + `RecordCard`), and CSS picks one; everything stays server-rendered. The switch is at
1280px rather than 1024px because `lg` is also where the 256px desktop rail appears — at 1024px that leaves
768px of content for tables that want ~1125px, so the table would scroll sideways exactly where cards are the
better answer. Landscape tablets fall in that band. Scrolling a 7-column table on a 390px screen is worse than
useless: the row label leaves the viewport before the numbers arrive, so the numbers lose their meaning.

**Touch sizing keys on the pointer, not the width.** `@media (pointer: coarse)` in `globals.css` gives
`.btn`, `.field`, `.check`, `.check-row`, `.nav-item`, `.summary-tap`, `.row-title` and `.link-tap` a 44px
minimum (WCAG 2.5.5 / Apple HIG) and sets `.field` to 16px. A width breakpoint gets this wrong both ways: a
tablet at 800px is still a thumb, a 500px-wide desktop window is not. The 16px matters specifically because
iOS Safari zooms the viewport whenever a focused input's text is smaller, which left the user scrolled
sideways with no obvious way back.

**`viewport` sets no `maximumScale`.** Pinch-zoom is the main accessibility tool on a phone for dense data,
and blocking it fails WCAG 1.4.4.

Charts cannot use CSS breakpoints for axis widths, so `charts.tsx` reads `matchMedia` in a hook that starts
`false`, which keeps SSR and hydration consistent and means a phone never briefly renders desktop sizing.
Category axes drop from 150/170px to 88/96px with truncated tick labels.

Verified with a headless-Chrome audit over 6 pages × 6 viewports (375, 412, 768, 1024, 1280, 1920) checking
document overflow, tap targets under 44px (measuring the wrapping `<label>` for checkboxes, exempting
`sr-only` helpers and inline prose links) and text under 12px. Result: no horizontal overflow and no
undersized touch target at any size, confirmed against the deployed site as well as locally.

## Accessibility

Checked on all pages: one `<h1>`, `lang="en"`, every control has a label, `<th scope="col">` on all table headers,
no duplicate ids, no empty links, a skip-to-content link, `aria-current` on the active nav item, visible focus rings,
and chance labels conveyed by text as well as colour. Charts are decorative duplicates of the table data; the
underlying numbers are always available as text. `prefers-reduced-motion` disables transitions. Full WCAG
compliance needs manual testing with assistive technology and an expert review.

## Verified

* All routes return 200 with real data; an unknown college id renders the 404 page.
* Dashboard KPIs match the API exactly for the golden profile (2025, ST, AIR 30,000, AIQ, clinical MD/MS):
  530 achievable, 170 Safe, 181 Good + Borderline, 179 Later-round. The chance breakdown lists all 1,995
  options (170 / 114 / 67 / 179 / 165 / 1,300) while the table total is 695 — the default filter keeps the four
  achievable labels plus Reach, and drops Unlikely.
* Table shows 25 rows per page; pagination reads "1–25 of 695 options" and page 2 "26–50 of 695".
* CSV export contains those 695 options plus a four-line provenance header (year, quota, category, rank,
  rounds, eligible seat categories, source, thresholds) — 699 lines in total.
* `tsc --noEmit`, `next lint` and `next build` are all clean.

## Not in this milestone

Saving and reordering a shortlist is Milestone 4; the table has no selection column yet. There is no authentication —
Phase 1 is local only and the port is bound to `127.0.0.1`.
