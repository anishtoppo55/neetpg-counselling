"""API settings from environment variables (see docker-compose.yml)."""
import os

DATABASE_URL = os.environ.get('DATABASE_URL', '')
# Comma-separated origins allowed to call the API from a browser (the local Next.js dev server in Milestone 3).
# In a hosted deployment the dashboard calls the API from its server, so this can be left empty.
CORS_ORIGINS = [o.strip() for o in os.environ.get('CORS_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000').split(',') if o.strip()]
POOL_MAX = int(os.environ.get('DB_POOL_MAX', '5'))

# Shared secret. When set, every request except the health check must carry it as `X-API-Token`.
# Unset in both the development stack and the current deployment, where the API is only reachable on the
# Docker network and nothing outside the host can open a connection to it. Set it if you ever publish the
# API directly - for example by enabling the /api/* route in deploy/Caddyfile.
API_TOKEN = os.environ.get('API_TOKEN', '').strip()
# Serve /docs, /redoc and /openapi.json without the token. Keep false on a public deployment.
DOCS_PUBLIC = os.environ.get('DOCS_PUBLIC', 'true' if not API_TOKEN else 'false').lower() in ('1', 'true', 'yes')

# Quotas the predictor supports. Others (NRI, minority, AFMS, DU/IP/AMU/BHU internal) have extra eligibility
# conditions that are not modelled yet, so they are rejected with an explanation instead of guessed.
SUPPORTED_QUOTAS = {
    'AI': 'All India Quota – government and central institutes',
    'AD': 'DNB Quota – NBEMS-accredited hospitals',
    'PS': 'Self-Financed Merit / Management-Paid seats of deemed universities',
}

LIMITATIONS = [
    'Results are historical cut-offs from official MCC allotment PDFs, not predictions or admission probabilities.',
    'Most institute × course combinations have only one or two seats per category, so a single candidate sets the '
    'closing rank and it can move a lot from year to year.',
    'Round-2/3 closing ranks come from seats re-allotted in that round; they show what became possible, not a stable cut-off.',
    'Seat matrices, new colleges and rules change every year; check the current MCC information bulletin and seat matrix.',
    'Desirability is a demand proxy (how early toppers chose a branch/institute), not a measure of teaching quality, '
    'workload, bond or fees.',
    'Quota-specific eligibility (NRI, minority, AFMS, internal university quotas) is not modelled.',
    'This is a personal research aid; it is not an official MCC choice list.',
]
