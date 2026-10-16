# NEET PG Counselling Intelligence Platform

A web app that turns the official MCC seat-allotment PDFs into a **college predictor**: enter a rank and
category, and see which college × course options were historically within reach, with the evidence behind each one.

### ▶ Live: **https://ncounselling.duckdns.org**

Self-hosted on a single AWS Lightsail instance. No sign-up, works on phones, and every result is a shareable URL:
[2025, ST, AIR 30,000, AIQ, clinical MD/MS](https://ncounselling.duckdns.org/?rank=30000&category=ST&quota=AI&year=2025&groups=Clinical&degrees=MD%2FMS).

Everything here is **historical evidence, not a prediction**. Cut-offs, seat matrices and rules change every year.

| Documentation | |
|---|---|
| [`docs/data_model.md`](docs/data_model.md) | Tables, the PDF parsing approach, validation, limitations, adding a year |
| [`docs/api.md`](docs/api.md) | Endpoints, classification rules, verification |
| [`docs/frontend.md`](docs/frontend.md) | Pages, URL state, responsive behaviour, accessibility |
| [`docs/deploy-lightsail.md`](docs/deploy-lightsail.md) | Deploying the stack to a $7/month VM with HTTPS |

## Status

Phase 1 (MVP) is the predictor, and it is deployed. The Gemini assistant and user accounts come in Phase 2.

| # | Milestone | State |
|---|---|---|
| 0 | Official source documents collected (80 PDFs, 149 MB) | ✅ |
| 1 | Data foundation – PostgreSQL schema + repeatable import | ✅ |
| 2 | Predictor API – FastAPI, classification, lookups | ✅ |
| 3 | Frontend – Next.js dashboard, colleges, cut-offs, branches | ✅ |
| 4 | Saved shortlist with reordering (CSV export already works) | next |
| 6 | Hosting – AWS Lightsail, HTTPS, live at [ncounselling.duckdns.org](https://ncounselling.duckdns.org) | ✅ deployed |
| 5, 7 | Counselling assistant (Gemini), accounts, more years | later |

One open item: the category-eligibility rules in `pipeline/rules/eligibility.yaml` are drafted from the MCC
bulletins and match every allotment in the data, but are marked `confirmed: false` until reviewed. The UI and every
API response say so.

## Requirements

* Docker with Compose v2 (tested on Docker 29.4 / Compose v5.1)
* ~3 GB free disk for images, ~600 MB for the PDFs, parse cache and database
* `python3` only if you want the script to download the source PDFs for you

## Run

```bash
./start.sh
```

That single command creates `.env` (with a random database password), checks the source PDFs, builds any missing
images, starts PostgreSQL, applies migrations, imports the counselling years, then starts the API and the dashboard
and waits until both report healthy. Re-running is safe: loaded data is kept and only missing work is done.
First run takes a few minutes (image build plus ~35 s per year); later runs about 30 seconds.

| Command | What it does |
|---|---|
| `./start.sh` | Bring everything up: db → migrate → import → api → web |
| `./start.sh --tests` | Same, plus both test suites (40 pipeline + 52 API) |
| `./start.sh --status` | What is running, and which years and tables are loaded |
| `./start.sh --logs web` | Follow logs (`db`, `api`, `web`, or all) |
| `./start.sh --stop` | Stop the containers, keep the data |
| `./start.sh --down` | Remove the containers, keep the database volume |
| `./start.sh --rebuild` | Rebuild images first (after changing code or dependencies) |
| `./start.sh --force-import` | Re-import even if data is already loaded |
| `./start.sh --years "2025"` | Import only these years |
| `./start.sh --reset` | Wipe the database volume and rebuild from the PDFs (asks you to confirm) |
| `./start.sh --fetch` | Download the official source PDFs first |
| `./start.sh --help` | All options |

If you change `POSTGRES_PASSWORD` after the database volume exists, the script re-syncs the stored role password
instead of failing — no data is lost.

### Where things are

| URL | What |
|---|---|
| http://127.0.0.1:3000 | Dashboard (predictor, colleges, cut-offs, branches, data & limits) |
| http://127.0.0.1:8000/docs | API reference (OpenAPI) |
| `127.0.0.1:5432` | PostgreSQL, credentials in `.env` |

A prediction lives entirely in the URL, so it can be bookmarked or shared:

```text
http://127.0.0.1:3000/?rank=30000&category=ST&quota=AI&year=2025&groups=Clinical&degrees=MD%2FMS
```

The same query through the API:

```bash
curl -s -X POST http://127.0.0.1:8000/api/predict -H 'Content-Type: application/json' \
     -d '{"rank": 30000, "category": "ST", "groups": ["Clinical"], "degrees": ["MD/MS"], "limit": 10}'
```

<details>
<summary>The same steps by hand</summary>

```bash
cp .env.example .env              # then set POSTGRES_PASSWORD
docker compose up -d db
docker compose build pipeline api web
docker compose run --rm pipeline migrate
docker compose run --rm pipeline import --year 2025 --year 2024
docker compose run --rm pipeline status
docker compose run --rm --entrypoint pytest pipeline -q
docker compose up -d api                                 # http://127.0.0.1:8000/docs
docker compose exec -T api pytest -q
docker compose up -d web                                 # http://127.0.0.1:3000
```

* `docker compose run --rm pipeline check --year 2024` parses and validates without touching the database.
* Re-running `import --year Y` replaces year Y only; other years are untouched.
* Validation reports go to `data/reports/`; the parse cache in `data/cache/` is safe to delete.

</details>

## What the data contains

Loaded from the official MCC results: every round of 2024 and 2025, including the stray and special stray rounds.

| | 2025 | 2024 |
|---|---|---|
| Rounds | R1, R2, R3, Stray | R1, R2, R3, Stray, Special Stray |
| Allotments | 69,147 | 57,733 |
| Ranks printed | 106,404 | 95,633 |
| Reporting statuses | 47,675 | 40,853 |
| Round-1 seat-matrix rows | 15,649 | 14,888 |

Shared across years: 1,952 institutes, 100 courses (branch, group, degree), 80,997 cut-off rows
(round × quota × college × course × seat category) and 54 eligibility rules with their source clause.

Each import runs hard validation — no words lost or crossing columns, ranks unique and sorted, every label known,
and seats reprinted in a later round agreeing with that round's own PDF. If a check fails, nothing is written for
that year.

## How a chance label is decided

For each college × course, the closing rank of a round is the worst rank allotted on any seat category your
category may hold (e.g. ST or Open for an ST candidate). The label compares your rank with the **first** considered
round:

| Label | Default rule | Meaning |
|---|---|---|
| Safe | ≥ 1.5 × your rank | Closed far behind you |
| Good chance | 1.15 – 1.5 × | Comfortable margin |
| Borderline | 0.95 – 1.15 × | Around your rank |
| Later-round opportunity | Not in round 1, but a later round ≥ 0.95 × | Comes through upgrades |
| Reach | Best of any round ≥ 0.75 × | Low chance, worth listing high |
| Unlikely | below that | |

Thresholds are adjustable in the form. **Desirability (0–100)** mixes how early a branch and a college fill up
(median Round-1 rank); it is a demand proxy, not a measure of teaching quality, workload, bond or fees.

Supported quotas: `AI` (All India), `AD` (DNB), `PS` (self-financed / management-paid). NRI, minority, Armed Forces
and internal university quotas have extra conditions that are not modelled, so the predictor refuses them with an
explanation — their cut-offs remain browsable.

## Verification

* The database and API reproduce the independent analysis notebook. For 2025, ST, AIR 30,000, AIQ, clinical MD/MS:
  **520 options — 170 Safe, 114 Good, 67 Borderline, 169 Later-round**; ST AIQ seats 842 / 703 / 688 across rounds
  with median ranks 40,570.5 / 52,465 / 69,040.5.
* 92 automated tests (40 pipeline, 52 API) including that golden case, threshold boundaries, error handling and a
  p95 latency limit. Measured `/api/predict` p95 is 0.12 s locally (median 0.10 s over 12 runs).
* The deployed site reproduces the same figures exactly, checked against the live instance.
* `tsc`, `next lint` and `next build` are clean. Layout is verified by a headless-Chrome audit over 6 pages ×
  6 viewports (375 → 1920 px) for horizontal overflow, 44 px touch targets and text size.

## Known gaps

* Eligibility rules awaiting review (above).
* One 2025 Round-2 seat (rank 96,868, Armed Forces) is missing from MCC's own Round-3 PDF, so its reporting status
  is unknown.
* 82 of ~55,000 seat-matrix seats could not be attributed to a course (overlapping cells in the PDF); 52–83 % of
  seat-matrix institutes are linked to allotment institutes, depending on the matrix.
* Vacancy lists, Round-2/3 seat matrices and stray-round reporting status are not imported.
* No "government colleges only" filter yet — the data has no reliable institute-type field.
* Shortlist saving and reordering arrives in Milestone 4.

## Hosting

Live at **https://ncounselling.duckdns.org**, on one **AWS Lightsail** instance for **$7/month**
(1 GB RAM, 2 vCPU, 40 GB SSD, Mumbai).

`deploy/docker-compose.prod.yml` runs four containers — Postgres, the API, the dashboard, and Caddy, which
terminates HTTPS with a free Let's Encrypt certificate on a free DuckDNS hostname, so no domain name is needed.
Caddy is the only container that publishes ports, so the database and the API are unreachable from the internet
and need no shared secret. The production images are `api/Dockerfile.prod` and `web/Dockerfile.prod`; the plain
`Dockerfile`s stay for local development.

Nothing is ever built on the instance. `deploy/lightsail.sh` builds the images here and ships them over SSH
(~140 MB), which is what keeps a 1 GB box viable — a Next.js production build needs far more memory than that
and would be killed:

```bash
cp deploy/env.prod.example deploy/.env.prod   # set SITE_HOST, TLS_EMAIL, POSTGRES_PASSWORD
./deploy/lightsail.sh local                   # smoke-test the production stack on this machine
./deploy/lightsail.sh bootstrap               # Docker + swap + log rotation on the instance
./deploy/lightsail.sh deploy                  # build, ship, start, verify the public URL
./deploy/lightsail.sh data                    # pg_dump the local database into the instance
```

Measured footprint on the instance: **263 MiB** across the four containers (web 104, db 79, api 59, caddy 21),
roughly 615 MB of the 909 MB in use overall. `./deploy/lightsail.sh status | logs web | check | ssh` handle
day-to-day operation. Walk-through, including the console click-path, firewall rules, backups, costs and
troubleshooting: **`docs/deploy-lightsail.md`**.

## Security

Running locally is the default and is local only. The database (`5432`), API (`8000`) and web (`3000`) ports are bound to `127.0.0.1`.
The API has no authentication and uses read-only database sessions; the web app has no login and stores nothing.
Do not expose these ports on a network. `.env` holds the database password and is git-ignored.

The deployment narrows that surface rather than closing it. Only Caddy publishes ports, so Postgres and the API
are unreachable from outside the box (verified: 5432, 8000, 3000 and Caddy's admin 2019 all refuse connections
from the internet), everything is served over HTTPS with HSTS and `X-Robots-Tag: noindex`, and SSH is restricted
to one address. There is still no **user** authentication: anyone with the link sees the dashboard, and there is
no rate limiting — treat a shared URL as semi-private. Secrets live only in `deploy/.env.prod` locally
(git-ignored) and `~/neetpg/.env` on the instance (mode 600).

The build loads **Google Analytics 4** (`NEXT_PUBLIC_GA_ID`, baked in at build time; set it to an empty
string to switch analytics off). Worth knowing what that implies: GA records `page_location`, and on the
predictor the URL carries the visitor's rank and category, so those values reach Google. The predictor still
stores nothing server-side. The `/about` page states this plainly. To record paths without the query string,
change the `gtag('config', …)` call in `web/app/layout.tsx` to
`gtag('config', GA_ID, { page_location: location.origin + location.pathname })`.

## Layout

```text
counselling_platform/
  start.sh                                                           one-command local stack
  docker-compose.yml, .env.example
  data/raw/<year>/{allotments,seat_matrix,rules,notices,admitted}/   official PDFs + manifest.csv (SHA-256)
  scripts/fetch_mcc_documents.py                                     document crawler (MCC + NBEMS)
  pipeline/
    config/{sources,layouts,courses}.yaml                            which documents, column layouts, course catalogue
    rules/eligibility.yaml                                           category eligibility per year, with sources
    migrations/001_init.sql                                          schema
    neetpg_pipeline/                                                 parser, normaliser, validator, loader, CLI
    tests/
  api/
    app/                                                             FastAPI app, predictor core, queries, schemas
    tests/
  web/
    app/                                                             pages (predictor, colleges, cut-offs, branches, about)
    components/, lib/                                                UI kit, charts, typed API client
  docs/data_model.md                                                 tables, validation, limitations, adding a year
  docs/api.md                                                        endpoints, classification rules, verification
  docs/frontend.md                                                   pages, design, URL state, accessibility
  docs/deploy-lightsail.md                                           $7/month single-VM deployment
  deploy/
    docker-compose.prod.yml, Caddyfile                               production stack behind automatic HTTPS
    env.prod.example                                                 template for deploy/.env.prod
    lightsail.sh                                                     build, ship, start, load data, check
```

## Adding another counselling year

1. `./start.sh --fetch` (or add title patterns for the year in `scripts/fetch_mcc_documents.py` and run it).
2. Check the result-PDF column layout against `pipeline/config/layouts.yaml`; reuse a layout or add one.
3. Add the year to `pipeline/config/sources.yaml` and its rules to `pipeline/rules/eligibility.yaml`.
4. `./start.sh --years "2023"` — the import refuses a wrong layout rather than loading bad data.

Full details in `docs/data_model.md`.

---

Not affiliated with MCC, NBEMS or NMC. Always confirm against the current official information bulletin and seat
matrix before filling choices.
