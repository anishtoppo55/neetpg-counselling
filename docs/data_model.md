# Data model and import pipeline (Milestone 1)

## Flow

```text
data/raw/<year>/*.pdf  ──pdftotext -bbox──▶  word boxes  ──layout──▶  tables  ──normalise──▶  validate  ──▶  PostgreSQL
 (official MCC PDFs)        (cached by SHA-256)       (config/layouts.yaml)   (vocab.py,       (hard/soft      (one transaction
                                                                               courses.yaml)     checks)         per year)
```

* `config/sources.yaml` lists the documents of each year: one result PDF per round, which later PDF gives the
  reporting status of a round's seats, and the Round-1 seat matrices.
* `config/layouts.yaml` holds the column x-positions of each result-PDF layout. Five layouts cover 2024 and 2025.
* `config/courses.yaml` is the course catalogue (100 MCC programme codes) with branch, group and degree.
* `rules/eligibility.yaml` lists the seat categories each candidate category may hold, per year, with the bulletin
  clause it comes from.

## Tables

| Table | One row per | Notes |
|---|---|---|
| `counselling_year` | year | `NEET PG 2024`, `NEET PG 2025` |
| `round` | year × round | `R1`, `R2`, `R3`, `STRAY`, `SPECIAL_STRAY`; `seq` orders them, `kind` regular/stray |
| `source_document` | PDF | path, SHA-256, title/URL from `data/raw/manifest.csv` |
| `quota` | quota | MCC codes `AI` (All India), `AD` (DNB), `PS` (self-financed / management-paid), `NR`, `DU`, `IP`, `AM`, `BH`, `JM`, `MM`, `AF` |
| `seat_category` / `candidate_category` | category | `OPEN`, `OBC`, `SC`, `ST`, `EWS` (+ `_PWD`) / `GEN`, `OBC`, … (+ `_PWD`) |
| `institute` | institute | `key` = upper-case alphanumerics of the full printed name; `short_name`, `state`, `mcc_code` (from seat matrix), `last_year` |
| `course` | MCC programme | `code` (GMED, RADD, DMED …), `branch`, `branch_group`, `degree` |
| `round_result` | round × rank | every rank printed in a round's own PDF, allotted or not, with remarks and source page |
| `allotment` | round × rank | the seat held after that round: quota, institute, course, seat category, candidate category, option no. |
| `reporting_status` | round × rank | Reported / Not Reported / Seat Surrendered / Seat Cancelled, read from the next round's PDF |
| `seat_matrix` | seat group | Round-1 seats per institute × course × quota × seat category (deemed matrices: totals only) |
| `category_eligibility` | year × candidate cat × seat cat | with `source_document_id`, `source_clause`, `confirmed` |
| `cutoff` (materialised view) | year × round × quota × institute × course × seat category | `seats_allotted`, `opening_rank`, `closing_rank`; refreshed after each import |
| `import_run` | import | status and the full validation report (JSON) |

**Round meaning:** a round's `allotment` rows are the seats allotted *in that round* (fresh or upgraded), exactly as
printed in the round's own PDF. A candidate who kept a Round-1 seat appears in Round 2 only in `round_result`
(e.g. "Did not opt for Upgradation.").

**Institute identity:** the full printed name (name + address) is the key. It is identical across rounds of a year
and mostly across years. When an address changes between years, two `institute` rows result. These can be linked
later through `mcc_code`.

## Validation (every import)

Hard checks fail the import, and nothing is written for that year:

* 0 words outside a record and 0 words crossing a column border, in every result PDF
* ranks numeric, unique and sorted, and serial numbers continuous where printed
* every allotted row has a known quota, course, seat category and candidate category, and a non-empty institute
* seats reprinted in the next round's PDF belong to that round and have the same quota (two independent parses agree)

Soft checks become warnings: seat-matrix totals and course matches, seat-matrix institute matching, and seats
missing from the next round's reprint.

Reports are written to `data/reports/import_<year>_<timestamp>.json` and stored in `import_run.report`.

## Current data (2024 + 2025)

| Year | Round | Ranks printed | Allotted | AIQ allotted |
|---|---|---|---|---|
| 2025 | R1 / R2 / R3 / STRAY | 26,889 / 35,023 / 41,694 / 2,798 | 26,889 / 20,787 / 18,673 / 2,798 | 12,047 / 9,667 / 8,783 / 1,510 |
| 2024 | R1 / R2 / R3 / STRAY / SPECIAL_STRAY | 24,671 / 31,490 / 36,583 / 2,331 / 558 | 24,671 / 16,182 / 13,991 / 2,331 / 558 | 12,029 / 8,451 / 7,958 / 1,453 / 362 |

The database reproduces the analysis notebook. For ST AIQ seats in 2025, there are 842 / 703 / 688 seats in
R1 / R2 / R3, with median ranks of 40,570.5 / 52,465 / 69,040.5 (`tests/test_database.py`).

## Known limitations

* **Missing reprint:** 2025 rank 96,868 (an AFMS Round-2 seat) is missing from MCC's Round-3 PDF, so its
  reporting status is unknown.
* **Seat-matrix courses:** 34 seats (2025 AIQ) and 48 seats (2024 central-internal) could not be assigned to a
  course. Neighbouring multi-line cells overlap on the page. These seats are reported and left out.
* **Seat-matrix institutes:** about 75–83 % of seat-matrix institutes (52 % for central-internal) are linked to
  allotment institutes by name. Unmatched rows keep their printed name and MCC code.
* **Missing states:** 27 (2025) and 1 (2024) institute addresses name no state.
* **Not yet imported:** stray-round reporting status (no later PDF exists), vacancy lists, Round-2/3 seat
  matrices and quota-specific eligibility (NRI, minority, AFMS).
* **Eligibility rules:** `rules/eligibility.yaml` is drafted from the bulletins and agrees with every allotment in
  both years. It is marked `confirmed: false` until it has been reviewed.

## Adding a year

1. Download the documents: add title patterns for the year to `scripts/fetch_mcc_documents.py` and run it.
2. Check the result-PDF layouts. Print word positions for a few pages and compare them with
   `config/layouts.yaml`. Reuse a layout if the columns match, otherwise add one. The import refuses a wrong
   layout, because straddling words or unknown labels fail the hard checks.
3. Add the year to `config/sources.yaml` (rounds, `reporting_from`, seat matrices).
4. Add the year's rules to `rules/eligibility.yaml`, citing its bulletin.
5. If a course name is printed differently, add it as an `alias` in `config/courses.yaml`. Unknown names fail
   the import.
6. Run `docker compose run --rm pipeline check --year <year>`, then `import --year <year>`.
