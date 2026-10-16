"""FastAPI application: predictor and read-only data endpoints.

No authentication: Phase 1 runs locally and the port is bound to 127.0.0.1 (see docker-compose.yml).
"""
from __future__ import annotations

import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Path, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import config, db, predictor as P, repo, service
from .schemas import PredictRequest, PredictResponse


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.open_pool()
    yield
    db.close_pool()


app = FastAPI(title='NEET PG Counselling Predictor API', version='0.1.0', lifespan=lifespan,
              description='Historical MCC allotment cut-offs and a rule-based college × course predictor. '
                          'Estimates only – not admission guarantees.')
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=['GET', 'POST'],
                   allow_headers=['Content-Type', 'X-API-Token'])

OPEN_PATHS = {'/', '/api/live', '/api/health'}    # platform probes: port detection, health check, diagnostics
DOCS_PATHS = {'/docs', '/redoc', '/openapi.json', '/docs/oauth2-redirect'}


@app.middleware('http')
async def require_api_token(request: Request, call_next):
    """When API_TOKEN is set, require it as the X-API-Token header. No token configured = open (local dev)."""
    path = request.url.path.rstrip('/') or '/'
    if config.API_TOKEN and path not in OPEN_PATHS and not (config.DOCS_PUBLIC and path in DOCS_PATHS):
        sent = request.headers.get('x-api-token', '')
        if not secrets.compare_digest(sent, config.API_TOKEN):
            return JSONResponse(status_code=401, content={'detail': {
                'message': 'This API requires a shared secret. Send it as the X-API-Token header.',
                'field': 'X-API-Token'}})
    return await call_next(request)


@app.api_route('/', methods=['GET', 'HEAD'])
def root():
    """Answers an unauthenticated port probe. Probes often use HEAD, which a GET-only route would reject
    with 405, so both methods are registered."""
    return {'service': 'neetpg-api', 'docs': '/docs', 'health': '/api/health', 'live': '/api/live'}


@app.api_route('/api/live', methods=['GET', 'HEAD'])
def live():
    """Liveness only – never touches the database.

    This is the container health-check path. A database problem must not stop the container being
    considered up, because the data is loaded *after* the stack starts - pointing a health check at
    /api/health instead deadlocks the first deploy. Readiness, including the database, is /api/health.
    """
    return {'status': 'ok'}


@app.get('/api/health')
def health():
    """Readiness: process up *and* database reachable, plus the current data version."""
    try:
        return {'status': 'ok', 'data_version': repo.data_version()}
    except Exception as exc:                         # database unreachable / not migrated yet
        return JSONResponse(status_code=503, content={'status': 'degraded', 'detail': str(exc)[:200]})


@app.post('/api/predict', response_model=PredictResponse)
def predict(req: PredictRequest):
    """Classify historical options for a candidate profile (status, desirability and reason per option)."""
    return service.predict(req)


@app.get('/api/meta')
def meta():
    ref = repo.reference()
    docs = db.fetch('SELECT year, path, kind, title, url, sha256 FROM source_document ORDER BY year, kind, path')
    return {
        'supported_quotas': config.SUPPORTED_QUOTAS,
        'all_quotas': ref.quotas,
        'candidate_categories': ref.candidate_categories,
        'seat_categories': ref.seat_categories,
        'statuses': P.STATUS_LABELS,
        'sorts': service.SORT_LABELS,
        'default_sort': 'desirability',
        'default_statuses': list(service.DEFAULT_STATUSES),
        'default_thresholds': P.Thresholds().__dict__,
        'groups': sorted({c['branch_group'] for c in ref.courses.values()}),
        'degrees': sorted({c['degree'] for c in ref.courses.values()}),
        'limitations': config.LIMITATIONS,
        'sources': docs,
        'data_version': ref.version,
    }


@app.get('/api/years')
def years():
    ref = repo.reference()
    return [{'year': y, 'label': v['label'], 'rounds': v['rounds'], 'eligibility': v['eligibility']}
            for y, v in sorted(ref.years.items(), reverse=True)]


@app.get('/api/branches')
def branches(year: int | None = None, quota: str = 'AI'):
    """Branches with their group, degrees offered and national demand (first-round median AIR in the quota)."""
    ref = repo.reference()
    y = service.resolve_year(ref, year)
    q = service.resolve_quota(ref, quota)
    detail = repo.demand(y, q)['branch_detail']
    out: dict[str, dict] = {}
    for c in ref.courses.values():
        b = out.setdefault(c['branch'], {'branch': c['branch'], 'group': c['branch_group'], 'degrees': set(),
                                         'course_codes': []})
        b['degrees'].add(c['degree']); b['course_codes'].append(c['code'])
    for b in out.values():
        b['degrees'] = sorted(b['degrees']); b['course_codes'].sort()
        b['demand'] = detail.get(b['branch'])
    return sorted(out.values(), key=lambda b: (b['demand'] or {}).get('median_air', 1e12))


@app.get('/api/states')
def states(year: int | None = None):
    ref = repo.reference()
    y = service.resolve_year(ref, year)
    rows = db.fetch('''SELECT i.state, count(DISTINCT i.id) AS institutes
                       FROM allotment a JOIN round r ON r.id = a.round_id JOIN institute i ON i.id = a.institute_id
                       WHERE r.year = %s GROUP BY i.state ORDER BY i.state NULLS LAST''', (y,))
    return [{'state': r['state'], 'institutes': r['institutes']} for r in rows]


@app.get('/api/colleges')
def colleges(year: int | None = None, quota: str | None = None, state: str | None = None,
             q: str | None = Query(None, min_length=2, max_length=100, description='Name contains (case-insensitive)'),
             branch: str | None = None, limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    ref = repo.reference()
    y = service.resolve_year(ref, year)
    quota_code = service.resolve_quota(ref, quota) if quota else None
    where, params = ['r.year = %s'], [y]
    if quota_code:
        where.append('a.quota_code = %s'); params.append(quota_code)
    if state:
        where.append('i.state = %s'); params.append(state)
    if q:
        where.append('(i.name ILIKE %s OR i.short_name ILIKE %s)'); params += [f'%{q}%', f'%{q}%']
    if branch:
        where.append('c.branch = %s'); params.append(branch)
    sql = f'''SELECT i.id, i.name, i.short_name, i.state, i.mcc_code,
                     count(*) AS allotments, count(DISTINCT a.course_id) AS courses,
                     array_agg(DISTINCT a.quota_code ORDER BY a.quota_code) AS quotas,
                     count(*) OVER () AS total
              FROM allotment a JOIN round r ON r.id = a.round_id JOIN institute i ON i.id = a.institute_id
              JOIN course c ON c.id = a.course_id
              WHERE {' AND '.join(where)}
              GROUP BY i.id ORDER BY i.short_name, i.id LIMIT %s OFFSET %s'''
    rows = db.fetch(sql, params + [limit, offset])
    return {'year': y, 'total': rows[0]['total'] if rows else 0,
            'items': [{k: r[k] for k in r if k != 'total'} for r in rows]}


@app.get('/api/colleges/{college_id}')
def college(college_id: int = Path(..., ge=1), year: int | None = None):
    """One institute: every course with round-wise opening/closing ranks per quota and seat category, plus
    Round-1 seat-matrix seats where the seat matrix was linked to this institute."""
    ref = repo.reference()
    inst = ref.institutes.get(college_id)
    if inst is None:
        raise HTTPException(status_code=404, detail={'message': f'College {college_id} not found.'})
    years_ = [service.resolve_year(ref, year)] if year else sorted(ref.years)
    cut = db.fetch('''SELECT year, round_code, round_seq, quota_code, course_id, seat_category_code,
                             seats_allotted, opening_rank, closing_rank
                      FROM cutoff WHERE institute_id = %s AND year = ANY(%s)
                      ORDER BY year DESC, course_id, quota_code, round_seq, seat_category_code''', (college_id, years_))
    seats = db.fetch('''SELECT r.year, s.course_id, s.quota_code, s.seat_category_code, sum(s.seats) AS seats
                        FROM seat_matrix s JOIN round r ON r.id = s.round_id
                        WHERE s.institute_id = %s AND r.year = ANY(%s)
                        GROUP BY 1, 2, 3, 4''', (college_id, years_))
    courses: dict[tuple, dict] = {}
    for r in cut:
        c = ref.courses[r['course_id']]
        k = (r['year'], r['course_id'])
        e = courses.setdefault(k, {'year': r['year'], 'course': {'id': c['id'], 'code': c['code'], 'name': c['name'],
                                   'branch': c['branch'], 'group': c['branch_group'], 'degree': c['degree']},
                                   'cutoffs': [], 'seat_matrix_round1': []})
        e['cutoffs'].append({'round': r['round_code'], 'quota': r['quota_code'], 'seat_category': r['seat_category_code'],
                             'seats_allotted': r['seats_allotted'], 'opening_rank': r['opening_rank'],
                             'closing_rank': r['closing_rank']})
    for s in seats:
        c = ref.courses[s['course_id']]
        e = courses.setdefault((s['year'], s['course_id']), {
            'year': s['year'], 'course': {'id': c['id'], 'code': c['code'], 'name': c['name'], 'branch': c['branch'],
                                          'group': c['branch_group'], 'degree': c['degree']},
            'cutoffs': [], 'seat_matrix_round1': []})
        e['seat_matrix_round1'].append({'quota': s['quota_code'], 'seat_category': s['seat_category_code'],
                                        'seats': int(s['seats'])})
    return {'institute': inst, 'years': years_,
            'courses': sorted(courses.values(), key=lambda e: (-e['year'], e['course']['branch'], e['course']['name']))}


@app.get('/api/cutoffs')
def cutoffs(year: int | None = None, quota: str = 'AI', round: str | None = None, seat_category: str | None = None,
            branch: str | None = None, state: str | None = None, college_id: int | None = None,
            course_code: str | None = None, max_closing_rank: int | None = Query(None, ge=1),
            min_closing_rank: int | None = Query(None, ge=1),
            limit: int = Query(200, ge=1, le=5000), offset: int = Query(0, ge=0)):
    """Raw round-wise cut-offs (one row per round × quota × institute × course × seat category)."""
    ref = repo.reference()
    y = service.resolve_year(ref, year)
    if quota.upper() not in ref.quotas:
        raise service.bad_request(f'Unknown quota "{quota}".', 'quota', ref.quotas)
    where, params = ['c.year = %s', 'c.quota_code = %s'], [y, quota.upper()]
    for col, val in (('c.round_code', round and round.upper()), ('c.seat_category_code', seat_category and seat_category.upper()),
                     ('co.branch', branch), ('i.state', state), ('c.institute_id', college_id),
                     ('co.code', course_code and course_code.upper())):
        if val is not None:
            where.append(f'{col} = %s'); params.append(val)
    if max_closing_rank:
        where.append('c.closing_rank <= %s'); params.append(max_closing_rank)
    if min_closing_rank:
        where.append('c.closing_rank >= %s'); params.append(min_closing_rank)
    rows = db.fetch(f'''SELECT c.year, c.round_code, c.quota_code, c.seat_category_code, c.seats_allotted,
                               c.opening_rank, c.closing_rank, i.id AS college_id, i.short_name AS college,
                               i.state, co.code AS course_code, co.name AS course, co.branch, co.degree,
                               count(*) OVER () AS total
                        FROM cutoff c JOIN institute i ON i.id = c.institute_id JOIN course co ON co.id = c.course_id
                        WHERE {' AND '.join(where)}
                        ORDER BY c.round_seq, c.closing_rank, i.short_name LIMIT %s OFFSET %s''',
                     params + [limit, offset])
    return {'year': y, 'total': rows[0]['total'] if rows else 0,
            'items': [{k: r[k] for k in r if k != 'total'} for r in rows]}
