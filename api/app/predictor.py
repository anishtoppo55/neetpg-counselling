"""Predictor core: classify historical college × course options for a candidate profile.

Pure functions over plain data (no database, no web framework) so the logic is easy to test and reason about.
The rules reproduce the analysis notebook `MCC_2025_ST_AIQ_all_rounds_analysis.ipynb`:

* An option is one institute × course in the chosen quota. For each considered round, its closing rank is the
  worst (highest) rank allotted on any seat category the candidate is eligible for (e.g. ST or Open for ST).
* The status compares the *first* considered round's closing rank with the candidate's rank (ratio = close / rank):
  Safe ≥ safe, Good chance ≥ good, Borderline ≥ borderline. If the first round does not qualify but a later round's
  closing rank ≥ borderline × rank, the option is a Later-round opportunity. Otherwise Reach when the best closing
  rank of any round ≥ reach × rank, else Unlikely.
* Desirability (0–100) = 100 × (1 − (w × branch percentile + (1 − w) × institute percentile)), where the
  percentiles rank the median AIR of first-round allotments in that quota (all categories) – a demand proxy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

STATUSES = ('safe', 'good', 'borderline', 'later_round', 'reach', 'unlikely')
STATUS_LABELS = {'safe': 'Safe', 'good': 'Good chance', 'borderline': 'Borderline',
                 'later_round': 'Later-round opportunity', 'reach': 'Reach', 'unlikely': 'Unlikely'}
ACHIEVABLE = ('safe', 'good', 'borderline', 'later_round')


@dataclass(frozen=True)
class Thresholds:
    safe: float = 1.5
    good: float = 1.15
    borderline: float = 0.95
    reach: float = 0.75

    def validate(self) -> None:
        if not (self.safe > self.good > self.borderline > self.reach > 0):
            raise ValueError('thresholds must satisfy safe > good > borderline > reach > 0')


@dataclass(frozen=True)
class CutoffRow:
    """One row of the `cutoff` view: closing rank of a seat category in a round."""
    institute_id: int
    course_id: int
    round_code: str
    round_seq: int
    seat_category: str
    seats: int
    opening_rank: int
    closing_rank: int


@dataclass
class RoundCutoff:
    round_code: str
    round_seq: int
    best_close: int | None = None          # max closing rank over eligible seat categories
    best_category: str | None = None       # seat category that gave best_close
    by_category: dict = field(default_factory=dict)   # seat category -> {seats, opening_rank, closing_rank}


@dataclass
class Option:
    institute_id: int
    course_id: int
    rounds: list[RoundCutoff]
    status: str = 'unlikely'
    ratio_first: float | None = None
    best_close_later: int | None = None
    best_close_any: int | None = None
    desirability: float = 0.0
    reason: str = ''


def build_options(rows: Iterable[CutoffRow], round_order: list[tuple[str, int]]) -> list[Option]:
    """Group cutoff rows into options with one RoundCutoff per considered round (in round order)."""
    by_key: dict[tuple[int, int], dict[str, RoundCutoff]] = {}
    for r in rows:
        rounds = by_key.setdefault((r.institute_id, r.course_id),
                                   {code: RoundCutoff(code, seq) for code, seq in round_order})
        rc = rounds.get(r.round_code)
        if rc is None:
            continue
        rc.by_category[r.seat_category] = {'seats': r.seats, 'opening_rank': r.opening_rank,
                                           'closing_rank': r.closing_rank}
        if rc.best_close is None or r.closing_rank > rc.best_close:
            rc.best_close, rc.best_category = r.closing_rank, r.seat_category
    return [Option(i, c, list(rs.values())) for (i, c), rs in by_key.items()]


def classify(opt: Option, rank: int, th: Thresholds) -> None:
    first, later = opt.rounds[0], opt.rounds[1:]
    closes = [rc.best_close for rc in opt.rounds if rc.best_close is not None]
    later_closes = [rc.best_close for rc in later if rc.best_close is not None]
    opt.best_close_any = max(closes) if closes else None
    opt.best_close_later = max(later_closes) if later_closes else None
    opt.ratio_first = first.best_close / rank if first.best_close is not None else None
    r = opt.ratio_first
    if r is not None and r >= th.safe:
        opt.status = 'safe'
    elif r is not None and r >= th.good:
        opt.status = 'good'
    elif r is not None and r >= th.borderline:
        opt.status = 'borderline'
    elif opt.best_close_later is not None and opt.best_close_later >= th.borderline * rank:
        opt.status = 'later_round'
    elif opt.best_close_any is not None and opt.best_close_any >= th.reach * rank:
        opt.status = 'reach'
    else:
        opt.status = 'unlikely'


def percentile_ranks(values: dict) -> dict:
    """pandas Series.rank(pct=True): average rank of ties / n (smallest value -> 1/n)."""
    items = sorted(values.items(), key=lambda kv: kv[1])
    n = len(items)
    out, i = {}, 0
    while i < n:
        j = i
        while j + 1 < n and items[j + 1][1] == items[i][1]:
            j += 1
        avg = (i + 1 + j + 1) / 2
        for k in range(i, j + 1):
            out[items[k][0]] = avg / n
        i = j + 1
    return out


def desirability(branch_pct: float | None, inst_pct: float | None, branch_weight: float) -> float:
    bp = 1.0 if branch_pct is None else branch_pct
    ip = 1.0 if inst_pct is None else inst_pct
    return round(100 * (1 - (branch_weight * bp + (1 - branch_weight) * ip)), 1)


def _fmt(n: int | None) -> str:
    return '–' if n is None else f'{n:,}'


CATEGORY_NAMES = {'OPEN': 'Open', 'OPEN_PWD': 'Open-PwD', 'OBC': 'OBC', 'OBC_PWD': 'OBC-PwD', 'SC': 'SC',
                  'SC_PWD': 'SC-PwD', 'ST': 'ST', 'ST_PWD': 'ST-PwD', 'EWS': 'EWS', 'EWS_PWD': 'EWS-PwD'}


def explain(opt: Option, rank: int, th: Thresholds, round_names: dict[str, str]) -> str:
    """Plain-language reason for the status, citing the rank and round it is based on."""
    first = opt.rounds[0]
    fname = round_names.get(first.round_code, first.round_code)
    if first.best_close is not None:
        head = (f'In {fname} the last eligible seat ({CATEGORY_NAMES.get(first.best_category, first.best_category)}) '
                f'went to AIR {_fmt(first.best_close)}, {opt.ratio_first:.2f}× your rank of {rank:,}')
    else:
        head = f'No eligible seat of this course was allotted here in {fname}'
    later = [(rc, round_names.get(rc.round_code, rc.round_code)) for rc in opt.rounds[1:] if rc.best_close is not None]
    tail = ''
    if later:
        best_rc, best_name = max(later, key=lambda t: t[0].best_close)
        tail = f'; latest closing in later rounds: AIR {_fmt(best_rc.best_close)} in {best_name}'
    rule = {
        'safe': f'≥ {th.safe}× → Safe',
        'good': f'between {th.good}× and {th.safe}× → Good chance',
        'borderline': f'between {th.borderline}× and {th.good}× → Borderline',
        'later_round': f'below {th.borderline}× in {fname}, but a later round reached ≥ {th.borderline}× → Later-round opportunity',
        'reach': f'best of all rounds between {th.reach}× and {th.borderline}× → Reach',
        'unlikely': f'best of all rounds below {th.reach}× → Unlikely',
    }[opt.status]
    return f'{head}{tail}. Rule: {rule}.'
