# Predictor API (Milestone 2)

FastAPI service over the Milestone-1 database. Interactive docs (OpenAPI) are at **http://127.0.0.1:8000/docs**.

```bash
docker compose up -d api                    # starts db too; code reloads on change
docker compose exec -T api pytest -q        # unit + API tests (needs the data imported)
```

The API is **read-only**: every database session is read-only. It has **no authentication** and is bound to
`127.0.0.1` for Phase 1. CORS allows only the local frontend origins (`CORS_ORIGINS`, default `http://localhost:3000`).

## How a prediction is made

1. **Eligible seat categories** come from `category_eligibility` for the year and candidate category,
   e.g. ST → ST + Open, ST-PwD → ST, ST-PwD, Open, Open-PwD. Nothing is hard-coded.
2. **Options:** for every institute × course in the quota, and for each considered round (default: the regular
   rounds R1–R3), the closing rank is the worst rank allotted on any eligible seat category.
3. **Status:** compares the *first* considered round's closing rank with your rank (`ratio = close / rank`):

   | Status | Rule (default thresholds, configurable) |
   |---|---|
   | `safe` – Safe | ratio ≥ 1.5 |
   | `good` – Good chance | 1.15 ≤ ratio < 1.5 |
   | `borderline` – Borderline | 0.95 ≤ ratio < 1.15 |
   | `later_round` – Later-round opportunity | first round below 0.95, but a later round closed at ≥ 0.95 × rank |
   | `reach` – Reach | best closing rank of any round ≥ 0.75 × rank |
   | `unlikely` – Unlikely | otherwise |

4. **Desirability (0–100):**
   `100 × (1 − (w × branch percentile + (1 − w) × institute percentile))`. The percentiles rank the median AIR of
   first-round allotments in the quota, across all categories. The default weight is `w = 0.6`. This measures
   demand, not quality.
5. **Reason:** each option carries a plain-language reason that cites the rank, round and rule, e.g.
   *"In Round 1 the last eligible seat (ST) went to AIR 31,354, 1.05× your rank of 30,000; latest closing in later
   rounds: AIR 45,737 in Round 3. Rule: between 0.95× and 1.15× → Borderline."*

These are historical estimates, not probabilities. Every response includes `notices`, and while the eligibility
rules are unreviewed, one notice says they have not been confirmed.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/predict` | Classify options for a candidate profile |
| GET | `/api/years` | Loaded years, their rounds and the eligibility rules (with source and `confirmed`) |
| GET | `/api/meta` | Supported quotas, categories, statuses, default thresholds, limitations, source documents |
| GET | `/api/branches?year=&quota=AI` | Branches with group, degrees, course codes and demand (median / p25 AIR, seats) |
| GET | `/api/states?year=` | States with the number of institutes |
| GET | `/api/colleges?year=&quota=&state=&q=&branch=&limit=&offset=` | Institutes with allotments in the year |
| GET | `/api/colleges/{id}?year=` | Every course: round-wise cut-offs per quota and seat category + Round-1 seat-matrix seats |
| GET | `/api/cutoffs?year=&quota=&round=&seat_category=&branch=&state=&college_id=&course_code=&min_closing_rank=&max_closing_rank=` | Raw cut-off rows, paginated |
| GET | `/api/health` | Liveness and the current data version |

### `POST /api/predict`

```json
{
  "rank": 30000, "category": "ST", "quota": "AI", "year": 2025,
  "rounds": ["R1", "R2", "R3"],
  "branches": ["General Medicine", "Paediatrics"], "states": ["Kerala"],
  "groups": ["Clinical"], "degrees": ["MD/MS"],
  "statuses": ["safe", "good", "borderline", "later_round", "reach"],
  "thresholds": {"safe": 1.5, "good": 1.15, "borderline": 0.95, "reach": 0.75},
  "branch_weight": 0.6, "sort": "desirability", "limit": 500, "offset": 0
}
```

Only `rank` and `category` are required. The rest of the request works as follows:

* **`year`:** defaults to the latest loaded year.
* **`rounds`:** defaults to that year's regular rounds. Add `STRAY` or `SPECIAL_STRAY` to include stray rounds.
* **`statuses`:** defaults to all statuses except `unlikely`.
* **`sort`:** one of the keys below (default `desirability`). `closing_rank` is accepted as an alias of
  `closing_rank_desc` so older links keep working. The applied value is echoed back as `sort`.
* **Unknown fields** are rejected.

| `sort` | Order |
|---|---|
| `desirability` | Most in-demand first (branch × college demand mix) |
| `chance` | Best chance first: Safe → Good → Borderline → Later-round → Reach → Unlikely |
| `closing_rank_desc` | Closing rank, most relaxed first |
| `closing_rank_asc` | Closing rank, most competitive first |
| `branch_demand` | Branch most in demand first (lowest median Round-1 AIR) |
| `college_demand` | College most in demand first |
| `college` | College name A–Z |
| `branch` | Branch name A–Z |

Closing-rank sorts use the **best closing rank across the chosen rounds**, so a seat that only opened in a later
round is ranked by that round rather than appearing blank. Ties break by college name, then course name. Sorting
never changes which options are returned, only their order. `GET /api/meta` returns `sorts` (key → label) and
`default_sort`.

The response contains:

* the resolved `year`, `quota` and `rounds`
* `eligibility`: seat categories, `confirmed`, source and clauses
* the applied `sort`
* `thresholds`
* `summary.by_status` and `summary.by_branch`: counts after the branch/state/group/degree filters, for all statuses
* `total`: options after all filters, before `limit`/`offset`
* `options`: institute, course, status, desirability, `ratio_first_round`, per-round `best_close` and
  `by_category` (seats, opening and closing rank), median AIRs, and the reason
* `notices`

### Errors

Inputs that can't be answered reliably return **422** with a `detail` object instead of a guess:

```json
{"detail": {"message": "Quota \"NR\" (Non-Resident Indian) has extra eligibility conditions that the predictor does not model yet.",
            "field": "quota", "allowed": {"AI": "...", "AD": "...", "PS": "..."}}}
```

This happens for:

* **Quotas:** unsupported quotas (NRI, minority, AFMS, DU/IP/AMU/BHU internal) and unknown quotas
* **Data:** years that aren't loaded, unknown round codes, branches or states
* **Rules:** categories with no eligibility rules
* **Request shape:** thresholds out of order and malformed requests

## Verification

* **Golden test:** 2025, ST, AIR 30,000, AIQ, Clinical, MD/MS gives **520 options: 170 Safe, 114 Good, 67 Borderline,
  169 Later rounds**, the same as the analysis notebook. The top option is Stanley MC – General Medicine
  (desirability 91.5, Round-1 close 19,508).
  * The API returns extra options for 19 institutes whose address has no state. The notebook's pandas pivot
    dropped those, so the test compares the options for institutes with a state.
* **Latency:** measured over HTTP on the local machine, with 45 mixed profiles. The median is 0.14 s and p95 is
  0.20 s.
* **Response size:** a full unfiltered response (`limit: 5000`) is about 1.4 MB, so use filters and `limit` in the UI.
* **Tests:** 36 API tests. They cover:
  * status thresholds at their boundaries and percentile ranks that match pandas
  * the golden test
  * filters, pagination, PwD eligibility, 2024 data, stray rounds and custom thresholds
  * every error case
  * the lookup endpoints and the p95 latency limit
