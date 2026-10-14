"""API tests against the loaded database (run inside the api container: docker compose exec api pytest -q)."""
import os
import statistics
import time

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(not os.environ.get('DATABASE_URL'), reason='DATABASE_URL not set')

GOLDEN = {'rank': 30000, 'category': 'ST', 'quota': 'AI', 'year': 2025, 'groups': ['Clinical'], 'degrees': ['MD/MS'],
          'statuses': ['safe', 'good', 'borderline', 'later_round'], 'limit': 5000}


@pytest.fixture(scope='module')
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get('/api/health')
    assert r.status_code == 200 and r.json()['status'] == 'ok'


def test_golden_matches_notebook(client):
    """Notebook (2025, ST, AIR 30,000, AIQ, clinical MD/MS): 520 options = 170 Safe, 114 Good, 67 Borderline,
    169 Later rounds. The notebook dropped 19 institutes whose address has no state (pandas pivot on a NaN key),
    so the comparison is on institutes with a state; the API additionally returns the stateless ones."""
    r = client.post('/api/predict', json=GOLDEN)
    assert r.status_code == 200, r.text
    d = r.json()
    with_state = [o for o in d['options'] if o['institute']['state'] is not None]
    counts = {s: sum(o['status'] == s for o in with_state) for s in GOLDEN['statuses']}
    assert len(with_state) == 520
    assert counts == {'safe': 170, 'good': 114, 'borderline': 67, 'later_round': 169}
    assert d['total'] == len(d['options']) >= 520
    assert d['eligibility']['seat_categories'] == ['OPEN', 'ST']


def test_golden_top_options_match_notebook(client):
    """First rows of the notebook's recommendation table (sorted by desirability)."""
    d = client.post('/api/predict', json=GOLDEN).json()
    top = [(o['institute']['short_name'], o['course']['branch'], o['status']) for o in d['options'][:3]]
    assert top[0] == ('STANLEY MEDICAL COLLEGE', 'General Medicine', 'later_round')
    assert d['options'][0]['desirability'] == 91.5
    assert d['options'][0]['rounds'][0]['best_close'] == 19508


def test_option_shape_and_reason(client):
    d = client.post('/api/predict', json=GOLDEN | {'limit': 1}).json()
    o = d['options'][0]
    assert set(o) >= {'institute', 'course', 'status', 'status_label', 'desirability', 'rounds', 'reason'}
    assert [r['round'] for r in o['rounds']] == ['R1', 'R2', 'R3']
    assert 'Rule:' in o['reason'] and 'AIR' in o['reason']
    assert any('not been confirmed' in n for n in d['notices'])


def test_filters_and_pagination(client):
    base = GOLDEN | {'branches': ['Paediatrics'], 'states': ['Tamil Nadu']}
    d = client.post('/api/predict', json=base).json()
    assert d['options'] and all(o['course']['branch'] == 'Paediatrics' and o['institute']['state'] == 'Tamil Nadu'
                                for o in d['options'])
    p1 = client.post('/api/predict', json=base | {'limit': 2, 'offset': 0}).json()['options']
    p2 = client.post('/api/predict', json=base | {'limit': 2, 'offset': 2}).json()['options']
    assert [o['institute']['id'] for o in p1 + p2] == [o['institute']['id'] for o in d['options'][:4]]


def test_pwd_category_uses_pwd_seats(client):
    d = client.post('/api/predict', json={'rank': 100000, 'category': 'ST_PWD', 'year': 2025}).json()
    assert set(d['eligibility']['seat_categories']) == {'ST', 'ST_PWD', 'OPEN', 'OPEN_PWD'}


def _eff_close(option):
    """Best closing rank across the returned rounds – what the closing-rank sorts order by."""
    return max(r['best_close'] for r in option['rounds'] if r['best_close'] is not None)


@pytest.mark.parametrize('sort,key,reverse', [
    ('desirability', lambda o: o['desirability'], True),
    ('closing_rank_desc', _eff_close, True),
    ('closing_rank_asc', _eff_close, False),
    ('branch_demand', lambda o: o['branch_median_air'], False),
    ('college_demand', lambda o: o['institute_median_air'], False),
    ('college', lambda o: o['institute']['short_name'].upper(), False),
    ('branch', lambda o: o['course']['branch'], False),
])
def test_sort_orders(client, sort, key, reverse):
    d = client.post('/api/predict', json=GOLDEN | {'sort': sort, 'limit': 80}).json()
    values = [key(o) for o in d['options']]
    assert d['sort'] == sort
    assert values == sorted(values, reverse=reverse), f'{sort} not ordered: {values[:5]}'


def test_sort_by_chance_follows_status_order(client):
    order = ['safe', 'good', 'borderline', 'later_round', 'reach', 'unlikely']
    d = client.post('/api/predict', json=GOLDEN | {'sort': 'chance', 'limit': 200,
                                                   'statuses': order}).json()
    ranks = [order.index(o['status']) for o in d['options']]
    assert ranks == sorted(ranks)


def test_legacy_sort_alias_still_works(client):
    d = client.post('/api/predict', json=GOLDEN | {'sort': 'closing_rank'}).json()
    assert d['sort'] == 'closing_rank_desc'


def test_sort_options_listed_in_meta(client):
    meta = client.get('/api/meta').json()
    assert meta['default_sort'] == 'desirability'
    assert set(meta['sorts']) == {'desirability', 'chance', 'closing_rank_desc', 'closing_rank_asc',
                                  'branch_demand', 'college_demand', 'college', 'branch'}
    assert all(isinstance(v, str) and v for v in meta['sorts'].values())


def test_unknown_sort_is_rejected(client):
    assert client.post('/api/predict', json=GOLDEN | {'sort': 'price'}).status_code == 422


def test_sort_does_not_change_the_result_set(client):
    base = client.post('/api/predict', json=GOLDEN).json()
    other = client.post('/api/predict', json=GOLDEN | {'sort': 'college'}).json()
    keys = lambda d: {(o['institute']['id'], o['course']['id']) for o in d['options']}
    assert base['total'] == other['total'] and keys(base) == keys(other)


def test_2024_and_custom_thresholds(client):
    d = client.post('/api/predict', json={'rank': 30000, 'category': 'ST', 'year': 2024,
                                          'thresholds': {'safe': 2, 'good': 1.5, 'borderline': 1.0, 'reach': 0.5}}).json()
    assert d['year'] == 2024 and d['thresholds']['safe'] == 2
    assert [r['code'] for r in d['rounds']] == ['R1', 'R2', 'R3']


def test_stray_round_can_be_included(client):
    d = client.post('/api/predict', json={'rank': 30000, 'category': 'ST', 'year': 2025,
                                          'rounds': ['R1', 'R2', 'R3', 'STRAY']}).json()
    assert d['rounds'][-1]['code'] == 'STRAY' and any('Stray' in n for n in d['notices'])


@pytest.mark.parametrize('payload,field', [
    ({'rank': 30000, 'category': 'ST', 'quota': 'NR'}, 'quota'),                 # unsupported quota
    ({'rank': 30000, 'category': 'ST', 'quota': 'XX'}, 'quota'),                 # unknown quota
    ({'rank': 30000, 'category': 'ST', 'year': 2019}, 'year'),                   # year not loaded
    ({'rank': 30000, 'category': 'ST', 'rounds': ['R9']}, 'rounds'),
    ({'rank': 30000, 'category': 'ST', 'branches': ['Astrology']}, 'branches'),
    ({'rank': 30000, 'category': 'ST', 'states': ['Atlantis']}, 'states'),
])
def test_clear_errors_for_unsupported_inputs(client, payload, field):
    r = client.post('/api/predict', json=payload)
    assert r.status_code == 422
    detail = r.json()['detail']
    assert detail['field'] == field and detail['message']


@pytest.mark.parametrize('payload', [
    {'rank': 0, 'category': 'ST'},
    {'rank': 30000, 'category': 'XYZ'},
    {'rank': 30000, 'category': 'ST', 'thresholds': {'safe': 1.0, 'good': 1.2, 'borderline': 0.9, 'reach': 0.5}},
    {'rank': 30000, 'category': 'ST', 'unexpected': 1},
])
def test_schema_validation_errors(client, payload):
    assert client.post('/api/predict', json=payload).status_code == 422


def test_no_token_configured_means_open(client):
    """Local development: API_TOKEN unset, so no header is needed."""
    from app import config
    assert config.API_TOKEN == ''
    assert client.post('/api/predict', json={'rank': 30000, 'category': 'ST'}).status_code == 200


def test_token_is_required_when_configured(client, monkeypatch):
    """Hosted deployment: every path except the health check needs the shared secret."""
    from app import config
    monkeypatch.setattr(config, 'API_TOKEN', 's3cret-token')
    monkeypatch.setattr(config, 'DOCS_PUBLIC', False)

    denied = client.post('/api/predict', json={'rank': 30000, 'category': 'ST'})
    assert denied.status_code == 401
    assert denied.json()['detail']['field'] == 'X-API-Token'
    assert client.get('/api/meta').status_code == 401
    assert client.get('/openapi.json').status_code == 401

    # health stays open so the platform health check keeps working
    assert client.get('/api/health').status_code == 200

    headers = {'X-API-Token': 's3cret-token'}
    assert client.post('/api/predict', json={'rank': 30000, 'category': 'ST'}, headers=headers).status_code == 200
    assert client.get('/api/meta', headers=headers).status_code == 200
    # a wrong token is rejected
    assert client.get('/api/meta', headers={'X-API-Token': 'nope'}).status_code == 401


def test_docs_can_be_left_public(client, monkeypatch):
    from app import config
    monkeypatch.setattr(config, 'API_TOKEN', 's3cret-token')
    monkeypatch.setattr(config, 'DOCS_PUBLIC', True)
    assert client.get('/openapi.json').status_code == 200
    assert client.get('/api/meta').status_code == 401


def test_lookup_endpoints(client):
    years = client.get('/api/years').json()
    assert [y['year'] for y in years][:2] == [2025, 2024]
    meta = client.get('/api/meta').json()
    assert set(meta['supported_quotas']) == {'AI', 'AD', 'PS'} and meta['limitations'] and meta['sources']
    branches = client.get('/api/branches', params={'year': 2025}).json()
    assert branches[0]['branch'] == 'Nuclear Medicine' or branches[0]['demand']['median_air'] < 2000
    states = client.get('/api/states', params={'year': 2025}).json()
    assert any(s['state'] == 'Kerala' for s in states)


def test_colleges_and_detail(client):
    lst = client.get('/api/colleges', params={'year': 2025, 'q': 'Stanley', 'quota': 'AI'}).json()
    assert lst['total'] >= 1
    cid = lst['items'][0]['id']
    det = client.get(f'/api/colleges/{cid}', params={'year': 2025}).json()
    assert det['institute']['id'] == cid and det['courses']
    gm = [c for c in det['courses'] if c['course']['code'] == 'GMED'][0]
    assert any(x['round'] == 'R1' and x['quota'] == 'AI' for x in gm['cutoffs'])
    assert client.get('/api/colleges/999999').status_code == 404


def test_cutoffs_endpoint(client):
    d = client.get('/api/cutoffs', params={'year': 2025, 'quota': 'AI', 'round': 'R1', 'seat_category': 'ST',
                                           'branch': 'General Medicine', 'limit': 5}).json()
    assert d['total'] > 0 and all(x['seat_category_code'] == 'ST' and x['round_code'] == 'R1' for x in d['items'])
    closes = [x['closing_rank'] for x in d['items']]
    assert closes == sorted(closes)


def test_predict_p95_under_one_second(client):
    client.post('/api/predict', json=GOLDEN)        # warm the reference cache
    times = []
    for i in range(20):
        t = time.perf_counter()
        r = client.post('/api/predict', json={'rank': 5000 + i * 3000, 'category': 'OBC', 'year': 2025})
        times.append(time.perf_counter() - t)
        assert r.status_code == 200
    p95 = statistics.quantiles(times, n=20)[18]
    assert p95 < 1.0, f'p95 {p95:.3f}s'
