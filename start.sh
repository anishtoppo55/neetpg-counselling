#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# NEET PG Counselling Platform – one-command local start.
#
#   ./start.sh                 bring the whole stack up (db -> import -> api -> web)
#   ./start.sh --tests         ... and run the pipeline + API test suites
#   ./start.sh --rebuild       rebuild the images first
#   ./start.sh --force-import  re-import the years even if data is already loaded
#   ./start.sh --reset         DESTROY the database volume and import from scratch
#   ./start.sh --years "2025"  import only these years (default: all years in config)
#   ./start.sh --status | --logs [svc] | --stop | --down
#   ./start.sh --help
#
# This starts the DEVELOPMENT stack. For the production stack (Caddy + HTTPS, nothing but port 443
# published) and for deploying it to a small VM, see ./deploy/lightsail.sh and docs/deploy-lightsail.md.
#
# Everything binds to 127.0.0.1 only: this stack has no authentication (Phase 1).
# ---------------------------------------------------------------------------
set -Eeuo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ----------------------------------------------------------------- settings
DEFAULT_YEARS="2025 2024"
WAIT_DB=90          # seconds to wait for each service to become healthy
WAIT_API=90
WAIT_WEB=180        # the first web start compiles the app

RUN_TESTS=0 REBUILD=0 FORCE_IMPORT=0 RESET=0 SKIP_IMPORT=0 FETCH=0
YEARS="$DEFAULT_YEARS"

# ----------------------------------------------------------------- output helpers
if [[ -t 1 ]]; then
  BOLD=$'\e[1m'; DIM=$'\e[2m'; RED=$'\e[31m'; GREEN=$'\e[32m'; YELLOW=$'\e[33m'; BLUE=$'\e[34m'; OFF=$'\e[0m'
else
  BOLD='' DIM='' RED='' GREEN='' YELLOW='' BLUE='' OFF=''
fi
STEP=0
step()  { STEP=$((STEP + 1)); printf '\n%s[%d/%d] %s%s\n' "$BOLD$BLUE" "$STEP" "$TOTAL_STEPS" "$1" "$OFF"; }
info()  { printf '      %s\n' "$1"; }
ok()    { printf '      %s✓%s %s\n' "$GREEN" "$OFF" "$1"; }
warn()  { printf '      %s!%s %s\n' "$YELLOW" "$OFF" "$1"; }
die()   { printf '\n%serror:%s %s\n' "$RED$BOLD" "$OFF" "$1" >&2; exit 1; }
trap 'die "failed on line $LINENO (see the output above)"' ERR

# print the header comment block (everything between the shebang and the first line of code)
usage() { awk 'NR>1 && /^#/ {sub(/^# ?/, ""); print; next} NR>1 {exit}' "${BASH_SOURCE[0]}"; }

# ----------------------------------------------------------------- arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --tests|-t)      RUN_TESTS=1 ;;
    --rebuild|-r)    REBUILD=1 ;;
    --force-import)  FORCE_IMPORT=1 ;;
    --skip-import)   SKIP_IMPORT=1 ;;
    --reset)         RESET=1; REBUILD=1 ;;
    --fetch)         FETCH=1 ;;
    --years)         [[ -n "${2:-}" ]] || die '--years needs a value, e.g. --years "2025 2024"'; YEARS="$2"; shift ;;
    --status)        ACTION=status ;;
    --stop)          ACTION=stop ;;
    --down)          ACTION=down ;;
    --logs)          ACTION=logs; LOG_SVC="${2:-}"; [[ -n "$LOG_SVC" ]] && shift ;;
    --help|-h)       usage; exit 0 ;;
    *)               die "unknown option: $1 (try --help)" ;;
  esac
  shift
done

# ----------------------------------------------------------------- docker compose
command -v docker >/dev/null 2>&1 || die 'docker is not installed or not on PATH.'
docker info >/dev/null 2>&1 || die 'the docker daemon is not reachable. Start Docker and try again.'
if docker compose version >/dev/null 2>&1; then DC=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then DC=(docker-compose)
else die 'docker compose v2 (or docker-compose) is required.'; fi

dc() { "${DC[@]}" "$@"; }

# `docker compose up -d` for one service, with the progress chatter folded into our own indentation
up_quiet() {
  dc up -d "$@" 2>&1 | grep -vE '^ *(Container|Network|Volume|\[\+\]|✔) ' | sed 's/^/      /' || true
}

# health of a compose service: healthy | unhealthy | starting | none | missing
health() {
  local cid; cid="$(dc ps -q "$1" 2>/dev/null || true)"
  [[ -n "$cid" ]] || { echo missing; return; }
  docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{if .State.Running}}none{{else}}stopped{{end}}{{end}}' "$cid" 2>/dev/null || echo missing
}

wait_healthy() {
  local svc="$1" limit="$2" waited=0 state
  printf '      waiting for %s ' "$svc"
  while :; do
    state="$(health "$svc")"
    case "$state" in
      healthy|none) printf ' %s✓%s %s\n' "$GREEN" "$OFF" "$state"; return 0 ;;
      unhealthy)    printf '\n'; dc logs --tail 30 "$svc" || true; die "$svc reported unhealthy." ;;
    esac
    (( waited >= limit )) && { printf '\n'; dc logs --tail 40 "$svc" || true; die "$svc did not become healthy within ${limit}s."; }
    printf '.'; sleep 3; waited=$((waited + 3))
  done
}

# ----------------------------------------------------------------- side actions
case "${ACTION:-up}" in
  status)
    dc ps
    printf '\n'
    for s in db api web; do printf '%-5s %s\n' "$s" "$(health "$s")"; done
    if [[ "$(health db)" == healthy ]]; then dc run --rm pipeline status 2>&1 | grep -vE '^ *Container|^$' || true; fi
    exit 0 ;;
  logs)  dc logs -f --tail 100 ${LOG_SVC:+"$LOG_SVC"}; exit $? ;;   # note: `exec` cannot run a shell function
  stop)  dc stop; ok 'containers stopped (data kept). Start again with ./start.sh'; exit 0 ;;
  down)  dc down; ok 'containers removed (database volume kept). Use --reset to wipe the data too.'; exit 0 ;;
esac

TOTAL_STEPS=7
(( RUN_TESTS )) && TOTAL_STEPS=9
(( RESET )) && TOTAL_STEPS=$((TOTAL_STEPS + 1))

printf '%sNEET PG Counselling Platform%s  %slocal stack%s\n' "$BOLD" "$OFF" "$DIM" "$OFF"

# ----------------------------------------------------------------- 1. environment file
step 'Environment file'
if [[ -f .env ]]; then
  ok '.env exists'
else
  [[ -f .env.example ]] || die '.env.example is missing – are you in the counselling_platform directory?'
  cp .env.example .env
  pw="$(LC_ALL=C tr -dc 'A-Za-z0-9_-' </dev/urandom | head -c 32 || true)"
  [[ -n "$pw" ]] || pw="neetpg-$(date +%s)"
  # portable in-place edit (GNU and BSD sed)
  sed "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${pw}|" .env > .env.tmp && mv .env.tmp .env
  chmod 600 .env
  ok '.env created from .env.example with a random POSTGRES_PASSWORD'
fi
grep -q '^POSTGRES_PASSWORD=.\+' .env || die 'POSTGRES_PASSWORD is empty in .env – set it and re-run.'
set -a; . ./.env; set +a
API_PORT="${API_PORT:-8000}"; WEB_PORT="${WEB_PORT:-3000}"

# ----------------------------------------------------------------- 2. source documents
step 'Source documents'
pdfs=$(find data/raw -name '*.pdf' 2>/dev/null | wc -l | tr -d ' ')
if (( pdfs == 0 )) || (( FETCH )); then
  if (( FETCH )) || [[ -t 0 ]]; then
    if (( ! FETCH )); then
      warn "no PDFs found in data/raw."
      read -r -p '      Download them from mcc.nic.in now? [y/N] ' reply
      [[ "$reply" =~ ^[Yy]$ ]] || die 'no source documents – run: python3 scripts/fetch_mcc_documents.py'
    fi
    command -v python3 >/dev/null 2>&1 || die 'python3 is needed to download the documents.'
    info 'downloading official MCC/NBEMS documents (~200 MB, a few minutes)…'
    python3 scripts/fetch_mcc_documents.py
    pdfs=$(find data/raw -name '*.pdf' | wc -l | tr -d ' ')
  else
    die 'no PDFs in data/raw – run: python3 scripts/fetch_mcc_documents.py'
  fi
fi
ok "$pdfs source PDFs in data/raw"
mkdir -p data/cache data/reports

# ----------------------------------------------------------------- 3. optional reset
if (( RESET )); then
  step 'Reset database'
  warn 'this deletes the PostgreSQL volume; the data is rebuilt from the PDFs.'
  if [[ -t 0 ]]; then
    read -r -p '      Type "reset" to confirm: ' reply
    [[ "$reply" == reset ]] || die 'aborted.'
  fi
  dc down -v
  ok 'volumes removed'
fi

# ----------------------------------------------------------------- 4. images
step 'Images'
if (( REBUILD )); then
  info 'building pipeline, api and web…'
  dc build pipeline api web
else
  # build only what is missing
  missing=()
  for pair in 'neetpg-pipeline:dev pipeline' 'neetpg-api:dev api' 'neetpg-web:dev web'; do
    set -- $pair
    docker image inspect "$1" >/dev/null 2>&1 || missing+=("$2")
  done
  if (( ${#missing[@]} )); then
    info "building: ${missing[*]}"
    dc build "${missing[@]}"
  else
    ok 'images present (use --rebuild to refresh)'
  fi
fi

# ----------------------------------------------------------------- 5. database
step 'Database'
up_quiet db
wait_healthy db "$WAIT_DB"

PGUSER_="${POSTGRES_USER:-neetpg}"; PGDB_="${POSTGRES_DB:-neetpg}"
RECREATE_APPS=0

# Does the password in .env actually open the database? (host "db", so the loopback trust rule does not apply)
creds_ok() {
  dc exec -T -e PGPASSWORD="$POSTGRES_PASSWORD" db \
     psql -h db -U "$PGUSER_" -d "$PGDB_" -Atq -c 'select 1' >/dev/null 2>&1
}

if creds_ok; then
  ok 'database credentials match .env'
else
  warn 'POSTGRES_PASSWORD in .env does not match the password stored in the database volume.'
  info 'this happens when .env is edited after the volume was first created – syncing the role password…'
  # loopback inside the container is trusted by the default pg_hba, so the role password can be reset safely
  if dc exec -T db psql -h 127.0.0.1 -U "$PGUSER_" -d "$PGDB_" -Atq \
        -c "ALTER ROLE \"$PGUSER_\" WITH PASSWORD '${POSTGRES_PASSWORD//\'/\'\'}'" >/dev/null 2>&1 && creds_ok; then
    ok 'role password synced with .env – no data lost'
    RECREATE_APPS=1          # api/web carry the old password in their environment
  else
    die "cannot open the database with the password in .env.
      Either restore the previous POSTGRES_PASSWORD in .env, or wipe the data and rebuild it:
        ./start.sh --reset"
  fi
fi

dc run --rm pipeline migrate 2>&1 | grep -vE '^ *Container|^$' | sed 's/^/      /' || true

# ----------------------------------------------------------------- 6. data import
step 'Counselling data'
loaded=$(dc exec -T -e PGPASSWORD="$POSTGRES_PASSWORD" db \
         psql -h db -U "$PGUSER_" -d "$PGDB_" -Atq \
         -c "SELECT coalesce(string_agg(year::text, ' ' ORDER BY year), '') FROM counselling_year" 2>/dev/null \
         | tr -d '\r' || true)
if (( SKIP_IMPORT )); then
  warn "skipping import (--skip-import). Loaded years: ${loaded:-none}"
elif [[ -n "$loaded" ]] && (( ! FORCE_IMPORT )); then
  ok "already loaded: $loaded  (use --force-import to re-import)"
else
  args=(); for y in $YEARS; do args+=(--year "$y"); done
  info "importing ${YEARS// /, } – about 35 s per year on the first run"
  dc run --rm pipeline import "${args[@]}" 2>&1 | grep -vE '^ *Container' | sed 's/^/      /'
fi
dc run --rm pipeline status 2>&1 | grep -vE '^ *Container|^$' | sed 's/^/      /' || true

# ----------------------------------------------------------------- 7/8. tests
if (( RUN_TESTS )); then
  step 'Pipeline tests'
  dc run --rm --entrypoint pytest pipeline -q 2>&1 | grep -vE '^ *Container' | tail -3 | sed 's/^/      /'
fi

# ----------------------------------------------------------------- API
step 'Predictor API'
if (( RECREATE_APPS )); then
  info 'recreating api/web so they pick up the synced password'
  up_quiet --force-recreate api
else
  up_quiet api
fi
wait_healthy api "$WAIT_API"
if command -v curl >/dev/null 2>&1; then
  curl -fsS "http://127.0.0.1:${API_PORT}/api/health" | sed 's/^/      /' || warn 'health endpoint did not answer yet'
  printf '\n'
fi
if (( RUN_TESTS )); then
  step 'API tests'
  dc exec -T api pytest -q | tail -3 | sed 's/^/      /'
fi

# ----------------------------------------------------------------- web
step 'Dashboard'
if (( RECREATE_APPS )); then up_quiet --force-recreate web; else up_quiet web; fi
wait_healthy web "$WAIT_WEB"
if command -v curl >/dev/null 2>&1; then
  code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${WEB_PORT}/" || true)
  [[ "$code" == 200 ]] && ok "dashboard answered HTTP 200" || warn "dashboard returned HTTP ${code:-no response} (it may still be compiling)"
fi

# ----------------------------------------------------------------- summary
cat <<EOF

${GREEN}${BOLD}Ready.${OFF}
  Dashboard    http://127.0.0.1:${WEB_PORT}
  API docs     http://127.0.0.1:${API_PORT}/docs
  Example      http://127.0.0.1:${WEB_PORT}/?rank=30000&category=ST&quota=AI&year=2025&groups=Clinical&degrees=MD%2FMS

  ${DIM}./start.sh --status      what is running and what is loaded
  ./start.sh --logs web    follow logs (db | api | web | pipeline)
  ./start.sh --tests       re-run both test suites
  ./start.sh --stop        stop the containers, keep the data${OFF}

${DIM}Local use only: every port is bound to 127.0.0.1 and nothing here has authentication.
Results are historical MCC cut-offs – estimates, not admission guarantees.${OFF}
EOF
