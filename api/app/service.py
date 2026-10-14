"""Predict endpoint logic: validate the profile against loaded data, run the predictor, shape the response."""
from __future__ import annotations

from fastapi import HTTPException

from . import config, predictor as P, repo
from .schemas import PredictRequest

DEFAULT_STATUSES = ('safe', 'good', 'borderline', 'later_round', 'reach')


def bad_request(message: str, field: str | None = None, allowed=None) -> HTTPException:
    detail = {'message': message}
    if field:
        detail['field'] = field
    if allowed is not None:
        detail['allowed'] = sorted(allowed) if not isinstance(allowed, dict) else allowed
    return HTTPException(status_code=422, detail=detail)


def resolve_year(ref: repo.Reference, year: int | None) -> int:
    if not ref.years:
        raise HTTPException(status_code=503, detail={'message': 'No counselling data loaded yet. Run the pipeline import.'})
    if year is None:
        return max(ref.years)
    if year not in ref.years:
        raise bad_request(f'No data loaded for year {year}.', 'year', list(ref.years))
    return year


def resolve_quota(ref: repo.Reference, quota: str) -> str:
    q = quota.upper()
    if q not in ref.quotas:
        raise bad_request(f'Unknown quota "{quota}".', 'quota', ref.quotas)
    if q not in config.SUPPORTED_QUOTAS:
        raise bad_request(f'Quota "{q}" ({ref.quotas[q]}) has extra eligibility conditions that the predictor does '
                          f'not model yet.', 'quota', config.SUPPORTED_QUOTAS)
    return q


def resolve_rounds(ref: repo.Reference, year: int, codes: list[str] | None) -> list[dict]:
    rounds = ref.years[year]['rounds']
    if not codes:
        chosen = [r for r in rounds if r['kind'] == 'regular']
    else:
        wanted = [c.upper() for c in codes]
        valid = {r['code'] for r in rounds}
        unknown = [c for c in wanted if c not in valid]
        if unknown:
            raise bad_request(f'Unknown round(s) for {year}: {", ".join(unknown)}.', 'rounds', valid)
        if len(set(wanted)) != len(wanted):
            raise bad_request('Rounds must not repeat.', 'rounds')
        chosen = [r for r in rounds if r['code'] in wanted]
    return sorted(chosen, key=lambda r: r['seq'])


def _check_values(given: list[str] | None, valid: set, field: str) -> set | None:
    if not given:
        return None
    unknown = [g for g in given if g not in valid]
    if unknown:
        raise bad_request(f'Unknown {field}: {", ".join(unknown)}.', field, valid)
    return set(given)


SORT_LABELS = {
    'desirability': 'Most in-demand first (desirability)',
    'chance': 'Best chance first (Safe → Reach)',
    'closing_rank_desc': 'Closing rank: most relaxed first',
    'closing_rank_asc': 'Closing rank: most competitive first',    # uses the best closing rank of any chosen round
    'branch_demand': 'Branch: most in-demand first',
    'college_demand': 'College: most in-demand first',
    'college': 'College name (A–Z)',
    'branch': 'Branch name (A–Z)',
}
BIG = float('inf')


def _sorter(sort: str, ref: repo.Reference, dem: dict):
    """Key function for the chosen order. Options with no closing rank or unknown demand sort last."""
    status_rank = {s: i for i, s in enumerate(P.STATUSES)}

    def close_first(o: P.Option) -> float:
        """Effective closing rank: the first chosen round when it allotted an eligible seat, else the best of any
        chosen round. Every option has at least one closing rank, so this is never None."""
        return o.rounds[0].best_close if o.rounds[0].best_close is not None else (o.best_close_any or 0)

    def close_any(o: P.Option) -> float:
        """Best (highest) closing rank across the chosen rounds – what 'stayed open longest' means."""
        return o.best_close_any if o.best_close_any is not None else close_first(o)

    def tiebreak(o: P.Option):
        return (ref.institutes[o.institute_id]['short_name'], ref.courses[o.course_id]['name'],
                o.institute_id, o.course_id)

    keys = {
        'desirability': lambda o: (-o.desirability, -close_first(o)),
        'chance': lambda o: (status_rank[o.status], -o.desirability, -close_first(o)),
        'closing_rank_desc': lambda o: (-close_any(o),),
        'closing_rank_asc': lambda o: (close_any(o),),
        'branch_demand': lambda o: (dem['branch'].get(ref.courses[o.course_id]['branch'], BIG), -o.desirability),
        'college_demand': lambda o: (dem['institute'].get(o.institute_id, BIG), -o.desirability),
        'college': lambda o: (ref.institutes[o.institute_id]['short_name'].upper(),),
        'branch': lambda o: (ref.courses[o.course_id]['branch'], ref.courses[o.course_id]['name']),
    }
    key = keys[sort]
    return lambda o: (*key(o), *tiebreak(o))


def predict(req: PredictRequest) -> dict:
    ref = repo.reference()
    year = resolve_year(ref, req.year)
    quota = resolve_quota(ref, req.quota)
    rounds = resolve_rounds(ref, year, req.rounds)
    elig = ref.years[year]['eligibility'].get(req.category)
    if not elig:
        raise bad_request(f'No category-eligibility rules loaded for {req.category} in {year}.', 'category')
    branches = _check_values(req.branches, {c['branch'] for c in ref.courses.values()}, 'branches')
    states = _check_values(req.states, {i['state'] for i in ref.institutes.values() if i['state']}, 'states')
    groups = set(req.groups) if req.groups else None
    degrees = set(req.degrees) if req.degrees else None
    statuses = set(req.statuses) if req.statuses else set(DEFAULT_STATUSES)
    th = P.Thresholds(**req.thresholds.model_dump())

    rows = repo.cutoff_rows(year, quota, elig['seat_categories'], [r['code'] for r in rounds])
    options = P.build_options(rows, [(r['code'], r['seq']) for r in rounds])

    def keep(o: P.Option) -> bool:
        c, i = ref.courses[o.course_id], ref.institutes[o.institute_id]
        return ((branches is None or c['branch'] in branches) and (states is None or i['state'] in states)
                and (groups is None or c['branch_group'] in groups) and (degrees is None or c['degree'] in degrees))

    options = [o for o in options if keep(o)]
    dem = repo.demand(year, quota)
    inst_pct, branch_pct = P.percentile_ranks(dem['institute']), P.percentile_ranks(dem['branch'])
    round_names = {r['code']: r['name'] for r in rounds}
    by_status = {s: 0 for s in P.STATUSES}
    by_branch: dict[str, dict] = {}
    for o in options:
        P.classify(o, req.rank, th)
        br = ref.courses[o.course_id]['branch']
        o.desirability = P.desirability(branch_pct.get(br), inst_pct.get(o.institute_id), req.branch_weight)
        by_status[o.status] += 1
        by_branch.setdefault(br, {s: 0 for s in P.STATUSES})[o.status] += 1

    selected = [o for o in options if o.status in statuses]
    sort_key = req.sort if req.sort != 'closing_rank' else 'closing_rank_desc'   # legacy alias
    selected.sort(key=_sorter(sort_key, ref, dem))
    page = selected[req.offset:req.offset + req.limit]

    out = []
    for o in page:
        o.reason = P.explain(o, req.rank, th, round_names)
        i, c = ref.institutes[o.institute_id], ref.courses[o.course_id]
        out.append({
            'institute': {k: i[k] for k in ('id', 'name', 'short_name', 'state', 'mcc_code')},
            'course': {'id': c['id'], 'code': c['code'], 'name': c['name'], 'branch': c['branch'],
                       'group': c['branch_group'], 'degree': c['degree']},
            'status': o.status, 'status_label': P.STATUS_LABELS[o.status], 'desirability': o.desirability,
            'ratio_first_round': None if o.ratio_first is None else round(o.ratio_first, 3),
            'best_close_later_rounds': o.best_close_later,
            'rounds': [{'round': rc.round_code, 'round_name': round_names[rc.round_code], 'best_close': rc.best_close,
                        'best_category': rc.best_category, 'by_category': rc.by_category} for rc in o.rounds],
            'institute_median_air': dem['institute'].get(o.institute_id),
            'branch_median_air': dem['branch'].get(c['branch']),
            'reason': o.reason,
        })

    notices = ['Historical estimate from official MCC allotment results – not a guarantee of admission.']
    if not elig['confirmed']:
        notices.append(f'The category-eligibility rules for {year} ({req.category} → '
                       f'{", ".join(elig["seat_categories"])}) are drafted from {elig["source"]} and have not been '
                       f'confirmed yet.')
    if any(r['kind'] == 'stray' for r in rounds):
        notices.append('Stray rounds fill leftover seats; their closing ranks are usually far higher than regular rounds.')
    return {
        'year': year, 'quota': quota, 'quota_name': ref.quotas[quota], 'category': req.category, 'rank': req.rank,
        'rounds': [{'code': r['code'], 'name': r['name'], 'kind': r['kind']} for r in rounds],
        'eligibility': {k: elig[k] for k in ('seat_categories', 'confirmed', 'source', 'clauses')},
        'thresholds': req.thresholds, 'sort': sort_key,
        'summary': {'by_status': by_status, 'by_branch': dict(sorted(by_branch.items()))},
        'total': len(selected), 'options': out, 'notices': notices,
    }
