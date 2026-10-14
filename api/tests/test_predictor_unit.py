"""Unit tests for the predictor core (no database)."""
import pytest

from app import predictor as P


def rows(*spec):
    """spec: (institute, course, round_code, seq, seat_category, closing_rank)."""
    return [P.CutoffRow(i, c, rc, s, cat, 1, close, close) for i, c, rc, s, cat, close in spec]


ROUNDS = [('R1', 1), ('R2', 2), ('R3', 3)]


def classify(spec, rank=30000, th=P.Thresholds()):
    opts = P.build_options(rows(*spec), ROUNDS)
    for o in opts:
        P.classify(o, rank, th)
    return {(o.institute_id, o.course_id): o for o in opts}


def test_best_close_takes_the_easier_eligible_category():
    o = classify([(1, 1, 'R1', 1, 'ST', 31000), (1, 1, 'R1', 1, 'OPEN', 900)])[(1, 1)]
    assert o.rounds[0].best_close == 31000 and o.rounds[0].best_category == 'ST'


@pytest.mark.parametrize('r1,later,expected', [
    (45000, None, 'safe'),          # 1.50×
    (44999, None, 'good'),          # just below 1.5×
    (34500, None, 'good'),          # 1.15×
    (28500, None, 'borderline'),    # 0.95×
    (28499, 28500, 'later_round'),  # R1 below 0.95×, R3 reaches 0.95×
    (20000, 22500, 'reach'),        # best of all rounds 0.75×
    (20000, 22499, 'unlikely'),
    (None, 30000, 'later_round'),   # no R1 allotment, later round qualifies
])
def test_status_thresholds(r1, later, expected):
    spec = []
    if r1 is not None:
        spec.append((1, 1, 'R1', 1, 'ST', r1))
    if later is not None:
        spec.append((1, 1, 'R3', 3, 'ST', later))
    assert classify(spec)[(1, 1)].status == expected


def test_custom_thresholds():
    th = P.Thresholds(safe=2.0, good=1.5, borderline=1.0, reach=0.5)
    assert classify([(1, 1, 'R1', 1, 'ST', 45000)], th=th)[(1, 1)].status == 'good'


def test_threshold_validation():
    with pytest.raises(ValueError):
        P.Thresholds(safe=1.0, good=1.2).validate()


def test_percentile_ranks_match_pandas_average_method():
    assert P.percentile_ranks({'a': 10, 'b': 20, 'c': 20, 'd': 30}) == {'a': 0.25, 'b': 0.625, 'c': 0.625, 'd': 1.0}


def test_desirability_formula():
    assert P.desirability(0.1, 0.5, 0.6) == round(100 * (1 - (0.06 + 0.2)), 1)
    assert P.desirability(None, None, 0.6) == 0.0          # unknown demand -> lowest desirability


def test_reason_mentions_rank_round_and_rule():
    o = classify([(1, 1, 'R1', 1, 'ST', 31354), (1, 1, 'R3', 3, 'ST', 45737)])[(1, 1)]
    text = P.explain(o, 30000, P.Thresholds(), {'R1': 'Round 1', 'R2': 'Round 2', 'R3': 'Round 3'})
    assert 'AIR 31,354' in text and '1.05×' in text and 'Round 3' in text and 'Borderline' in text
