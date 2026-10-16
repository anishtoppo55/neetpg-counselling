#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# NEET PG Counselling Platform – deploy the production stack to an AWS Lightsail instance.
#
# The images are built HERE and shipped as a tarball over SSH. The instance never compiles anything,
# which is what makes the $5/month 1 GB plan viable (a Next.js build needs far more memory than that).
#
# Typical first run:
#   cp deploy/env.prod.example deploy/.env.prod   &&  edit it (SITE_HOST, TLS_EMAIL, POSTGRES_PASSWORD)
#   ./deploy/lightsail.sh local                   # smoke-test the prod stack on this machine first
#   ./deploy/lightsail.sh local-down
#   ./deploy/lightsail.sh bootstrap               # install Docker + swap on the instance
#   ./deploy/lightsail.sh deploy                  # build + ship + start
#   ./deploy/lightsail.sh data                    # copy the counselling data up from the dev stack
#   ./deploy/lightsail.sh check                   # verify the public HTTPS URL
#
# Commands
#   local        run the production stack on this machine (self-signed TLS) for a smoke test
#   local-down   stop it and remove its volumes
#   bootstrap    install Docker, add a 2 GB swap file and create ~/neetpg on the instance
#   build        build neetpg-api:prod and neetpg-web:prod locally
#   ship         upload the compose file, Caddyfile, .env and the two images
#   up|down      start / stop the stack on the instance
#   restart      recreate the containers on the instance
#   deploy       build + ship + up
#   data         pg_dump the dev database and restore it on the instance (add --local for the local stack)
#   status       container state and loaded data on the instance
#   logs [svc]   follow logs (db | api | web | caddy)
#   check        request the public URL and report what came back
#   ssh          open a shell on the instance
#
# Options
#   --host user@ip    SSH target      (default: SSH_HOST from deploy/.env.prod)
#   --key  path.pem   SSH private key (default: SSH_KEY  from deploy/.env.prod)
#   --env  path       environment file (default: deploy/.env.prod)
#   --yes             do not ask for confirmation on destructive steps
# ---------------------------------------------------------------------------
set -Eeuo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
cd "$ROOT"

REMOTE_DIR='~/neetpg'                 # expanded by the remote shell, not here
ENV_FILE="$HERE/.env.prod"
COMPOSE_FILE="$HERE/docker-compose.prod.yml"
IMAGES=(neetpg-api:prod neetpg-web:prod)
ASSUME_YES=0
DATA_LOCAL=0

# Allotments per year. `allotment` carries round_id, not year, so it joins through `round`.
COUNT_SQL="select 'allotments ' || r.year || ': ' || count(*) from allotment a join round r on r.id = a.round_id group by r.year order by r.year"

# ----------------------------------------------------------------- output helpers
if [[ -t 1 ]]; then
  BOLD=$'\e[1m'; DIM=$'\e[2m'; RED=$'\e[31m'; GREEN=$'\e[32m'; YELLOW=$'\e[33m'; BLUE=$'\e[34m'; OFF=$'\e[0m'
else
  BOLD='' DIM='' RED='' GREEN='' YELLOW='' BLUE='' OFF=''
fi
step() { printf '\n%s==>%s %s%s\n' "$BOLD$BLUE" "$OFF$BOLD" "$1" "$OFF"; }
info() { printf '    %s\n' "$1"; }
ok()   { printf '    %s✓%s %s\n' "$GREEN" "$OFF" "$1"; }
warn() { printf '    %s!%s %s\n' "$YELLOW" "$OFF" "$1"; }
die()  { printf '\n%serror:%s %s\n' "$RED$BOLD" "$OFF" "$1" >&2; exit 1; }
trap 'die "failed on line $LINENO (see the output above)"' ERR
usage() { awk 'NR>1 && /^#/ {sub(/^# ?/, ""); print; next} NR>1 {exit}' "${BASH_SOURCE[0]}"; }

confirm() {
  (( ASSUME_YES )) && return 0
  [[ -t 0 ]] || die "$1 (re-run with --yes in a non-interactive shell)"
  read -r -p "    $1 [y/N] " reply
  [[ "$reply" =~ ^[Yy]$ ]] || die 'aborted.'
}

# ----------------------------------------------------------------- arguments
CMD=''
ARG=''
while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) [[ -n "${2:-}" ]] || die '--host needs a value, e.g. --host ubuntu@13.200.0.1'; SSH_HOST_OPT="$2"; shift ;;
    --key)  [[ -n "${2:-}" ]] || die '--key needs a path to a .pem file'; SSH_KEY_OPT="$2"; shift ;;
    --env)  [[ -n "${2:-}" ]] || die '--env needs a path'; ENV_FILE="$2"; shift ;;
    --yes|-y) ASSUME_YES=1 ;;
    --local)  DATA_LOCAL=1 ;;
    --help|-h) usage; exit 0 ;;
    -*) die "unknown option: $1 (try --help)" ;;
    *)  if [[ -z "$CMD" ]]; then CMD="$1"; else ARG="$1"; fi ;;
  esac
  shift
done
[[ -n "$CMD" ]] || { usage; exit 0; }

# ----------------------------------------------------------------- docker / compose on this machine
command -v docker >/dev/null 2>&1 || die 'docker is not installed or not on PATH.'
docker info >/dev/null 2>&1 || die 'the docker daemon is not reachable. Start Docker and try again.'
docker compose version >/dev/null 2>&1 || die 'docker compose v2 is required.'

# ----------------------------------------------------------------- environment file
load_env() {
  [[ -f "$ENV_FILE" ]] || die "$ENV_FILE is missing. Create it:
      cp deploy/env.prod.example deploy/.env.prod
    then set SITE_HOST, TLS_EMAIL and POSTGRES_PASSWORD."
  set -a; . "$ENV_FILE"; set +a
  [[ -n "${SITE_HOST:-}" && "$SITE_HOST" != changeme* ]] || die "SITE_HOST is not set in $ENV_FILE."
  [[ -n "${POSTGRES_PASSWORD:-}" && "$POSTGRES_PASSWORD" != changeme ]] \
    || die "POSTGRES_PASSWORD is still the placeholder in $ENV_FILE.
      Generate one:  openssl rand -base64 24 | tr -d '/+=' | cut -c1-28"
  PGUSER_="${POSTGRES_USER:-neetpg}"; PGDB_="${POSTGRES_DB:-neetpg}"
}

# ----------------------------------------------------------------- ssh plumbing
ssh_setup() {
  SSH_TARGET="${SSH_HOST_OPT:-${SSH_HOST:-}}"
  [[ -n "$SSH_TARGET" ]] || die "no SSH target. Pass --host ubuntu@<static-ip> or set SSH_HOST in $ENV_FILE."
  # These two are fine for a local smoke test but useless on a public box.
  [[ "$SITE_HOST" != localhost && "$SITE_HOST" != 127.0.0.1 ]] \
    || die "SITE_HOST is '$SITE_HOST' in $ENV_FILE. Set it to the public hostname that resolves to this
      instance's static IP, e.g. yourname.duckdns.org – Caddy requests a certificate for exactly that name."
  [[ "${TLS_EMAIL:-internal}" != internal ]] \
    || die "TLS_EMAIL is 'internal' in $ENV_FILE, which makes Caddy issue a self-signed certificate that every
      browser rejects. Set it to your email address to enable Let's Encrypt."
  SSH_ARGS=(-o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30 -o ConnectTimeout=15)
  local key="${SSH_KEY_OPT:-${SSH_KEY:-}}"
  if [[ -n "$key" ]]; then
    key="${key/#\~/$HOME}"
    [[ -f "$key" ]] || die "SSH key not found: $key"
    # A Lightsail .pem must not be group/world readable or ssh refuses it.
    [[ "$(stat -c '%a' "$key" 2>/dev/null || echo 600)" == 600 ]] || { chmod 600 "$key"; info "fixed permissions on $key"; }
    SSH_ARGS+=(-i "$key")
  fi

  # Fail with something readable instead of a timeout buried inside a pipeline.
  local err
  if ! err=$(ssh "${SSH_ARGS[@]}" -o BatchMode=yes "$SSH_TARGET" true 2>&1); then
    die "cannot reach $SSH_TARGET over SSH.
      ssh said: ${err:-no output}
      Check: the instance is running, SSH_KEY points at the right .pem, the Lightsail IPv4 firewall allows
      TCP 22 from your current IP address, and SSH_HOST uses the STATIC IP with the right user (ubuntu on
      Lightsail's Ubuntu blueprints, bitnami on the app blueprints)."
  fi
}
remote()  { ssh "${SSH_ARGS[@]}" "$SSH_TARGET" "$@"; }
# docker compose on the instance, with the uploaded env file
rdc() { remote "cd $REMOTE_DIR && docker compose --env-file .env -f docker-compose.prod.yml $*"; }

# docker compose for the production stack on THIS machine
ldc() { docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"; }

# ----------------------------------------------------------------- building
do_build() {
  step 'Building production images'
  info 'api  (python:3.12-slim + FastAPI)'
  docker build -q -f api/Dockerfile.prod -t neetpg-api:prod ./api | sed 's/^/    /'
  info 'web  (multi-stage Next.js standalone – this is the slow one)'
  docker build -q -f web/Dockerfile.prod -t neetpg-web:prod ./web | sed 's/^/    /'
  for img in "${IMAGES[@]}"; do
    ok "$img  $(docker image inspect "$img" --format '{{.Size}}' | awk '{printf "%.0f MB", $1/1048576}')"
  done
}

# ----------------------------------------------------------------- instance bootstrap
do_bootstrap() {
  step "Preparing $SSH_TARGET"
  remote 'bash -se' <<'BOOTSTRAP'
set -Eeuo pipefail
echo "    host: $(. /etc/os-release && echo "$PRETTY_NAME"), $(nproc) vCPU, $(free -m | awk '/^Mem:/{print $2}') MB RAM"

if command -v docker >/dev/null 2>&1; then
  echo "    ✓ docker already installed ($(docker --version))"
else
  echo "    installing docker from get.docker.com …"
  curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
  sudo sh /tmp/get-docker.sh >/dev/null
  rm -f /tmp/get-docker.sh
  sudo usermod -aG docker "$USER"
  echo "    ✓ docker installed"
fi
sudo systemctl enable --now docker >/dev/null 2>&1 || true

# A 2 GB swap file is cheap insurance on a 1 GB instance: nothing is built here, but a Postgres
# maintenance job or a traffic spike must not trigger the OOM killer.
if [ "$(swapon --show --noheadings | wc -l)" -gt 0 ]; then
  echo "    ✓ swap already present ($(free -m | awk '/^Swap:/{print $2}') MB)"
else
  echo "    adding a 2 GB swap file …"
  sudo fallocate -l 2G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=2048 status=none
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile >/dev/null
  sudo swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
  # Prefer RAM, but allow swapping rather than dying.
  sudo sysctl -q vm.swappiness=10
  echo 'vm.swappiness=10' | sudo tee /etc/sysctl.d/99-neetpg.conf >/dev/null
  echo "    ✓ swap on"
fi

# Keep journald and docker logs from filling a 20-40 GB disk.
sudo mkdir -p /etc/docker
if [ ! -f /etc/docker/daemon.json ]; then
  printf '{\n  "log-driver": "json-file",\n  "log-opts": { "max-size": "10m", "max-file": "3" }\n}\n' \
    | sudo tee /etc/docker/daemon.json >/dev/null
  sudo systemctl restart docker
  echo "    ✓ docker log rotation capped at 30 MB per container"
fi

mkdir -p ~/neetpg
echo "    ✓ ~/neetpg ready"
BOOTSTRAP
  ok 'instance prepared'
  warn 'if docker was just installed, the group change needs a new login – this script reconnects each time, so it is fine.'
}

# ----------------------------------------------------------------- shipping
do_ship() {
  step "Uploading configuration to $SSH_TARGET:$REMOTE_DIR"
  remote "mkdir -p $REMOTE_DIR"
  # scp cannot expand ~ reliably across shells, so pipe a tar instead.
  tar -C "$HERE" -cf - docker-compose.prod.yml Caddyfile \
    | remote "tar -C $REMOTE_DIR -xf -"
  # .env is uploaded separately so it can be renamed, stripped of the SSH settings (which are only useful
  # on this side) and locked down.
  grep -vE '^[[:space:]]*(SSH_HOST|SSH_KEY)=' "$ENV_FILE" \
    | remote "cat > $REMOTE_DIR/.env && chmod 600 $REMOTE_DIR/.env"
  ok 'docker-compose.prod.yml, Caddyfile, .env'

  for img in "${IMAGES[@]}"; do
    docker image inspect "$img" >/dev/null 2>&1 || die "$img is not built. Run: ./deploy/lightsail.sh build"
  done

  step 'Uploading images'
  local bytes
  bytes=$(docker image inspect "${IMAGES[@]}" --format '{{.Size}}' | awk '{s+=$1} END {printf "%.0f", s/1000000}')
  info "${IMAGES[*]} – roughly ${bytes} MB over the wire"
  info 'this is the slow step; it only re-sends everything when the images change'
  # gzip is nearly free but also nearly pointless with the containerd image store, where `docker save`
  # already emits compressed layer blobs (measured: 140 MB -> 139 MB). It still pays off on older
  # daemons using the overlay2 graph driver, where saved layers come out uncompressed.
  if command -v pv >/dev/null 2>&1; then
    docker save "${IMAGES[@]}" | gzip | pv -petr | remote 'gunzip | docker load'
  else
    docker save "${IMAGES[@]}" | gzip | remote 'gunzip | docker load' | sed 's/^/    /'
  fi
  ok 'images loaded on the instance'
}

# ----------------------------------------------------------------- lifecycle
do_up() {
  step 'Starting the stack'
  # `--force-recreate api web`, not a plain `up -d`.
  #
  # A rebuilt image gets a new ID even when the source did not change, and `docker load` leaves the
  # previous ID in place, still referenced by the running container. Compose did not always notice, so a
  # container could keep serving the old image after a deploy claimed success - which would mean a real
  # code change silently failing to roll out. Recreating the two application containers unconditionally
  # costs a few seconds and removes the ambiguity. db and caddy are left alone so the database is not
  # bounced and the TLS certificate cache is untouched.
  # `--no-deps` keeps db and caddy out of it, so the two are recreated in order: api first, then web
  # once the API is answering, rather than both at once with web briefly pointing at nothing.
  rdc 'up -d --remove-orphans' | sed 's/^/    /'
  rdc 'up -d --force-recreate --no-deps api' | sed 's/^/    /'
  local waited=0
  printf '    waiting for the API '
  while (( waited < 90 )); do
    [[ "$(rdc 'ps --format "{{.Service}} {{.Health}}"' 2>/dev/null | awk '$1=="api"{print $2}')" == healthy ]] && break
    printf '.'; sleep 3; waited=$((waited + 3))
  done
  printf '\n'
  rdc 'up -d --force-recreate --no-deps web' | sed 's/^/    /'
  info 'waiting for the containers to report healthy…'
  local waited=0 state
  while (( waited < 180 )); do
    state=$(rdc 'ps --format "{{.Service}} {{.State}} {{.Health}}"' 2>/dev/null || true)
    if ! grep -qE 'starting|unhealthy' <<<"$state" && grep -q 'web' <<<"$state"; then break; fi
    printf '.'; sleep 5; waited=$((waited + 5))
  done
  printf '\n'
  rdc 'ps' | sed 's/^/    /'

  # Each deploy replaces a tag and leaves the previous image untagged. They are ~60 MB a pair and were
  # accumulating silently on a 40 GB disk. `prune -f` only removes dangling images, never a tagged one
  # or anything a container references, so the running stack and the rollback tags are untouched.
  local reclaimed
  reclaimed=$(remote 'docker image prune -f' 2>/dev/null | grep -i 'reclaimed' || true)
  [[ -n "$reclaimed" ]] && info "cleaned up old image layers – ${reclaimed#*: }"

  info "Caddy needs up to a minute to obtain the first certificate for ${SITE_HOST}."
}

do_check() {
  step "Checking https://${SITE_HOST}"
  command -v curl >/dev/null 2>&1 || die 'curl is needed for this check.'

  # Resolve first: a missing DNS record is by far the most common reason the certificate never arrives.
  if command -v dig >/dev/null 2>&1; then
    local ip; ip=$(dig +short "$SITE_HOST" | head -1)
    if [[ -n "$ip" ]]; then ok "$SITE_HOST resolves to $ip"
    else warn "$SITE_HOST does not resolve – point it at the instance's static IP (DuckDNS: set 'current ip')"; fi
  fi

  # curl prints 000 into %{http_code} when it cannot connect, and exits non-zero; keep both quiet.
  local code failed=0
  http_code() { curl -sS -o /dev/null -w '%{http_code}' --max-time "$2" "$1" 2>/dev/null || true; }
  for path in / /about /branches /api/ping; do
    code=$(http_code "https://${SITE_HOST}${path}" 30)
    if [[ "$code" == 200 ]]; then ok "GET ${path} -> 200"
    else warn "GET ${path} -> ${code:-no response}"; failed=1; fi
  done
  code=$(http_code "http://${SITE_HOST}/" 20)
  if [[ "$code" =~ ^30 ]]; then ok "http:// redirects to https (${code})"
  else warn "http:// returned ${code:-no response}, expected 301/308"; failed=1; fi

  if (( failed )); then
    printf '\n'
    warn 'not serving yet. Caddy can need a minute for its first certificate; after that, check:'
    info './deploy/lightsail.sh logs caddy     (look for "certificate obtained" or an ACME error)'
    info './deploy/lightsail.sh status'
    info 'the Lightsail IPv4 firewall must allow TCP 80 and 443 from anywhere'
    return 1
  fi

  # Did the dashboard actually reach the API and find data, or is it rendering an error card?
  if curl -sS --max-time 30 "https://${SITE_HOST}/" 2>/dev/null | grep -q 'Cannot reach the predictor API'; then
    warn 'the page loads but the dashboard cannot reach the API – ./deploy/lightsail.sh logs api'
  else
    ok 'the dashboard rendered server-side content'
  fi
  printf '\n    %sShare this:%s https://%s\n' "$BOLD" "$OFF" "$SITE_HOST"
}

# ----------------------------------------------------------------- data transfer
# Dump the development database and restore it into the production one. Far lighter on a 1 GB instance
# than re-parsing 149 MB of PDFs there (the pipeline needs the source tree, pdftotext and real memory).
do_data() {
  local dev_db
  dev_db=$(docker compose -f docker-compose.yml ps -q db 2>/dev/null || true)
  [[ -n "$dev_db" ]] || die 'the development database is not running. Start it first:  ./start.sh'

  # Credentials of the DEV stack live in the root .env, which may differ from the production password.
  local dev_user dev_name dev_pass
  dev_user=$(docker inspect "$dev_db" --format '{{range .Config.Env}}{{println .}}{{end}}' | sed -n 's/^POSTGRES_USER=//p')
  dev_name=$(docker inspect "$dev_db" --format '{{range .Config.Env}}{{println .}}{{end}}' | sed -n 's/^POSTGRES_DB=//p')
  dev_pass=$(docker inspect "$dev_db" --format '{{range .Config.Env}}{{println .}}{{end}}' | sed -n 's/^POSTGRES_PASSWORD=//p')
  dev_user="${dev_user:-neetpg}"; dev_name="${dev_name:-neetpg}"

  step 'Dumping the development database'
  local dump="${TMPDIR:-/tmp}/neetpg-$(date +%Y%m%d-%H%M%S).sql.gz"
  docker exec -i -e PGPASSWORD="$dev_pass" "$dev_db" \
    pg_dump -U "$dev_user" -d "$dev_name" --clean --if-exists --no-owner --no-privileges \
    | gzip > "$dump"
  ok "$(du -h "$dump" | cut -f1) -> $dump"

  if (( DATA_LOCAL )); then
    step 'Restoring into the local production stack'
    local target
    target=$(ldc ps -q db)
    [[ -n "$target" ]] || die 'the local production database is not running. Start it:  ./deploy/lightsail.sh local'
    gunzip -c "$dump" | docker exec -i -e PGPASSWORD="$POSTGRES_PASSWORD" "$target" \
      psql -q -U "$PGUSER_" -d "$PGDB_" >/dev/null
    ok 'restored locally'
  else
    step "Restoring into the database on $SSH_TARGET"
    info 'the dashboard will return errors while this runs (a minute or two)'
    gunzip -c "$dump" \
      | remote "cd $REMOTE_DIR && docker compose --env-file .env -f docker-compose.prod.yml exec -T \
                -e PGPASSWORD='$POSTGRES_PASSWORD' db psql -q -U '$PGUSER_' -d '$PGDB_'" >/dev/null
    ok 'restored on the instance'
    rdc "exec -T -e PGPASSWORD='$POSTGRES_PASSWORD' db psql -U '$PGUSER_' -d '$PGDB_' -Atq -c \
         \"$COUNT_SQL\"" | sed 's/^/    /' || true
    info 'restarting the API so it drops its cached data version'
    rdc 'restart api' >/dev/null
  fi
  rm -f "$dump"
}

do_status() {
  step "Instance $SSH_TARGET"
  remote 'uptime; echo; free -m | head -2; echo; df -h / | tail -1' | sed 's/^/    /'
  step 'Containers'
  rdc 'ps' | sed 's/^/    /'
  step 'Loaded data'
  rdc "exec -T -e PGPASSWORD='$POSTGRES_PASSWORD' db psql -U '$PGUSER_' -d '$PGDB_' -Atq -c \"$COUNT_SQL\"" \
    2>/dev/null | sed 's/^/    /' || warn 'could not query the database'
}

# ----------------------------------------------------------------- local smoke test
do_local() {
  step 'Production stack on this machine'
  for p in 80 443; do
    if command -v ss >/dev/null 2>&1 && ss -ltn "sport = :$p" 2>/dev/null | grep -q LISTEN; then
      die "port $p is already in use on this machine; free it before the local smoke test."
    fi
  done
  for img in "${IMAGES[@]}"; do
    docker image inspect "$img" >/dev/null 2>&1 || die "$img is not built. Run: ./deploy/lightsail.sh build"
  done
  info 'hostname localhost, self-signed certificate (SITE_HOST/TLS_EMAIL from .env.prod are overridden)'
  SITE_HOST=localhost TLS_EMAIL=internal ldc up -d --remove-orphans 2>&1 | sed 's/^/    /'
  local waited=0
  printf '    waiting for health '
  while (( waited < 180 )); do
    if ! SITE_HOST=localhost TLS_EMAIL=internal ldc ps --format '{{.Service}} {{.Health}}' | grep -qE 'starting|unhealthy'; then break; fi
    printf '.'; sleep 5; waited=$((waited + 5))
  done
  printf '\n'
  SITE_HOST=localhost TLS_EMAIL=internal ldc ps | sed 's/^/    /'
  cat <<EOF

    ${BOLD}Smoke test${OFF}
      curl -ks https://localhost/api/ping
      curl -ks -o /dev/null -w '%{http_code}\\n' https://localhost/
      open  https://localhost   ${DIM}(the browser will warn: the certificate is self-signed)${OFF}

    ${DIM}The database starts empty. Load it from the dev stack:
      ./deploy/lightsail.sh data --local
    Tear it down again:
      ./deploy/lightsail.sh local-down${OFF}
EOF
}

do_local_down() {
  step 'Removing the local production stack'
  confirm 'this deletes its database and certificate volumes. Continue?'
  SITE_HOST=localhost TLS_EMAIL=internal ldc down -v 2>&1 | sed 's/^/    /'
  ok 'removed (the development stack and its data are untouched)'
}

# ----------------------------------------------------------------- dispatch
case "$CMD" in
  build)      load_env; do_build ;;
  local)      load_env; do_local ;;
  local-down) load_env; do_local_down ;;
  bootstrap)  load_env; ssh_setup; do_bootstrap ;;
  ship)       load_env; ssh_setup; do_ship ;;
  up)         load_env; ssh_setup; do_up ;;
  down)       load_env; ssh_setup; step 'Stopping the stack'; rdc 'down' | sed 's/^/    /'
              ok 'containers removed; the database and certificate volumes are kept' ;;
  restart)    load_env; ssh_setup; step 'Recreating the containers'; rdc 'up -d --force-recreate' | sed 's/^/    /' ;;
  deploy)     load_env; ssh_setup; do_build; do_ship; do_up; do_check || true ;;
  data)       load_env; (( DATA_LOCAL )) || ssh_setup; do_data ;;
  status)     load_env; ssh_setup; do_status ;;
  logs)       load_env; ssh_setup; rdc "logs -f --tail 100 ${ARG}" ;;
  check)      load_env; do_check || exit 1 ;;
  ssh)        load_env; ssh_setup; exec ssh "${SSH_ARGS[@]}" -t "$SSH_TARGET" "cd $REMOTE_DIR && exec \$SHELL -l" ;;
  *)          die "unknown command: $CMD (try --help)" ;;
esac
