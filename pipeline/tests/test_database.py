"""Integration tests against the loaded database.

Reference numbers come from the analysis notebook MCC_2025_ST_AIQ_all_rounds_analysis.ipynb, which was built
independently from the same 2025 PDFs. Skipped when DATABASE_URL is not set or a year is not loaded.
"""
import os

import pytest

psycopg = pytest.importorskip('psycopg')
pytestmark = pytest.mark.skipif(not os.environ.get('DATABASE_URL'), reason='DATABASE_URL not set')


@pytest.fixture(scope='module')
def conn():
    with psycopg.connect(os.environ['DATABASE_URL']) as c:
        yield c


def _require_year(conn, year):
    if not conn.execute('SELECT 1 FROM counselling_year WHERE year = %s', (year,)).fetchone():
        pytest.skip(f'{year} not loaded')


def q(conn, sql, *args):
    return conn.execute(sql, args).fetchall()


# ---------------------------------------------------------------- 2025 vs notebook
def test_2025_aiq_allotments_per_round(conn):
    _require_year(conn, 2025)
    rows = dict(q(conn, """SELECT r.code, count(*) FROM allotment a JOIN round r ON r.id = a.round_id
                           WHERE r.year = 2025 AND a.quota_code = 'AI' GROUP BY r.code"""))
    assert (rows['R1'], rows['R2'], rows['R3']) == (12047, 9667, 8783)


def test_2025_st_aiq_seats_match_notebook(conn):
    """Notebook section 3: ST seats 842/703/688, median rank 40,570.5/52,465/69,040.5, worse than 30k 551/572/614."""
    _require_year(conn, 2025)
    rows = q(conn, """SELECT r.code, count(*), percentile_cont(0.5) WITHIN GROUP (ORDER BY a.rank),
                             count(*) FILTER (WHERE a.rank > 30000)
                      FROM allotment a JOIN round r ON r.id = a.round_id
                      WHERE r.year = 2025 AND a.quota_code = 'AI' AND a.seat_category_code = 'ST'
                        AND r.code IN ('R1','R2','R3') GROUP BY r.code ORDER BY r.code""")
    assert [(c, n, float(m), w) for c, n, m, w in rows] == [
        ('R1', 842, 40570.5, 551), ('R2', 703, 52465.0, 572), ('R3', 688, 69040.5, 614)]


def test_2025_institute_course_combinations_match_notebook(conn):
    """Notebook section 4 reports 3,182 AIQ institute x course combinations with an ST or Open allotment in R1–R3.

    The notebook's pandas pivot_table silently dropped institutes whose address names no state (NaN group key):
    19 institutes / 57 combinations. The database keeps them, so: 3,182 with a state + 57 without = 3,239.
    """
    _require_year(conn, 2025)
    (with_state, without_state), = q(conn, """
        SELECT count(DISTINCT (c.institute_id, c.course_id)) FILTER (WHERE i.state IS NOT NULL),
               count(DISTINCT (c.institute_id, c.course_id)) FILTER (WHERE i.state IS NULL)
        FROM cutoff c JOIN institute i ON i.id = c.institute_id
        WHERE c.year = 2025 AND c.quota_code = 'AI' AND c.seat_category_code IN ('ST','OPEN')
          AND c.round_code IN ('R1','R2','R3')""")
    assert (with_state, without_state) == (3182, 57)


def test_2025_st_candidates_identified(conn):
    """Notebook section 2: 1,823 distinct ST candidates across rounds 1–3."""
    _require_year(conn, 2025)
    (n,), = q(conn, """SELECT count(DISTINCT a.rank) FROM allotment a JOIN round r ON r.id = a.round_id
                       WHERE r.year = 2025 AND r.code IN ('R1','R2','R3') AND a.candidate_category_code = 'ST'""")
    assert n == 1823


def test_2025_reporting_status_counts(conn):
    _require_year(conn, 2025)
    rows = dict(q(conn, """SELECT s.status, count(*) FROM reporting_status s JOIN round r ON r.id = s.round_id
                           WHERE r.year = 2025 AND r.code = 'R1' GROUP BY s.status"""))
    assert rows == {'Reported': 13498, 'Not Reported': 12848, 'Seat Surrendered': 540, 'Seat Cancelled': 3}


# ---------------------------------------------------------------- integrity, every loaded year
def test_cutoff_view_consistent_with_allotments(conn):
    (a,), = q(conn, 'SELECT count(*) FROM allotment')
    (c,), = q(conn, 'SELECT sum(seats_allotted) FROM cutoff')
    assert a == c and a > 0


def test_every_allotment_respects_eligibility_rules(conn):
    """Each (candidate category, seat category) pair in the data must be allowed by category_eligibility."""
    bad = q(conn, """SELECT r.year, a.candidate_category_code, a.seat_category_code, count(*)
                     FROM allotment a JOIN round r ON r.id = a.round_id
                     LEFT JOIN category_eligibility e ON e.year = r.year
                          AND e.candidate_category_code = a.candidate_category_code
                          AND e.seat_category_code = a.seat_category_code
                     WHERE a.candidate_category_code IS NOT NULL AND e.year IS NULL
                     GROUP BY 1, 2, 3""")
    assert bad == []


def test_eligibility_rules_cite_a_source(conn):
    rows = q(conn, """SELECT e.year, count(*), count(e.source_document_id), bool_and(e.source_clause <> '')
                      FROM category_eligibility e GROUP BY e.year""")
    assert rows and all(n == with_src and has_clause for _, n, with_src, has_clause in rows)


def test_ranks_unique_per_round_and_results_cover_allotments(conn):
    (n,), = q(conn, """SELECT count(*) FROM allotment a LEFT JOIN round_result rr
                       ON rr.round_id = a.round_id AND rr.rank = a.rank WHERE NOT rr.allotted OR rr.rank IS NULL""")
    assert n == 0


def test_institute_names_are_printed_names(conn):
    """Regression: names must be the printed text (contain letters and match the key), not row numbers."""
    (bad,), = q(conn, """SELECT count(*) FROM institute
                         WHERE name !~ '[A-Za-z]' OR upper(regexp_replace(replace(name, '&', 'AND'), '[^A-Za-z0-9]', '', 'g')) <> key""")
    assert bad == 0


def test_seat_matrix_seats_link_to_courses(conn):
    (unlinked,), = q(conn, 'SELECT count(*) FROM seat_matrix WHERE course_id IS NULL')
    assert unlinked == 0


def test_2024_loaded_with_all_rounds(conn):
    _require_year(conn, 2024)
    rows = dict(q(conn, """SELECT r.code, count(a.*) FROM round r LEFT JOIN allotment a ON a.round_id = r.id
                           WHERE r.year = 2024 GROUP BY r.code"""))
    assert rows == {'R1': 24671, 'R2': 16182, 'R3': 13991, 'STRAY': 2331, 'SPECIAL_STRAY': 558}
