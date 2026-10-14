"""Database queries and an in-process cache of small reference tables.

The cache is keyed by the id of the latest successful import, so it refreshes automatically after
`pipeline import` without restarting the API.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field

from . import db
from .predictor import CutoffRow


@dataclass
class Reference:
    version: int
    years: dict = field(default_factory=dict)          # year -> {label, rounds: [..], eligibility: {...}}
    institutes: dict = field(default_factory=dict)     # id -> row
    courses: dict = field(default_factory=dict)        # id -> row
    quotas: dict = field(default_factory=dict)         # code -> name
    seat_categories: dict = field(default_factory=dict)
    candidate_categories: dict = field(default_factory=dict)
    demand: dict = field(default_factory=dict)         # (year, quota) -> {'institute': {id: median}, 'branch': {..}}


_lock = threading.Lock()
_ref: Reference | None = None


def data_version() -> int:
    return db.fetch("SELECT coalesce(max(id), 0) AS v FROM import_run WHERE status = 'succeeded'")[0]['v']


def reference() -> Reference:
    global _ref
    v = data_version()
    if _ref is not None and _ref.version == v:
        return _ref
    with _lock:
        if _ref is None or _ref.version != v:
            _ref = _load_reference(v)
    return _ref


def _load_reference(version: int) -> Reference:
    ref = Reference(version=version)
    for y in db.fetch('SELECT year, label FROM counselling_year ORDER BY year'):
        ref.years[y['year']] = {'label': y['label'], 'rounds': [], 'eligibility': {}}
    for r in db.fetch('SELECT year, code, seq, name, kind FROM round ORDER BY year, seq'):
        ref.years[r['year']]['rounds'].append({k: r[k] for k in ('code', 'seq', 'name', 'kind')})
    for e in db.fetch('''SELECT e.year, e.candidate_category_code AS cand, e.seat_category_code AS seat,
                                e.source_clause, e.confirmed, e.notes, d.path, d.title
                         FROM category_eligibility e LEFT JOIN source_document d ON d.id = e.source_document_id
                         ORDER BY e.year, e.candidate_category_code, e.seat_category_code'''):
        el = ref.years[e['year']]['eligibility'].setdefault(e['cand'], {
            'seat_categories': [], 'confirmed': True, 'source': e['title'] or e['path'], 'source_path': e['path'],
            'clauses': []})
        el['seat_categories'].append(e['seat'])
        el['confirmed'] = el['confirmed'] and e['confirmed']
        if e['source_clause'] not in el['clauses']:
            el['clauses'].append(e['source_clause'])
    ref.institutes = {r['id']: r for r in db.fetch('SELECT id, name, short_name, state, mcc_code FROM institute')}
    ref.courses = {r['id']: r for r in db.fetch('SELECT id, code, name, branch, branch_group, degree FROM course')}
    ref.quotas = {r['code']: r['name'] for r in db.fetch('SELECT code, name FROM quota')}
    ref.seat_categories = {r['code']: r['name'] for r in db.fetch('SELECT code, name FROM seat_category')}
    ref.candidate_categories = {r['code']: r['name'] for r in db.fetch('SELECT code, name FROM candidate_category')}
    return ref


def demand(year: int, quota: str) -> dict:
    """Median AIR of first-round allotments in a quota (all categories), per institute and per branch."""
    ref = reference()
    key = (year, quota)
    if key not in ref.demand:
        inst = db.fetch('''SELECT a.institute_id AS k, percentile_cont(0.5) WITHIN GROUP (ORDER BY a.rank) AS m
                           FROM allotment a JOIN round r ON r.id = a.round_id
                           WHERE r.year = %s AND r.seq = 1 AND a.quota_code = %s GROUP BY a.institute_id''', (year, quota))
        branch = db.fetch('''SELECT c.branch AS k, percentile_cont(0.5) WITHIN GROUP (ORDER BY a.rank) AS m,
                                    count(*) AS seats, percentile_cont(0.25) WITHIN GROUP (ORDER BY a.rank) AS p25
                             FROM allotment a JOIN round r ON r.id = a.round_id JOIN course c ON c.id = a.course_id
                             WHERE r.year = %s AND r.seq = 1 AND a.quota_code = %s GROUP BY c.branch''', (year, quota))
        ref.demand[key] = {'institute': {r['k']: float(r['m']) for r in inst},
                           'branch': {r['k']: float(r['m']) for r in branch},
                           'branch_detail': {r['k']: {'seats': r['seats'], 'median_air': float(r['m']),
                                                      'p25_air': float(r['p25'])} for r in branch}}
    return ref.demand[key]


def cutoff_rows(year: int, quota: str, seat_categories: list[str], round_codes: list[str]) -> list[CutoffRow]:
    rows = db.fetch('''SELECT institute_id, course_id, round_code, round_seq, seat_category_code,
                              seats_allotted, opening_rank, closing_rank
                       FROM cutoff WHERE year = %s AND quota_code = %s
                         AND seat_category_code = ANY(%s) AND round_code = ANY(%s)''',
                    (year, quota, seat_categories, round_codes))
    return [CutoffRow(r['institute_id'], r['course_id'], r['round_code'], r['round_seq'], r['seat_category_code'],
                      r['seats_allotted'], r['opening_rank'], r['closing_rank']) for r in rows]
