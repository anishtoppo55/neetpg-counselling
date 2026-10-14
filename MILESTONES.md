# NEET PG Counselling Intelligence Platform – Milestones

Companion to `neet_pg_counselling_platform_plan.md`. This file tracks *what* will be built, in which order, and
how each milestone is judged done.

## Decisions so far

| Topic | Decision |
|---|---|
| Phase 1 (MVP) scope | Module A – College Predictor only |
| Phase 2 scope | Module B – Counselling Assistant (hosted LLM, likely Google Gemini), hosting, user accounts |
| Data years | 2024 and 2025 now; schema and pipeline must allow adding older years (2023, 2022 …) without code rewrites |
| Runtime | Local only, everything in Docker Compose (Docker 29.4 / Compose v5.1 available) |
| Hosting / accounts | Not in Phase 1; API bound to `127.0.0.1`, no login |
| Source documents | Official MCC / NBEMS / NMC PDFs in `data/raw/<year>/<kind>/`, fetched by `scripts/fetch_mcc_documents.py`, recorded in `data/raw/manifest.csv` |
| Reference results | The Jupyter notebook `MCC_2025_ST_AIQ_all_rounds_analysis.ipynb` is the baseline the predictor is tested against |

## Overview

| # | Milestone | Phase | Status |
|---|---|---|---|
| 0 | Source documents collected | 1 | ✅ Done |
| 1 | Data foundation (schema, import pipeline, Docker) | 1 | ✅ Done (eligibility rules awaiting review) |
| 2 | Predictor API | 1 | ✅ Done |
| 3 | Frontend (profile form, results dashboard, detail pages) | 1 | ✅ Done |
| 4 | Local shortlist and export | 1 | ⏳ Next (CSV export already shipped) |
| 5 | Counselling Assistant (Gemini) | 2 | Later |
| 6 | Hosting and user accounts | 2 | 🚧 Render free demo + Lightsail $7 VM done; accounts later |
| 7 | Expansion (more years, metadata, analyses) | 2+ | Later |

Shortlist/export (originally milestone 5 in the plan) is moved into Phase 1 as milestone 4, kept local
(browser storage + file export) because there are no accounts yet.

---

## Milestone 0 – Source documents ✅

**Goal:** have every official document needed for 2024 and 2025 in one place with provenance.

**Done**
* Crawler `scripts/fetch_mcc_documents.py` (MCC archive, news and current-events pages + NBEMS bulletin links).
* 80 PDFs, 193 MB, each with title, URL, size, SHA‑256 and time in `data/raw/manifest.csv`.
* Per year: allotment results for every round (incl. stray / special stray), seat matrices and vacancy lists,
  MCC and NBEMS information bulletins, percentile / eligibility notices, schedules, NRI lists, admitted lists.
  Cross-year: NMC PwBD guidelines, NRI eligibility notice.
* Duplicate uploads removed; the 2025 round PDFs are byte-identical to those used in the notebook.

**Known gaps:** 2025 percentile reduction notice not found on MCC; older years not yet fetched.

---

## Milestone 1 – Data foundation ✅

**Goal:** a PostgreSQL database with validated, year‑aware counselling data, rebuilt by one repeatable command.

**Outcome**
* **Stack:** Docker Compose with `db` (postgres:16.4) and `pipeline` (python:3.12 + poppler), bound to
  `127.0.0.1`. Run steps are in `README.md`; tables, checks and how to add a year are in `docs/data_model.md`.
* **Loaded years:**
  * **2025:** R1, R2, R3 and the stray round, 69,147 allotments.
  * **2024:** R1, R2, R3, the stray round and the special stray round, 57,733 allotments.
  * **Also loaded:** reporting status for R1/R2 seats, Round‑1 seat matrices (AIQ, central‑internal, DNB, deemed),
    1,952 institutes and 100 courses.
* **Validation:** all hard checks pass for both years. A re-import replaces only that year and leaves row counts
  unchanged.
* **Tests:** 39 pass (`docker compose run --rm --entrypoint pytest pipeline -q`). They include the notebook's
  reference numbers: ST AIQ seats 842 / 703 / 688 with median ranks 40,570.5 / 52,465 / 69,040.5, AIQ
  allotments 12,047 / 9,667 / 8,783, and 1,823 ST candidates.
* **Difference from the notebook:** the database has 3,239 AIQ ST/Open institute × course combinations, against
  3,182 in the notebook. The notebook's pivot dropped 19 institutes whose address has no state (57 combinations).
* **Open item:** `pipeline/rules/eligibility.yaml` is drafted from the bulletins (§3.1, FAQ Q.18, conversion
  algorithm) and matches every allotment in both years. It is marked `confirmed: false` until it has been reviewed.
* **Known gaps** (details in `docs/data_model.md`):
  * one 2025 Round‑2 seat (rank 96,868) is missing from MCC's Round‑3 reprint
  * 34 + 48 seat‑matrix seats are not attributed to a course
  * 52–83 % of seat-matrix institutes are matched to allotment institutes
  * vacancy lists and Round‑2/3 seat matrices are not imported yet

**Original plan**

**Tasks**
1. **Project skeleton & Docker**
   * `docker-compose.yml` with `db` (postgres:16), `pipeline` (python:3.12-slim + poppler-utils) – `api` and `web` added in M2/M3.
   * `.env.example`, named volume for database data, `data/raw` mounted read‑only, ports bound to `127.0.0.1`.
2. **Inspect the 2024 PDFs** – page layout and column positions of each round, stray and special stray results,
   and the seat-matrix / vacancy PDFs. Record differences from 2025.
3. **Database schema** (year is part of every key):
   * reference: `counselling_year`, `round` (year, code, order, kind e.g. regular/stray), `quota`, `category`,
     `institute` (+ state, type), `course` (+ branch, group, degree), `source_document`
   * facts: `allotment` (year, round, rank, quota, institute, course, seat category, candidate category, remarks,
     option no., source page), `reporting_status`, `seat_matrix` (seats per institute × course × quota × category × round)
   * rules: `category_eligibility` (year, candidate category → seat categories, source document + clause)
   * derived: `cutoff` (year, round, institute, course, quota, seat category → seats, opening rank, closing rank)
4. **Import pipeline** (package reused from the notebook code)
   * Layout registry: column positions per *year + document type + round*, so a new year = new layout entry.
   * Parse → normalise (course legend, branch rules, quota/category labels, institute keys, states) → validate → load.
   * Idempotent: `docker compose run pipeline import --year 2025` replaces that year only.
5. **Category-eligibility rules** – read from the 2024 and 2025 MCC information bulletins (reservation and PwD sections)
   and NMC PwBD guidelines; store each rule with year and source clause. Rules are confirmed with you before use.
6. **Validation checks** (fail the import if broken)
   * 0 orphan / straddling words; ranks unique per round; serial numbers continuous
   * all labels belong to known vocabularies; every course mapped to a branch
   * Round‑1 rows repeated in later PDFs agree with the Round‑1 PDF
   * allotment counts per quota/round match the notebook (2025: AIQ 12,047 / 9,667 / 8,783)
7. **Load 2025 first, then 2024.**

**Deliverables:** `docker-compose.yml`, `pipeline/` package, SQL migrations, validation report per import,
short `docs/data_model.md`.

**Done when**
* `docker compose up db` + `docker compose run pipeline import --year 2025 --year 2024` builds the database from scratch.
* All validation checks pass for both years.
* 2025 cut-offs from the database reproduce the notebook (e.g. ST AIQ Round‑1 seats 842, median rank 40,571).

---

## Milestone 2 – Predictor API ✅

**Goal:** a FastAPI service that returns classified historical options for any supported candidate profile.

**Outcome** (details in `docs/api.md`)
* `api` service in Docker Compose at `127.0.0.1:8000`. It uses FastAPI, Pydantic v2 and a psycopg pool with
  read-only sessions, with OpenAPI docs at `/docs`. Code reloads while developing, and the reference cache
  refreshes automatically after each import.
* `POST /api/predict` plus lookup endpoints: `/api/years`, `/api/meta`, `/api/branches`, `/api/states`,
  `/api/colleges`, `/api/colleges/{id}`, `/api/cutoffs` and `/api/health`.
* Eligible seat categories come from `category_eligibility`. Thresholds, rounds (including the stray rounds),
  filters, branch weight, sorting and pagination are all configurable. Every option carries a plain-language reason.
* **Golden test:** reproduces the notebook exactly. For 2025, ST, AIR 30,000, AIQ, Clinical, MD/MS there are 520
  options: 170 Safe, 114 Good, 67 Borderline and 169 Later rounds. The API also returns options for the 19
  institutes without a state, which the notebook had dropped.
* **Tests:** 36 API tests and 40 pipeline tests pass. Unsupported quotas (NRI, minority, AFMS, internal), years,
  rounds, branches and states return 422 errors with the allowed values.
* **Latency:** median 0.14 s and p95 0.20 s over HTTP, locally.
* **Fix found on the way:** the pipeline had stored row numbers instead of institute names. This is fixed and
  re-imported, and a regression test guards it.
* **Still open:** the eligibility rules are unconfirmed. Each prediction carries a notice about this until they
  are reviewed.
* **Not done:** the plan named SQLAlchemy, but plain psycopg covers the read-only queries, so I left it out.
  "Institution type" preferences, such as government colleges only, are not supported yet, because the data has
  no reliable institute-type field.

**Original plan**

**Tasks**
* `api` service in Docker (FastAPI + Pydantic + SQLAlchemy/psycopg), bound to `127.0.0.1:8000`, OpenAPI docs.
* Input model: year(s), rank, category (incl. PwD), quota, preferred branches / states / institute types,
  degree types, rounds to consider.
* Eligible seat categories taken from `category_eligibility` (no hard-coded "ST + Open").
* Classification with **configurable thresholds** (Safe / Good chance / Borderline / Later-round opportunity / Reach),
  defaults equal to the notebook's (1.5×, 1.15×, 0.95×, 0.75×).
* Per option: round-wise opening/closing ranks, seat counts, quota and seat category, and a plain-language reason
  ("ST seat closed at 31,354 in Round 1, which is 1.05× your rank → Borderline").
* Endpoints: `POST /api/predict`, `GET /api/colleges`, `GET /api/colleges/{id}`, `GET /api/cutoffs`,
  `GET /api/branches`, `GET /api/states`, `GET /api/years`, `GET /api/meta` (data sources, limitations).
* Finalise endpoint contracts after M1 schema is fixed.

**Done when**
* Automated tests pass inside Docker, including a golden test: 2025, ST, AIR 30,000, AIQ, clinical MD/MS
  → 520 options (170 Safe, 114 Good, 67 Borderline, 169 Later rounds), matching the notebook.
* Responses for unsupported or unvalidated inputs return clear errors instead of guesses.
* p95 response time under 1 s locally.

---

## Milestone 3 – Frontend ✅

**Goal:** a Next.js + TypeScript + Tailwind interface for the predictor.

**Outcome** (details in `docs/frontend.md`)
* `web` service in Docker Compose at `127.0.0.1:3000`, styled after the supplied reference dashboard: left rail with
  nav and a dataset card, page header with a meta row, KPI cards with coloured icon tiles, a two-panel chart row and
  card-style tables.
* **Pages:** predictor dashboard (`/`), colleges list, college detail with a closing-rank-per-round chart and the
  Round-1 seats offered, cut-off explorer, branch demand, and a data & limits page listing the eligibility rules per
  year with their bulletin clause and every source PDF with its checksum.
* **URL is the only state.** The profile form is a plain `GET` form, so predictions are shareable and bookmarkable,
  and the back button, pagination and sorting work server-side without client state.
* **Honesty in the UI:** API notices (including the unreviewed-eligibility warning), the seat categories used with
  their source clause, a per-row *Why?* explanation, and "personal research aid, not an official MCC choice list" on
  the table and in the CSV header. 422 responses render as a readable panel with the allowed values.
* **CSV export** of the full result set with a provenance header (brought forward from Milestone 4).
* **Verified:** KPIs match the API exactly for the golden profile (530 achievable / 170 Safe / 181 Good + Borderline /
  179 Later-round); pagination reads "1–25 of 695"; export has 529 rows; `tsc`, `next lint` and `next build` are clean;
  accessibility audit passes on all pages (single `h1`, labelled controls, `th scope`, skip link, focus rings, labels
  not colour-only).
* **Deviation:** charts use Recharts (the plan allowed ECharts or Recharts). The table has no selection column yet —
  that arrives with the shortlist in Milestone 4.

**Original plan**

**Tasks**
* `web` service in Docker, `127.0.0.1:3000`.
* **Profile form:** rank, category, quota, year(s), branch/state/institute-type/degree filters, rounds.
* **Results dashboard:** summary counts by round and classification; searchable, sortable, filterable table
  (branch, state, college, round, classification); reason text per option.
* **College and course detail pages:** round-wise cut-off chart (ECharts or Recharts), seats, quotas, years.
* **Transparency:** data year and source on every page, classification definitions, limitations panel,
  "historical estimate, not a guarantee" notice.
* Accessibility basics: keyboard navigation, labels, colour not the only signal for classification.

**Done when**
* The golden profile shows the same numbers as the API and the notebook.
* Filters and detail pages work for both 2024 and 2025.
* Basic accessibility checks (automated linting) pass; full WCAG compliance needs manual review.

---

## Milestone 4 – Local shortlist and export

**Goal:** let a user build and order a personal shortlist without accounts.

**Tasks**
* Add/remove options from results; drag or button reordering; notes per option.
* Persist in browser storage; import/export as CSV and JSON.
* Clear label: "Personal shortlist – not an official MCC choice list"; no claim of portal compatibility.

**Done when** a shortlist survives a page reload, exports and re-imports without loss, and carries the disclaimer.

**End of Phase 1 (MVP):** milestones 1–4 complete, running locally with `docker compose up`.

---

## Milestone 5 – Counselling Assistant (Phase 2)

**Goal:** a Gemini-based assistant grounded in the same database.

**Tasks**
* Tool/function calling to predictor and controlled query endpoints only – no free SQL, no invented ranks or colleges.
* Answers cite college, course, rank, round, category and year; say so when evidence is missing.
* Current rules and eligibility from the stored official documents (bulletins), with source and year shown.
* Evaluation set of questions with known answers; track factual accuracy and refusal on missing evidence.
* API key handled via environment variables; flag that candidate data is sent to an external provider.

---

## Milestone 6 – Hosting and accounts (Phase 2) 🚧

**Goal:** make the platform available beyond one machine.

**Done – free-tier demo on Render** (`render.yaml`, `docs/deploy-render.md`)
* Production images: `api/Dockerfile.prod` (uvicorn on `$PORT`, single worker, 267 MB) and
  `web/Dockerfile.prod` (multi-stage Next.js standalone, 321 MB vs 1.38 GB for the dev image).
* Blueprint creates free Postgres 16 + API + dashboard, wires `DATABASE_URL`, generates `API_TOKEN` once and
  copies it to the dashboard, and sets health checks (`/api/health`, `/api/ping`).
* A free Render service cannot *receive* private-network calls, so the API is public but refuses every request
  without the `X-API-Token` header (health check excepted); `/docs` is closed by default too.
* Data is loaded by running the existing pipeline from a developer machine against the Render database, so all
  validation still applies; the database is ~115 MB against the 1 GB free limit.
* Verified by running both production images locally with `PORT` injected and a token set: health open, 401
  without the token, the golden result exact (520 = 170/114/67/169) with it, all seven pages 200, and the token
  absent from both the HTML and the JS bundles.
* Accepted limits for a demo: database expires 30 days after creation, services sleep after 15 minutes idle
  (~1 min wake), 750 free instance hours/month, 5 GB bandwidth.

**Found on the first real deploy (fixed):** the blueprint pinned the services to `singapore` but left the
database region unset, so Render created it in `oregon` — cross-region means no shared private network, which
surfaced as `[Errno -2] Name or service not known` and a health-check timeout. The database now carries an
explicit region, the health check points at a new liveness endpoint (`/api/live`) so a database outage or the
free database expiring cannot block a deploy, and `/` answers GET and HEAD without the token for Render's port probe.

**Second deploy issue (fixed):** the blueprint wired the dashboard to the API with
`fromService … property: host`, but for web services that property returns the *internal* hostname, and a free
service cannot receive private-network requests — the dashboard failed with `fetch failed`. On the free tier the
API's public URL must be set by hand as `API_BASE_INTERNAL` (`sync: false` in the blueprint, so re-syncs do not
clobber it). The in-app error panel now tells you exactly that when the base URL is not local.

**Done – self-hosted path on AWS Lightsail, $7/month** (`deploy/`, `docs/deploy-lightsail.md`)

The Render free tier is fine for a look but the database is deleted 30 days after creation and the services
sleep. One small VM removes both limits for the price of a coffee, with no domain name required.

* `deploy/docker-compose.prod.yml` — Postgres, API, dashboard and Caddy under the project name `neetpg-prod`
  (a different name from the dev stack on purpose, so running it locally cannot touch dev containers or data).
  **Caddy is the only container that publishes ports**; `db` and `api` are reachable on the Docker network only.
  No `build:` keys: the instance never compiles anything.
* `deploy/Caddyfile` — automatic HTTPS from Let's Encrypt, HTTP→HTTPS redirect, gzip/zstd, HSTS, `nosniff`,
  `X-Frame-Options: DENY`, strict referrer policy, `X-Robots-Tag: noindex, nofollow`, `Server` header removed,
  and immutable caching for `/_next/static/*`. `tls {$TLS_EMAIL:internal}` doubles as the local-test switch:
  an address means ACME, the literal `internal` means a self-signed certificate.
* Because the API is private, the `API_TOKEN` shared secret that the Render deployment needs is unnecessary
  here — no page in the dashboard is rendered in the browser, so nothing outside the box ever calls the API.
* Free hostname: **DuckDNS**. It is stable (unlike a Cloudflare quick tunnel, whose URL changes on restart) and
  `duckdns.org` is on the Public Suffix List, so each `*.duckdns.org` name gets its own Let's Encrypt rate-limit
  budget. `sslip.io`/`nip.io` need no signup at all but are *not* on the list, so all their users share one
  bucket of 50 certificates per week. A Lightsail static IP never changes, so no DDNS updater is needed.
* `deploy/lightsail.sh` — `local`/`local-down`, `bootstrap`, `build`, `ship`, `up`/`down`/`restart`, `deploy`,
  `data`, `status`, `logs`, `check`, `ssh`.
  * **Images are built here and shipped over SSH** (`docker save | gzip | ssh … docker load`, measured at
    140 MB on the wire). This is the decision that makes the 1 GB plan work: a Next.js production build
    needs far more than 1 GB and would be OOM-killed on the instance. Note that gzip barely helps on
    Docker's containerd image store, which already saves compressed layer blobs — it is kept for older
    daemons on the overlay2 graph driver, where saved layers are uncompressed.
  * `bootstrap` installs Docker, adds a 2 GB swap file with `vm.swappiness=10`, and caps container logs at
    3 × 10 MB so they cannot fill the 40 GB disk.
  * `data` moves the database with `pg_dump --clean --if-exists` (2.4 MB gzipped, 4 s) instead of re-parsing
    149 MB of PDFs on a 1 GB box, then restarts the API so it re-reads its data version. Repeatable.
* Plan sizing: the $7 dual-stack bundle is 1 GB / 2 vCPU / 40 GB / 2 TB transfer (halved in Mumbai), **not**
  the $5 one, which is 512 MB. Measured footprint of the running stack: web 120 MiB, db 91, api 64, caddy 13 —
  289 MiB total, roughly 420 MB with Ubuntu, so 1 GB fits with no room for a second workload.
* **Verified locally before spending anything**, with the full data (2025: 69,147 allotments, 2024: 57,733)
  restored into the prod stack through `data --local`:
  * every page and the example query 200 over HTTPS, `/nope` 404, `http://` 308 → `https://`;
  * all five security headers present, `Server` stripped, `/_next/static/*` served `max-age=31536000, immutable`;
  * CSV export 200, `text/csv`, 695 options plus the four provenance comment lines;
  * the golden profile reproduced exactly on the production API — 520 options at institutes with a state,
    170 Safe / 114 Good / 67 Borderline / 169 Later-round, 530 achievable including the 10 stateless
    institutes, eligibility `['OPEN', 'ST']`, which is what `test_golden_matches_notebook` asserts;
  * `/api/predict` byte-identical between the dev and production stacks for the same body (unfiltered total
    695 across all six statuses; top option GOVT. MEDICAL COLLEGE, THIRUVANANTHAPURAM — M.D. General
    Medicine, desirability 92.9, R1 close 14,515);
  * 52 API tests pass.
* **Caught by that local test:** using `/api/health` as the `api` container's health check deadlocks the first
  deploy — it answers 503 until data is loaded, but data can only be loaded once the stack is up. The health
  check now uses `/api/live`, the same liveness endpoint added after the first Render deploy timed out. The
  lesson did not transfer automatically because the Render fix was in `render.yaml`, not in a compose file.

**Deployed and verified live** at `https://ncounselling.duckdns.org` (Lightsail `ncounselling`, ap-south-1,
$7 plan, static IP 15.206.161.215, Ubuntu 24.04.4, 2 vCPU, 909 MB RAM, 38 GB disk):

* Let's Encrypt certificate issued via the `tls-alpn-01` challenge, `CN=ncounselling.duckdns.org`, valid to
  12 Jan 2027, auto-renewing; `http://` 308 → `https://`.
* All six pages 200, `/nope` 404, all five security headers present, `Server` stripped.
* The golden profile reproduces exactly on the instance: 520 with-state options, 170/114/67/169, and the
  dashboard KPIs match the local stack digit for digit (170/114/67/179/165/1,300 over 695 matching options).
  CSV export 200 with 699 lines. `/api/health` → `data_version: 5`.
* Ports 5432, 8000, 3000 and Caddy's admin 2019 all confirmed **unreachable from the internet**; only 80 and
  443 answer. Every container is `restart=unless-stopped`, so a reboot recovers unattended.
* `data` moved both years in 11 s end to end (2.4 MB gzipped dump).
* Actual memory: containers 263 MiB (web 104, db 79, api 59, caddy 21), but the host reports 587 MB used of
  909 with ~54 MB swap touched. Working, with little headroom — see the sizing note in the deploy doc.

**Mobile pass over the dashboard** (`docs/frontend.md` → "Phones and tablets")

Prompted by the first real phone visit. Two bugs, the first severe:

* **The site was unusable on every phone and tablet.** `layout.tsx` wrapped the shell in
  `<div class="flex min-h-screen">`, but `Sidebar` renders *two* siblings — the desktop rail and the mobile
  top bar — so below `lg` the top bar became a flex column beside `<main>`. Measured at 768px: the bar took
  612px and the content was squeezed into 155px; at 390px the content was pushed off-screen and the page
  rendered blank. Fixed by making the row `lg:flex`, so below `lg` it is ordinary block flow.
* **The whole document scrolled sideways at every width, including desktop.** `sr-only` is
  `position: absolute`, and the `overflow-x-auto` table wrappers were `position: static`, so they were not
  the absolute containing block and could not clip them. The `sr-only` helpers (`<span>Open</span>` in a
  header cell, the table `<caption>`) resolved against the document at the table's far-right edge — x=1321
  on `/colleges` — which set `document.scrollWidth` and added up to 297px of phantom scroll. Fixed with
  `relative` on the wrapper. This one had been live on desktop the whole time.

Then the actual responsive work: tables re-render as stacked cards below `xl`, touch sizing keyed on
`@media (pointer: coarse)` rather than viewport width, 16px form text to stop iOS zoom-on-focus, chart axes
sized from `matchMedia`, two-up KPI tiles, and stacking headers/pagination. Rationale for each in the
frontend doc. Verified by a headless-Chrome audit of 6 pages × 6 viewports for overflow, tap-target size and
text size — clean locally and against the live site, with the golden figures unchanged (520 with-state
options, 170/114/67/169; dashboard 170/114/67/179/165/1,300 over 695; CSV 699 lines).

**Still to do for real hosting:** authentication once shortlists become per-user, rate limiting (Caddy's core
build has none; it needs a plugin or a small reverse-proxy rule), off-box backups on a schedule rather than by
hand, and an uptime check. For the Render path specifically: paid plans would let the API be a private service
with no cold starts and give a non-expiring Postgres.

**Original plan**

**Tasks**
* Choose hosting (e.g. Vercel + Render, or a single VM with Docker Compose).
* Authentication, saved shortlists per user, rate limiting, HTTPS, backups.
* Security review before any public exposure (the Phase 1 API has no auth by design).

---

## Milestone 7 – Expansion

* Add older years (2023, 2022 …) via the crawler + layout registry.
* College metadata: fees, stipend, bond, hospital type.
* Richer analyses: multi-year trends, seat movement between rounds, college comparisons, counselling simulation.
* Only after the predictor and assistant are reliable.

---

## Principles carried through every milestone

* Historical cut-offs are evidence, not guarantees; no probabilities without a validated model.
* Every number traceable to a source document, year and round.
* Eligibility rules come from official documents and are confirmed before use.
* Recommendations follow the candidate's stated preferences.
