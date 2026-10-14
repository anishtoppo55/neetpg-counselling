"""Command line interface.

    python -m neetpg_pipeline migrate                    create / upgrade the database schema
    python -m neetpg_pipeline check  --year 2024         parse + validate only (no database)
    python -m neetpg_pipeline import --year 2025 --year 2024
    python -m neetpg_pipeline status                     what is loaded, last import per year
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime

from . import db, settings


def _print_report(rep: dict) -> None:
    for name, c in rep['checks'].items():
        mark = 'ok ' if c['ok'] else ('ERR' if name in rep['errors'] else 'WRN')
        print(f'  [{mark}] {name}: {json.dumps(c["details"], default=str)[:220]}')
    extra = [w for w in rep['warnings'] if w not in rep['checks']]
    for w in extra:
        print(f'  [WRN] {w}')


def _save_report(rep: dict) -> str:
    settings.REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = settings.REPORT_DIR / f"import_{rep['year']}_{datetime.now():%Y%m%d_%H%M%S}.json"
    path.write_text(json.dumps(rep, indent=2, default=str))
    return str(path)


def cmd_migrate(_args) -> int:
    with db.connect() as conn:
        applied = db.migrate(conn)
    print('applied:', applied or 'nothing (up to date)')
    return 0


def _extract(year: int):
    from .extract import extract_year
    t = time.time()
    data, rep = extract_year(year)
    print(f'== {year}: extracted in {time.time() - t:.0f}s')
    return data, rep


def cmd_check(args) -> int:
    rc = 0
    for y in args.year:
        _, rep = _extract(y)
        d = rep.as_dict()
        _print_report(d)
        print(f'   report: {_save_report(d)}  ->  {"PASS" if d["ok"] else "FAIL"}')
        rc |= 0 if d['ok'] else 1
    return rc


def cmd_import(args) -> int:
    from .load import load_year, record_run
    rc = 0
    with db.connect() as conn:
        db.migrate(conn)
        for y in args.year:
            data, rep = _extract(y)
            d = rep.as_dict()
            if not d['ok']:
                _print_report(d)
                record_run(conn, y, 'failed', d) if _year_exists(conn, y) else None
                print(f'   report: {_save_report(d)}  ->  FAIL, nothing written for {y}')
                rc = 1
                continue
            counts = load_year(conn, data, rep)
            d = rep.as_dict() | {'loaded': counts}
            record_run(conn, y, 'succeeded', d)
            _print_report(d)
            print(f'   loaded: {counts}')
            print(f'   report: {_save_report(d)}  ->  OK')
    return rc


def _year_exists(conn, y: int) -> bool:
    return conn.execute('SELECT 1 FROM counselling_year WHERE year = %s', (y,)).fetchone() is not None


def cmd_status(_args) -> int:
    with db.connect() as conn:
        rows = conn.execute('''
            SELECT r.year, r.code, r.name, count(rr.*) AS ranks, count(a.*) AS allotted,
                   min(a.rank) AS best_rank, max(a.rank) AS last_rank
            FROM round r LEFT JOIN round_result rr ON rr.round_id = r.id
            LEFT JOIN allotment a ON a.round_id = rr.round_id AND a.rank = rr.rank
            GROUP BY r.year, r.code, r.name, r.seq ORDER BY r.year, r.seq''').fetchall()
        print(f'{"year":>4} {"round":<14} {"ranks":>7} {"allotted":>8} {"best":>7} {"last":>7}')
        for y, code, _name, ranks, allotted, best, last in rows:
            print(f'{y:>4} {code:<14} {ranks:>7} {allotted:>8} {best or "-":>7} {last or "-":>7}')
        for t in ('institute', 'course', 'seat_matrix', 'reporting_status', 'category_eligibility', 'cutoff'):
            print(f'{t}: {conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]}')
        runs = conn.execute('SELECT DISTINCT ON (year) year, status, finished_at, report->\'warnings\' '
                            'FROM import_run ORDER BY year, id DESC').fetchall()
        for y, st, ts, warn in runs:
            print(f'last import {y}: {st} at {ts:%Y-%m-%d %H:%M} warnings={warn}')
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog='neetpg_pipeline', description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('migrate').set_defaults(fn=cmd_migrate)
    years = sorted(settings.sources())
    for name, fn in (('check', cmd_check), ('import', cmd_import)):
        p = sub.add_parser(name)
        p.add_argument('--year', type=int, action='append', required=True, choices=years)
        p.set_defaults(fn=fn)
    sub.add_parser('status').set_defaults(fn=cmd_status)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == '__main__':
    sys.exit(main())
