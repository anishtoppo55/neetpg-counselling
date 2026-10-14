# Deploying the demo on Render (free tier)

This is a **testing deployment**. It is cheap (₹0) but has real limits, and the API is exposed to the internet
behind a shared secret rather than a private network. Read "Free-tier limits" and "Before you share the link"
before sending the URL to anyone.

Facts below are from Render's documentation ([free tier](https://render.com/docs/free),
[private network](https://render.com/docs/private-network), [blueprint spec](https://render.com/docs/blueprint-spec));
wording is paraphrased.

## What gets created

`render.yaml` in this directory is a Render Blueprint that creates three resources:

| Resource | Plan | Notes |
|---|---|---|
| `neetpg-db` – Postgres 16 | free | 1 GB storage, **expires 30 days after creation** |
| `neetpg-api` – predictor API | free | Public URL, locked with the `API_TOKEN` secret. Health check `/api/live` |
| `neetpg-web` – dashboard | free | Public URL, the only thing a visitor needs. Health check `/api/ping` |

Why the API is public: a free Render service can *make* private-network calls but cannot *receive* them, so the
dashboard cannot reach a free API privately. The blueprint therefore generates a random `API_TOKEN`, gives it to
both services, and the API rejects every request without it (except the health check). On a paid plan you would
instead make the API a private service and drop the token.

## 1. Push the code

The blueprint expects **this directory to be the repository root**:

```bash
cd counselling_platform
git init && git add -A && git commit -m "NEET PG counselling platform"
git remote add origin git@github.com:<you>/<repo>.git
git push -u origin main
```

`.gitignore` keeps `.env` and the ~150 MB of source PDFs out of the repository (`data/raw/manifest.csv` stays, so
provenance is still tracked). If you prefer to keep `counselling_platform` as a subdirectory of a larger repo,
prefix both `rootDir` values in `render.yaml` with it.

## 2. Create the services

> **One region for everything.** Every Render region has its own private network, so a service can only resolve
> a database's internal hostname if both sit in the same region. `render.yaml` pins the database and both
> services to `singapore`; if you change it, change all three. Databases default to `oregon` when the field is
> omitted, which is exactly how the first deploy of this project failed
> (`error connecting in 'pool-1': [Errno -2] Name or service not known`, then a health-check timeout).
> Region cannot be changed after a resource is created — you have to delete and recreate it.


1. Render dashboard → **New** → **Blueprint**.
2. Pick the repository. Render reads `render.yaml` and lists the database and two services.
3. **Apply**. The first build takes roughly 5–10 minutes (two Docker images).
4. **Tell the dashboard where the API is.** Copy the API's public URL from its service page, then
   `neetpg-web` → **Environment** → add:

   | Key | Value |
   |---|---|
   | `API_BASE_INTERNAL` | `https://neetpg-api-xxxx.onrender.com` |

   Save; the dashboard redeploys. This one variable cannot come from the blueprint: `fromService` only exposes a
   service's **internal** hostname (`host` / `hostport`), and a free service cannot *receive* private-network
   requests — so an internal address produces `fetch failed` in the dashboard. It is declared `sync: false` so
   re-syncing the blueprint will not overwrite what you set.

Render generates `API_TOKEN` once and copies it into both services, so you never type that one.

## 3. Load the counselling data

The images do not contain the PDFs — run the existing pipeline from your machine against the Render database, so
all the usual validation still applies.

1. Render → `neetpg-db` → **Connect** → copy the **External Database URL**.
2. Run the import locally (the local database is not involved):

```bash
cd counselling_platform
# keep the credential out of your shell history: store it once, readable only by you
umask 077 && printf '%s' 'postgresql://USER:PASSWORD@HOST.singapore-postgres.render.com/DBNAME?sslmode=require' > ~/.render_db.url

run() {                     # all three mounts matter: PDFs in, parse cache, validation reports out
  docker run --rm -e DATABASE_URL="$(cat ~/.render_db.url)" \
    -v "$PWD/data/raw:/data/raw:ro" \
    -v "$PWD/data/cache:/data/cache" \
    -v "$PWD/data/reports:/data/reports" \
    neetpg-pipeline:dev "$@"
}

run migrate
run import --year 2025 --year 2024
run status
```

`sslmode=require` is needed for external connections — without it the connection is refused. If
`neetpg-pipeline:dev` does not exist yet, build it with `docker compose build pipeline`.

Each year takes a few minutes: the PDFs are parsed locally and the rows are inserted across the network
(about 4 minutes per year from India to Singapore). The import is one transaction per year, so a dropped
connection leaves the previous data intact — just re-run it.

The database ends up around 115 MB, well inside the 1 GB limit. Expect a few minutes — the PDFs are parsed locally
and the rows are inserted over the network.

3. Render → `neetpg-db` → **Settings** → remove the `0.0.0.0/0` entry from the IP allow list once you are done,
   so only Render can reach the database. (It is in the blueprint purely to let you load the data.)

## 4. Check it

```bash
curl -s https://neetpg-api-XXXX.onrender.com/api/live        # {"status":"ok"} – liveness, no database
curl -s https://neetpg-api-XXXX.onrender.com/api/health      # {"status":"ok","data_version":N}
curl -s https://neetpg-api-XXXX.onrender.com/api/meta        # 401 – correct, the token is required
```

`/api/live` answers even when the database is down or empty, which is why it is the health-check path.
`/api/health` is the readiness probe: it returns 503 with `{"status":"degraded",…}` until the database is
reachable *and* migrated, so use it to confirm step 3 worked.

Then open `https://neetpg-web-XXXX.onrender.com`, enter a rank and category, and confirm the table fills.
Remember the first request after 15 idle minutes takes about a minute while the service wakes.

## Free-tier limits

* **The database expires 30 days after creation**, with a 14-day grace period before deletion. Either upgrade it
  before then or recreate it and re-run step 3. Nothing else is lost — the data is rebuilt from the PDFs.
* Services **sleep after 15 minutes** of no traffic and take about a minute to wake. The first page load after a
  nap is slow, and a prediction can take a few seconds while the reference cache refills.
* 750 free instance hours per workspace per month across all free services; exceeding them suspends them until
  the next month. Two services running continuously use more than that, which is another reason they sleep.
* Hobby bandwidth is 5 GB/month. The dashboard sends about 100–260 KB per page, so normal testing is fine, but
  avoid linking the unfiltered CSV export (1.4 MB per download) publicly.
* Free instances have 512 MB RAM. The API runs a single worker for that reason.

## Before you share the link

* **The eligibility rules are still unreviewed** (`confirmed: false`). Every prediction says so, which is the
  honest default for a public demo — but it is worth reviewing them first.
* The API has no rate limiting. The token keeps casual traffic out, but anyone who reads the dashboard's server
  responses cannot see it (verified: the token appears in neither the HTML nor the JS bundles), so the practical
  risk is low. Add Cloudflare or basic auth in front of the dashboard if you want access control for people.
* `DOCS_PUBLIC` is `false`, so `/docs` also needs the token. Set it to `true` if you want the API reference open.
* The disclaimers ("historical estimate, not a guarantee", "not an official MCC choice list", "not affiliated
  with MCC") are already in the UI and the CSV header. Keep them.
* Consider adding `X-Robots-Tag: noindex` or a `robots.txt` if you do not want the demo indexed.

## Updating

Pushing to the linked branch rebuilds and redeploys both services (`autoDeployTrigger: commit`). Data changes are
separate: re-run step 3 whenever you import another year or re-parse a document.

## Moving beyond the demo

When the demo stops being a demo:

1. Put the API on a paid plan and change `type: web` to `type: pserv` so it has no public URL; then drop
   `API_TOKEN` and wire the address automatically, which now works because a paid private service *can* receive
   private-network traffic:

   ```yaml
   - key: API_BASE_INTERNAL
     fromService: { name: neetpg-api, type: pserv, property: hostport }   # prefix with http:// in code
   ```
2. Put the dashboard on a paid plan to remove cold starts.
3. Upgrade Postgres so it does not expire, and take backups.
4. Add authentication if shortlists become per-user (Milestone 6 in `MILESTONES.md`).
