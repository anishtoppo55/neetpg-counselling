"""Write one extracted counselling year into PostgreSQL (replacing that year's previous data)."""
from __future__ import annotations

import json

import pandas as pd
import yaml

from . import db, settings, vocab
from .extract import Report, YearData


def _none(v):
    """pandas missing values -> None for COPY."""
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


def eligibility_rules(year: int) -> dict | None:
    """rules/eligibility.yaml entry for a year (None when the year has no reviewed rules yet)."""
    path = settings.RULES_DIR / 'eligibility.yaml'
    if not path.exists():
        return None
    with open(path) as fh:
        return (yaml.safe_load(fh) or {}).get('years', {}).get(year)


def load_year(conn, data: YearData, report: Report) -> dict:
    y = data.year
    counts = {}
    with conn.transaction():
        # ---- remove the previous import of this year (children cascade from round)
        conn.execute('DELETE FROM category_eligibility WHERE year = %s', (y,))
        conn.execute('DELETE FROM round WHERE year = %s', (y,))
        conn.execute('DELETE FROM source_document WHERE year = %s', (y,))
        conn.execute('INSERT INTO counselling_year (year, label) VALUES (%s, %s) '
                     'ON CONFLICT (year) DO UPDATE SET label = EXCLUDED.label', (y, data.label))

        # ---- courses (whole catalogue; shared by all years)
        seen = set()
        for c in vocab.course_catalog().values():
            if c['code'] in seen:
                continue
            seen.add(c['code'])
            conn.execute('INSERT INTO course (code, name, branch, branch_group, degree) VALUES (%s,%s,%s,%s,%s) '
                         'ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name, branch = EXCLUDED.branch, '
                         'branch_group = EXCLUDED.branch_group, degree = EXCLUDED.degree',
                         (c['code'], c['name'], c['branch'], c['branch_group'], c['degree']))
        course_id = dict(conn.execute('SELECT code, id FROM course').fetchall())

        # ---- institutes (shared; the most recent year's printed name wins)
        inst = data.institutes
        with conn.cursor() as cur:
            cur.executemany(
                'INSERT INTO institute (key, name, short_name, state, mcc_code, last_year) VALUES (%s,%s,%s,%s,%s,%s) '
                'ON CONFLICT (key) DO UPDATE SET '
                '  name = CASE WHEN institute.last_year <= EXCLUDED.last_year THEN EXCLUDED.name ELSE institute.name END, '
                '  short_name = CASE WHEN institute.last_year <= EXCLUDED.last_year THEN EXCLUDED.short_name ELSE institute.short_name END, '
                '  state = COALESCE(CASE WHEN institute.last_year <= EXCLUDED.last_year THEN EXCLUDED.state END, institute.state), '
                '  mcc_code = COALESCE(EXCLUDED.mcc_code, institute.mcc_code), '
                '  last_year = GREATEST(institute.last_year, EXCLUDED.last_year)',
                # use r['name'], not r.name: on an iterrows() Series, .name is the row index
                [(r['key'], r['name'], r['short_name'], _none(r['state']), _none(r.get('mcc_code')), y)
                 for _, r in inst.iterrows()])
        inst_id = dict(conn.execute('SELECT key, id FROM institute').fetchall())

        # ---- source documents
        doc_id = {}
        rules = eligibility_rules(y)
        docs = list(data.documents)
        if rules and rules.get('source'):
            p = rules['source']
            from . import pdfwords
            docs.append({'path': p, 'year': y, 'kind': 'rules', 'title': rules.get('source_title'), 'url': None,
                         'sha256': pdfwords.sha256(settings.RAW_DIR / p), 'pages': None})
        for d in docs:
            row = conn.execute(
                'INSERT INTO source_document (year, path, kind, title, url, sha256, pages) VALUES (%s,%s,%s,%s,%s,%s,%s) '
                'ON CONFLICT (path) DO UPDATE SET sha256 = EXCLUDED.sha256 RETURNING id',
                (d['year'], d['path'], d['kind'], d['title'], d['url'], d['sha256'], d['pages'])).fetchone()
            doc_id[d['path']] = row[0]

        # ---- rounds
        round_id = {}
        for r in data.rounds:
            round_id[r['code']] = conn.execute(
                'INSERT INTO round (year, code, seq, name, kind) VALUES (%s,%s,%s,%s,%s) RETURNING id',
                (y, r['code'], r['seq'], r['name'], r['kind'])).fetchone()[0]

        # ---- facts
        res = data.results
        counts['round_result'] = db.copy_rows(conn, 'round_result',
            ['round_id', 'rank', 'allotted', 'remarks', 'source_document_id', 'source_page'],
            ((round_id[r.round_code], int(r.rank), bool(r.allotted), _none(r.remarks), doc_id[r.doc_path], int(r.page))
             for r in res.itertuples()))
        al = data.allotments
        counts['allotment'] = db.copy_rows(conn, 'allotment',
            ['round_id', 'rank', 'quota_code', 'institute_id', 'course_id', 'seat_category_code',
             'candidate_category_code', 'option_no'],
            ((round_id[r.round_code], int(r.rank), r.quota_code, inst_id[r.institute_key], course_id[r.course_code],
              r.seat_category_code, _none(r.candidate_category_code),
              None if _none(r.option_no) is None else int(r.option_no)) for r in al.itertuples()))
        rp = data.reporting
        counts['reporting_status'] = db.copy_rows(conn, 'reporting_status',
            ['round_id', 'rank', 'status', 'source_document_id'],
            ((round_id[r.round_code], int(r.rank), r.status, doc_id[r.doc_path]) for r in rp.itertuples())) if len(rp) else 0
        sm = data.seat_matrix
        r1 = next(r['code'] for r in sorted(data.rounds, key=lambda r: r['seq']))
        counts['seat_matrix'] = db.copy_rows(conn, 'seat_matrix',
            ['round_id', 'matrix', 'institute_name', 'mcc_code', 'institute_id', 'course_name', 'course_id',
             'quota_code', 'seat_category_code', 'seats', 'source_document_id', 'source_page'],
            ((round_id[r1], r.matrix, r.institute_name, _none(r.mcc_code),
              inst_id.get(r.institute_key) if _none(r.institute_key) else None, r.course_name, course_id[r.course_code],
              r.quota_code, _none(r.seat_category_code), int(r.seats), doc_id[r.doc_path], int(r.page))
             for r in sm.itertuples())) if len(sm) else 0

        # ---- category eligibility rules
        n = 0
        if rules:
            src = doc_id.get(rules.get('source'))
            for rule in rules['rules']:
                for seat in rule['seats']:
                    conn.execute('INSERT INTO category_eligibility (year, candidate_category_code, seat_category_code, '
                                 'source_document_id, source_clause, confirmed, notes) VALUES (%s,%s,%s,%s,%s,%s,%s)',
                                 (y, rule['candidate'], seat, src, rule['clause'], bool(rules.get('confirmed', False)),
                                  rule.get('notes')))
                    n += 1
        else:
            report.warnings.append('eligibility.no_rules_for_year')
        counts['category_eligibility'] = n

        conn.execute('REFRESH MATERIALIZED VIEW cutoff')
        counts['cutoff_rows_total'] = conn.execute('SELECT count(*) FROM cutoff').fetchone()[0]
    return counts


def record_run(conn, year: int, status: str, report: dict) -> None:
    conn.execute("INSERT INTO import_run (year, finished_at, status, report) VALUES (%s, now(), %s, %s)",
                 (year, status, json.dumps(report, default=str)))
    conn.commit()
