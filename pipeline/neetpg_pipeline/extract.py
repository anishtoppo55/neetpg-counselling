"""Turn parsed PDF tables into clean, validated records for one counselling year (no database access)."""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from . import pdfwords, seatmatrix, settings, tables, vocab


@dataclass
class Report:
    year: int
    errors: list = field(default_factory=list)      # any error fails the import
    warnings: list = field(default_factory=list)
    checks: dict = field(default_factory=dict)       # name -> details

    def check(self, name: str, ok: bool, details, hard: bool = True):
        self.checks[name] = {'ok': bool(ok), 'details': details}
        if not ok:
            (self.errors if hard else self.warnings).append(name)

    def as_dict(self) -> dict:
        return {'year': self.year, 'ok': not self.errors, 'errors': self.errors, 'warnings': self.warnings,
                'checks': self.checks}


@dataclass
class YearData:
    year: int
    label: str
    documents: list = field(default_factory=list)    # dicts for source_document
    rounds: list = field(default_factory=list)       # dicts from sources.yaml
    results: pd.DataFrame | None = None              # round_code, rank, allotted, remarks, doc_path, page
    allotments: pd.DataFrame | None = None           # round_code, rank, quota, institute_key, course_code, ...
    reporting: pd.DataFrame | None = None            # round_code, rank, status, doc_path
    institutes: pd.DataFrame | None = None           # key, name, short_name, state
    seat_matrix: pd.DataFrame | None = None


def _manifest() -> dict[str, dict]:
    path = settings.RAW_DIR / 'manifest.csv'
    if not path.exists():
        return {}
    with open(path) as fh:
        return {r['path']: r for r in csv.DictReader(fh)}


def _document(path: str, year: int | None, kind: str, pages: int, manifest: dict) -> dict:
    m = manifest.get(path, {})
    return {'path': path, 'year': year, 'kind': kind, 'title': m.get('title'), 'url': m.get('url'),
            'sha256': pdfwords.sha256(settings.RAW_DIR / path), 'pages': pages}


def _int(s) -> int | None:
    s = str(s).strip()
    return int(s) if s.isdigit() else None


def extract_year(year: int) -> tuple[YearData, Report]:
    cfg = settings.sources()[year]
    layouts = settings.layouts()
    manifest = _manifest()
    rep = Report(year)
    data = YearData(year=year, label=cfg['label'], rounds=cfg['rounds'])
    parsed: dict[str, pd.DataFrame] = {}

    # ------------------------------------------------------------------ round result PDFs
    results, allots = [], []
    for rnd in cfg['rounds']:
        code, path = rnd['code'], rnd['file']
        if not (settings.RAW_DIR / path).exists():
            rep.check(f'{code}.file_exists', False, path); continue
        pages = pdfwords.read_words_cached(settings.RAW_DIR / path)
        data.documents.append(_document(path, year, 'allotments', len(pages), manifest))
        df, st = tables.parse_table(pages, layouts[rnd['layout']])
        parsed[code] = df
        rank = pd.to_numeric(df['rank'], errors='coerce')
        rep.check(f'{code}.parse', st.orphan_words == 0 and st.straddling_words == 0 and len(df) > 0,
                  {'rows': len(df), 'first_table_page': st.first_table_page, 'orphan_words': st.orphan_words,
                   'straddling_words': st.straddling_words, 'examples': st.straddle_examples})
        rep.check(f'{code}.ranks_unique_sorted', rank.notna().all() and rank.is_unique and rank.is_monotonic_increasing,
                  {'min': int(rank.min()), 'max': int(rank.max())})
        if 'sno' in df:
            sno = pd.to_numeric(df['sno'], errors='coerce')
            rep.check(f'{code}.serial_numbers_continuous', sno.notna().all() and (sno.diff().dropna() == 1).all()
                      and sno.iloc[0] == 1, {'last': int(sno.max())})

        allotted = ~df['cur_quota'].map(vocab.blank)
        quota = df['cur_quota'].map(vocab.quota_code)
        course = df['cur_course'].map(vocab.course)
        seat = df['cur_allotted_cat'].map(vocab.seat_category)
        cand = df['cur_candidate_cat'].map(vocab.candidate_category)
        bad = {
            'quota': df.loc[allotted & quota.isna(), 'cur_quota'].value_counts().head(10).to_dict(),
            'course': df.loc[allotted & course.isna(), 'cur_course'].value_counts().head(10).to_dict(),
            'seat_category': df.loc[allotted & seat.isna(), 'cur_allotted_cat'].value_counts().head(10).to_dict(),
            'candidate_category': df.loc[allotted & cand.isna() & ~df['cur_candidate_cat'].map(vocab.blank),
                                         'cur_candidate_cat'].value_counts().head(10).to_dict(),
            'institute': int((allotted & df['cur_institute'].map(vocab.blank)).sum()),
            'candidate_category_missing': int((allotted & df['cur_candidate_cat'].map(vocab.blank)).sum()),
        }
        rep.check(f'{code}.vocabulary', not any(bad.values()), bad)
        rep.checks[f'{code}.counts'] = {'ok': True, 'details': {
            'ranks': len(df), 'allotted': int(allotted.sum()),
            'by_quota': quota[allotted].value_counts().to_dict(),
            'by_seat_category': seat[allotted].value_counts().to_dict()}}

        remarks = df['cur_remarks'].map(lambda s: None if vocab.blank(s) else vocab.clean(s))
        results.append(pd.DataFrame({'round_code': code, 'rank': rank.astype(int), 'allotted': allotted,
                                     'remarks': remarks, 'doc_path': path, 'page': df['page']}))
        a = df[allotted]
        allots.append(pd.DataFrame({
            'round_code': code, 'rank': rank[allotted].astype(int), 'quota_code': quota[allotted],
            'institute_name': a['cur_institute'].map(vocab.clean),
            'course_code': course[allotted].map(lambda c: c['code'] if c else None),
            'seat_category_code': seat[allotted], 'candidate_category_code': cand[allotted],
            'option_no': a['cur_option'].map(_int) if 'cur_option' in a else None}))
    data.results = pd.concat(results, ignore_index=True) if results else pd.DataFrame()
    data.allotments = pd.concat(allots, ignore_index=True) if allots else pd.DataFrame()

    # ------------------------------------------------------------------ institutes
    if len(data.allotments):
        data.allotments['institute_key'] = data.allotments['institute_name'].map(vocab.key)
        inst = data.allotments.drop_duplicates('institute_key')[['institute_key', 'institute_name']]
        data.institutes = pd.DataFrame({'key': inst['institute_key'], 'name': inst['institute_name'],
                                        'short_name': inst['institute_name'].map(vocab.short_name),
                                        'state': inst['institute_name'].map(vocab.state_of)})
        rep.checks['institutes'] = {'ok': True, 'details': {
            'count': len(data.institutes), 'without_state': int(data.institutes['state'].isna().sum())}}

    # ------------------------------------------------------------------ reporting status (from the next round's PDF)
    rows = []
    for code, src in (cfg.get('reporting_from') or {}).items():
        nxt = parsed.get(src['round'])
        if nxt is None or src['column'] not in nxt:
            rep.check(f'{code}.reporting_source', False, src); continue
        prefix = src['column'].rsplit('_', 1)[0]           # e.g. p1
        held = nxt[~nxt[f'{prefix}_quota'].map(vocab.blank)]
        own = data.allotments[data.allotments.round_code == code].set_index('rank')
        r = pd.to_numeric(held['rank']).astype(int)
        reprint_quota = held[f'{prefix}_quota'].map(vocab.quota_code).values
        in_round = r.isin(own.index)
        same_quota = pd.Series(reprint_quota, index=held.index)[in_round.values] == own.loc[r[in_round], 'quota_code'].values
        status = held[src['column']].map(lambda s: None if vocab.blank(s) else vocab.clean(s))
        # hard: every reprinted seat must be a seat of that round with the same quota (proves both parses agree)
        rep.check(f'{code}.reprinted_in_{src["round"]}', in_round.all() and same_quota.all(),
                  {'reprinted': len(held), 'allotted_in_round': len(own), 'not_allotted_in_round': int((~in_round).sum()),
                   'quota_mismatch': int((~same_quota).sum()),
                   'status_values': status.value_counts().to_dict()})
        # soft: seats of the round that the later PDF does not reprint at all (no reporting status known)
        missing = sorted(set(own.index) - set(r))
        rep.check(f'{code}.all_seats_reprinted_in_{src["round"]}', not missing,
                  {'missing_ranks': missing[:50], 'count': len(missing)}, hard=False)
        doc = next(x['file'] for x in cfg['rounds'] if x['code'] == src['round'])
        rows.append(pd.DataFrame({'round_code': code, 'rank': r[in_round.values].values,
                                  'status': status[in_round.values].values, 'doc_path': doc}))
    data.reporting = pd.concat(rows, ignore_index=True).dropna(subset=['status']) if rows else pd.DataFrame()

    # ------------------------------------------------------------------ Round-1 seat matrices
    frames = []
    for sm in cfg.get('seat_matrix') or []:
        path = sm['file']
        pages = pdfwords.read_words_cached(settings.RAW_DIR / path)
        data.documents.append(_document(path, year, 'seat_matrix', len(pages), manifest))
        df, st = seatmatrix.parse_matrix(pages)
        unknown_course_seats = int(df.loc[df['course_code'].isna(), 'seats'].sum()) if len(df) else 0
        details = {'records': st.records, 'rows': len(df), 'seats': int(df['seats'].sum()) if len(df) else 0,
                   'seats_total_column': st.seats_total, 'total_mismatch': st.total_mismatch,
                   'unknown_course_seats': unknown_course_seats, 'unknown_quota': st.unknown_quota,
                   'bad_category': st.bad_category, 'missing_institute_code': st.missing_institute_code,
                   'pages_without_header': st.pages_without_header}
        ok = (st.records > 0 and st.total_mismatch == 0 and not st.unknown_quota and not st.bad_category
              and details['seats'] == st.seats_total)
        rep.check(f'seat_matrix.{sm["matrix"]}', ok, details, hard=False)
        # rows that could not be attributed to a course are kept out but reported
        if unknown_course_seats:
            rep.warnings.append(f'seat_matrix.{sm["matrix"]}.unknown_course_seats={unknown_course_seats}')
        if len(df):
            df = df[df['course_code'].notna() & df['quota_code'].notna()].copy()
            df['matrix'], df['doc_path'] = sm['matrix'], path
            frames.append(df)
    data.seat_matrix = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if len(data.seat_matrix) and data.institutes is not None:
        _match_seat_matrix_institutes(data, rep)
    return data, rep


def _match_seat_matrix_institutes(data: YearData, rep: Report) -> None:
    """Link seat-matrix institutes (name + MCC code) to allotment institutes of the same year by name key."""
    keys = data.institutes['key'].tolist()
    by_prefix: dict[str, set] = {}
    def match(name: str) -> str | None:
        k = vocab.key(name)
        if not k:
            return None
        if k in by_prefix:
            hits = by_prefix[k]
        else:
            hits = {x for x in keys if x == k}
            if not hits:
                hits = {x for x in keys if x.startswith(k) or (len(x) >= 20 and k.startswith(x))}
            if not hits and len(k) >= 25:
                hits = {x for x in keys if x.startswith(k[:25])}
            by_prefix[k] = hits
        return next(iter(hits)) if len(hits) == 1 else None
    sm = data.seat_matrix
    names = sm.drop_duplicates('institute_name')['institute_name']
    m = {n: match(n) for n in names}
    sm['institute_key'] = sm['institute_name'].map(m)
    # MCC code per allotment institute (only when a single code maps to it)
    codes = sm.dropna(subset=['institute_key', 'mcc_code']).groupby('institute_key')['mcc_code'].agg(set)
    data.institutes['mcc_code'] = data.institutes['key'].map(lambda k: next(iter(codes[k])) if k in codes and len(codes[k]) == 1 else None)
    seats = sm.groupby(sm['institute_key'].notna())['seats'].sum().to_dict()
    rep.check('seat_matrix.institute_match', True, {
        'matrix_institutes': len(names), 'matched': int(sum(v is not None for v in m.values())),
        'seats_matched': int(seats.get(True, 0)), 'seats_unmatched': int(seats.get(False, 0)),
        'by_matrix': sm.groupby('matrix')['institute_key'].apply(lambda s: round(s.notna().mean(), 3)).to_dict()},
        hard=False)
