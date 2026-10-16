# Deploying to AWS Lightsail

A single Lightsail instance running the whole stack with `docker compose`, behind Caddy for free
automatic HTTPS, on a free DuckDNS hostname. Budget: **$7/month**, no domain name needed.

This is the deployment path for the project. It replaced an earlier free-tier PaaS demo, whose managed database
was deleted 30 days after creation and whose services slept after 15 minutes idle; that blueprint has been
removed. What one small VM buys instead:

| | Free-tier PaaS | Lightsail $7 instance |
| --- | --- | --- |
| Database | 1 GB, deleted after 30 days | 40 GB disk, yours |
| Sleeping | after 15 min idle, ~1 min cold start | never |
| API exposure | public, needs a shared secret | private, Docker network only |
| Cost | $0 | $7/month |
| Who operates it | the platform | you (patching, backups) |

---

## 1. What gets deployed

```
                       internet
                          │  443/tcp, 443/udp, 80/tcp
┌─────────────────────────┼──────────────────────────────┐
│ Lightsail instance      ▼                              │
│   ┌────────┐   caddy  (TLS, Let's Encrypt, gzip)       │
│   └───┬────┘                                           │
│       │ web:3000                                       │
│   ┌───▼────┐   web    Next.js standalone server        │
│   └───┬────┘                                           │
│       │ api:8000      ← not published to the internet  │
│   ┌───▼────┐   api    FastAPI predictor                │
│   └───┬────┘                                           │
│       │ db:5432       ← not published to the internet  │
│   ┌───▼────┐   db     PostgreSQL 16 + named volume     │
│   └────────┘                                           │
└────────────────────────────────────────────────────────┘
```

Caddy is the only container with published ports. Every page in the dashboard renders on the server, and
no browser code calls the predictor API, so the API needs no public URL and therefore no `API_TOKEN` — the
`API_TOKEN` shared secret, which a publicly reachable API would need, is simply unnecessary here.

Files involved:

| Path | What it is |
| --- | --- |
| `deploy/docker-compose.prod.yml` | the production stack (no `build:` keys – the instance never compiles) |
| `deploy/Caddyfile` | TLS, security headers, reverse proxy to `web:3000` |
| `deploy/env.prod.example` | template for `deploy/.env.prod` (hostname, TLS email, DB password) |
| `deploy/lightsail.sh` | build, ship, start, load data, check |
| `api/Dockerfile.prod`, `web/Dockerfile.prod` | the production images (the plain `Dockerfile`s are for development) |

**The images are built on your machine and shipped over SSH.** This is the one design decision that makes
the $7 plan work: a Next.js production build needs well over 1 GB of memory and would be killed on the
instance. `docker save | ssh … docker load` moves about 140 MB over the wire instead (measured; the
`docker images` figures of 267 MB and 321 MB are unpacked sizes, and layers travel compressed).

---

## 2. Pick a plan

Lightsail dual-stack (IPv4 + IPv6) Linux bundles, from the
[Lightsail pricing page](https://aws.amazon.com/lightsail/pricing/) and
[CPU baseline table](https://docs.aws.amazon.com/lightsail/latest/userguide/baseline-cpu-performance.html):

| Price/month | RAM | vCPU | SSD | Transfer | CPU baseline | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| $5 | 512 MB | 2 | 20 GB | 1 TB | 5% | too small – Postgres plus two Node/Python servers will not fit |
| **$7** | **1 GB** | **2** | **40 GB** | **2 TB** | **10%** | **what this guide uses** |
| $12 | 2 GB | 2 | 60 GB | 3 TB | 20% | comfortable headroom; what to pick if the budget allows |

Measured with `docker stats` after exercising the dashboard, with both years loaded:

| Container | Memory |
| --- | --- |
| `web` (Next.js standalone) | 120 MiB |
| `db` (PostgreSQL 16) | 91 MiB |
| `api` (uvicorn, 1 worker) | 64 MiB |
| `caddy` | 13 MiB |
| **total** | **289 MiB** |

On a real $7 instance the containers settle at a similar 263 MiB, but `free -m` reports **587 MB used of 909
and ~320 MB available, with ~54 MB of swap in use** — Ubuntu's own services and the kernel's page cache
account for the rest. It works, and has worked under the full test sweep, but the headroom is thin: there is
no room for a second workload, and a memory-hungry addition (a second API worker, an LLM client, a build)
will push it into swap. `lightsail.sh bootstrap` adds the 2 GB swap file for exactly that reason, so the
box degrades instead of getting OOM-killed. If you want comfort rather than "fits", the $12 / 2 GB plan is
the upgrade, and Lightsail can resize from a snapshot.

Notes before you click:

- **Region.** Asia Pacific (Mumbai), `ap-south-1`, is closest to Indian users. Mumbai (and Sydney, Jakarta,
  Malaysia, Hong Kong, São Paulo) include **half** the listed transfer allowance, so 1 TB rather than 2 TB
  on the $7 plan. Still far more than this dashboard will ever use.
- **IPv6-only bundles are cheaper** ($5 for the same 1 GB specs) but unreachable from IPv4-only networks.
  Not worth it for links you want to share.
- A **static IP** is free while attached to a running instance. Attach one — DuckDNS points at it, and
  Let's Encrypt validates against it.
- New AWS accounts get free credits, and the $5 plan has a one-month free trial. Check your own account;
  don't assume.
- Snapshots are $0.05/GB-month and billed separately from the bundle.

---

## 3. Get a free hostname

Let's Encrypt will not issue a certificate for a bare IP address, so a hostname is required.
**[DuckDNS](https://www.duckdns.org)** is the right pick here:

- free, up to 5 subdomains, sign in with an existing GitHub/Google/Reddit account;
- the name is stable, unlike a Cloudflare quick tunnel whose `*.trycloudflare.com` URL changes on every
  restart;
- `duckdns.org` is on the [Public Suffix List](https://publicsuffix.org/list/), so
  `yourname.duckdns.org` gets its **own** Let's Encrypt rate-limit budget. `sslip.io` and `nip.io` (which
  need no signup at all) are *not* on the list, so every user of those services shares one bucket of
  50 certificates per week — fine until it isn't, and then you cannot renew.

Steps:

1. Sign in at <https://www.duckdns.org>, add a subdomain, e.g. `neetpg-demo`.
2. Copy your account **token** (shown at the top of the page).
3. Once the instance has a static IP, paste it into the subdomain's `current ip` field and press *update ip*.

A Lightsail static IP never changes, so there is nothing to automate — no updater cron job is needed.
If you ever move the instance, either edit the field again or call:

```bash
curl "https://www.duckdns.org/update?domains=neetpg-demo&token=YOUR_TOKEN&ip=NEW_IP"
```

Confirm it resolves before continuing, or Caddy's first certificate request will fail:

```bash
dig +short neetpg-demo.duckdns.org      # must print the static IP
```

---

## 4. Create the instance

In the [Lightsail console](https://lightsail.aws.amazon.com):

1. **Create instance** → region *Asia Pacific (Mumbai)*.
2. Platform **Linux/Unix** → blueprint **OS Only → Ubuntu 24.04 LTS**.
   Do *not* pick an app blueprint; they pre-install Apache or Nginx that would fight Caddy for port 80.
3. Plan: **$7/month, 1 GB**.
4. Name it, e.g. `neetpg`, then **Create instance**.
5. **Networking → Static IPs → Create static IP**, attach it to the instance.
6. **Instance → Networking → IPv4 Firewall.** Keep only what is needed:

   | Application | Protocol | Port | Restricted to |
   | --- | --- | --- | --- |
   | SSH | TCP | 22 | **your IP address** |
   | HTTP | TCP | 80 | anywhere |
   | HTTPS | TCP | 443 | anywhere |
   | Custom | UDP | 443 | anywhere (HTTP/3 – optional) |

   Port 80 has to stay open: Let's Encrypt validates over it, and Caddy uses it for the HTTPS redirect.
   Delete any other default rule. Postgres (5432) and the API (8000) must **never** appear here; the
   compose file does not publish them, and the firewall is the second line of defence.
7. **Account → SSH keys** → download the region's default private key (`.pem`), or upload your own.
   Then `chmod 600` it.

Check you can get in:

```bash
chmod 600 ~/Downloads/LightsailDefaultKey-ap-south-1.pem
ssh -i ~/Downloads/LightsailDefaultKey-ap-south-1.pem ubuntu@<STATIC_IP>
```

---

## 5. Configure the deployment

```bash
cd counselling_platform
cp deploy/env.prod.example deploy/.env.prod
chmod 600 deploy/.env.prod
```

Edit `deploy/.env.prod`:

```ini
SITE_HOST=neetpg-demo.duckdns.org
TLS_EMAIL=you@example.com                  # enables Let's Encrypt; expiry notices go here
POSTGRES_DB=neetpg
POSTGRES_USER=neetpg
POSTGRES_PASSWORD=<openssl rand -base64 24 | tr -d '/+=' | cut -c1-28>
DB_POOL_MAX=3

SSH_HOST=ubuntu@<STATIC_IP>
SSH_KEY=~/Downloads/LightsailDefaultKey-ap-south-1.pem
```

`deploy/.env.prod` is git-ignored, as are `*.pem` files.

---

## 6. Smoke-test locally first

Verify the production stack on your own machine before spending anything. `TLS_EMAIL=internal` makes Caddy
issue its own self-signed certificate, so no ACME request leaves the machine.

```bash
./deploy/lightsail.sh build        # neetpg-api:prod (~267 MB), neetpg-web:prod (~321 MB)
./deploy/lightsail.sh local        # needs ports 80 and 443 free
./deploy/lightsail.sh data --local # copy the data in from the dev stack (./start.sh must be running)

curl -ks -o /dev/null -w '%{http_code}\n' https://localhost/        # 200
curl -s  -o /dev/null -w '%{http_code}\n' http://localhost/         # 308 redirect to https
curl -ks https://localhost/api/ping                                 # {"ok":true,...}

./deploy/lightsail.sh local-down   # removes its containers and volumes
```

The local production stack uses the compose project name `neetpg-prod`, so it has its own volumes and
cannot disturb the development stack or its database.

---

## 7. Deploy

```bash
./deploy/lightsail.sh bootstrap    # installs Docker, 2 GB swap, log rotation, creates ~/neetpg
./deploy/lightsail.sh deploy       # build + upload images and config + start + check the public URL
./deploy/lightsail.sh data         # pg_dump the dev database, restore it on the instance
./deploy/lightsail.sh check
```

What each step does:

- **bootstrap** — Docker from `get.docker.com`, a 2 GB swap file with `vm.swappiness=10`, container log
  rotation capped at 3 × 10 MB so logs cannot fill the 40 GB disk.
- **deploy** — builds both production images locally, pipes them through `gzip` into `docker load` on the
  instance, uploads `docker-compose.prod.yml`, `Caddyfile` and `.env` (mode 600), then `docker compose up -d`.
  Expect a few minutes on the image upload; it is the only slow part and only repeats when the images change.
- **data** — `pg_dump` of the running development database (≈2.5 MB gzipped) restored into the instance's
  Postgres, then restarts the API so it re-reads its data version. This is much lighter than re-parsing
  149 MB of PDFs on a 1 GB box.

Caddy needs up to a minute after the first start to obtain the certificate. `check` requests the public URL
and reports the status of each page.

Then share `https://neetpg-demo.duckdns.org`.

---

## 8. Operating it

```bash
./deploy/lightsail.sh status       # uptime, memory, disk, containers, rows loaded per year
./deploy/lightsail.sh logs caddy   # or db | api | web
./deploy/lightsail.sh ssh          # shell in ~/neetpg
./deploy/lightsail.sh restart
./deploy/lightsail.sh down         # stop the containers; volumes (data, certificates) are kept
```

**Shipping a code change**

```bash
./deploy/lightsail.sh deploy       # rebuild, re-upload, recreate
```

The database is untouched; only the two application images are replaced.

**Adding another year of data**

Import it locally first — that is where the PDFs and the pipeline live:

```bash
./start.sh --years "2023" --force-import
./deploy/lightsail.sh data         # replaces the instance's database with the new local one
```

`pg_dump --clean --if-exists` means `data` is repeatable; it drops and recreates the schema each time.

**Backups**

Lightsail snapshots cover the whole disk, including the Postgres volume:
*Instance → Snapshots → Enable automatic snapshots* (daily, $0.05/GB-month, ~$0.35/month for a 7 GB used
disk). A logical backup is cheaper still:

```bash
ssh -i "$SSH_KEY" "$SSH_HOST" 'cd ~/neetpg && docker compose --env-file .env -f docker-compose.prod.yml \
  exec -T db pg_dump -U neetpg neetpg | gzip' > neetpg-backup-$(date +%F).sql.gz
```

(`SSH_KEY` and `SSH_HOST` are the values from `deploy/.env.prod`.)

**Patching**

```bash
./deploy/lightsail.sh ssh
sudo apt update && sudo apt upgrade -y && sudo reboot
```

`restart: unless-stopped` brings every container back after a reboot.

**Keeping the bill at $7**

Only the instance bundle is billed on this setup. Watch for: a second static IP left detached (billed when
unattached), snapshots piling up, and a load balancer or managed database accidentally created — a Lightsail
managed Postgres starts at $15/month, more than the instance itself.

---

## 9. Security notes

What this setup does:

- Postgres and the API have no published ports; only Caddy listens on the public interface.
- HTTPS everywhere, with HTTP redirecting to it, plus HSTS, `nosniff`, `X-Frame-Options: DENY`,
  a strict referrer policy and `X-Robots-Tag: noindex, nofollow` (this is a personal research aid working
  with derived data — it should not turn up in search results).
- The database password lives only in `deploy/.env.prod` locally and `~/neetpg/.env` (mode 600) on the box.
- SSH is restricted to your own IP by the Lightsail firewall.

What it does **not** do:

- **No authentication.** Anyone with the link sees the dashboard. There are no accounts and no rate
  limiting, so treat the URL as semi-private and expect to rotate the hostname if it spreads.
- No WAF, no DDoS protection beyond what AWS does by default.
- Uncommenting the `/api/*` block in the `Caddyfile` publishes the JSON API and `/docs`. Set `API_TOKEN`
  on the `api` service first — that block otherwise removes the only thing keeping the API private.

---

## 10. Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `./deploy/lightsail.sh check` → 000 on every path | DNS or firewall | `dig +short $SITE_HOST` must return the static IP; confirm 80 and 443 are open |
| Caddy logs `could not get certificate` / ACME 403 | the hostname does not resolve to this instance yet, or port 80 is blocked | fix DNS, open port 80, then `./deploy/lightsail.sh restart` |
| Pages load but show "Cannot reach the predictor API" | the `api` container is unhealthy | `./deploy/lightsail.sh logs api` |
| The dashboard renders but every number is empty | the database has no data | `./deploy/lightsail.sh data` |
| `api` keeps restarting right after `deploy` | `POSTGRES_PASSWORD` in `.env` differs from the password inside the existing `pgdata` volume | either restore the old password, or `ssh` in and `docker compose … down -v` to start the database over, then re-run `data` |
| `docker: permission denied` during `bootstrap` | the `docker` group membership is not active in that session | harmless — the script reconnects for each command; re-run it |
| Out-of-memory kills | not enough RAM | confirm swap is on (`free -m`), otherwise move to the $12 / 2 GB plan |

**Never run `docker compose build` on the instance.** The Next.js build will be OOM-killed on 1 GB, and may
take the running containers with it. Build locally and ship, which is what `deploy` does.
