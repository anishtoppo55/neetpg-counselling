"""Parse MCC seat-matrix PDFs (Round-1 AIQ, central-internal, DNB and deemed matrices).

The matrices have centred, wrapping text columns, so fixed column borders measured by hand are fragile.
Instead, per document:
1. the header row is located by its 'TotalSeats' / 'Seats' label and its words are clustered by x-overlap into
   column labels (multi-line labels such as 'General-' / 'EWS' / 'PwD' are joined);
2. the border between two neighbouring columns is placed at the x with the least word coverage between the two
   header centres (the whitespace valley), measured over all data rows of the document;
3. each record is anchored by the number in the total column; every other word belongs to the nearest anchor
   by y (wrapped lines sit above and below the anchor line);
4. words are put into columns by their centre x and joined in reading order.

Formats: wide (seat count per category + TotalSeats), long (one 'Category' cell such as 'EW NO'), and
totals-only (deemed universities).
"""
from __future__ import annotations

import bisect
import re
from dataclasses import dataclass, field

import pandas as pd

from . import vocab
from .pdfwords import Word

WIDE_CATEGORY_LABELS = {  # header label key -> seat category
    'OPEN': 'OPEN', 'OPENPWD': 'OPEN_PWD', 'GENERALEWS': 'EWS', 'GENERALEWSPWD': 'EWS_PWD', 'OBC': 'OBC',
    'OBCPWD': 'OBC_PWD', 'SC': 'SC', 'SCPWD': 'SC_PWD', 'ST': 'ST', 'STPWD': 'ST_PWD',
}
TOTAL_LABELS = ('TOTALSEATS', 'SEATS')
TEXT_LABELS = {'INSTITUTETYPE': 'institute_type', 'INSTITUTE': 'institute', 'PROGRAM': 'course',
               'BRANCH': 'course', 'QUOTA': 'quota', 'STATENAME': 'state', 'CATEGORY': 'category'}
LONG_CATEGORY = {'OP': 'OPEN', 'GN': 'OPEN', 'BC': 'OBC', 'EW': 'EWS', 'SC': 'SC', 'ST': 'ST'}
CODE_RE = re.compile(r'\(\s*(\d{6})\s*\)')
TITLE_RE = re.compile(r'MATRIX|COUNSELLING|PAGE|^OF$', re.I)
HEADER_WORDS = {'INSTITUTE', 'TYPE', 'PROGRAM', 'BRANCH', 'QUOTA', 'OPEN', 'PWD', 'GENERAL', 'GENERALEWS', 'EWS',
                'OBC', 'SC', 'ST', 'TOTALSEATS', 'SEATS', 'STATENAME', 'CATEGORY'}
RECORD_GAP = 10.5      # points between text lines; larger gaps separate records


@dataclass
class Column:
    label: str
    x0: float
    x1: float

    @property
    def centre(self) -> float:
        return (self.x0 + self.x1) / 2


@dataclass
class MatrixStats:
    pages: int = 0
    records: int = 0
    columns: list = field(default_factory=list)
    pages_without_header: list = field(default_factory=list)
    ambiguous_pages: list = field(default_factory=list)
    total_mismatch: int = 0          # wide rows whose category counts do not add up to the total
    unknown_course: dict = field(default_factory=dict)
    unknown_quota: dict = field(default_factory=dict)
    missing_institute_code: int = 0
    bad_category: dict = field(default_factory=dict)
    seats_total: int = 0             # sum of the total column over all records


def _total_word(words: list[Word]) -> Word | None:
    for label in TOTAL_LABELS:
        cand = [w for i, w in enumerate(words) if vocab.key(w.text) == label
                and not (i + 1 < len(words) and TITLE_RE.search(words[i + 1].text))]
        if cand:
            return max(cand, key=lambda w: w.x0)
    return None


def _label(group: list[Word]) -> str:
    label = vocab.key(''.join(w.text for w in sorted(group, key=lambda w: (round(w.y0), w.x0))))
    half = len(label) // 2
    if len(label) % 2 == 0 and label[:half] == label[half:]:   # label printed twice (e.g. repeated header)
        label = label[:half]
    return label


def _header(words: list[Word]) -> tuple[list[Column], float] | None:
    t = _total_word(words)
    if t is None:
        return None
    band = [w for w in words if t.y0 - 12 <= w.y0 <= t.y1 + 12 and vocab.key(w.text) in HEADER_WORDS]
    band.sort(key=lambda w: w.x0)
    groups: list[list[Word]] = []
    for w in band:
        if groups and w.x0 <= max(g.x1 for g in groups[-1]) + 3:
            groups[-1].append(w)
        else:
            groups.append([w])
    cols = [Column(_label(g), min(w.x0 for w in g), max(w.x1 for w in g)) for g in groups]
    return cols, max(w.y1 for w in band)


def _group_records(body: list[Word], anchors: list[Word], col_of) -> list[list[Word]] | None:
    """Split the page body into records.

    Lines inside one record are 6–9 pt apart, the gap between records is larger (≥ 12 pt), so lines are first
    clustered at gaps > RECORD_GAP. A cluster with one anchor is one record; a cluster with several anchors
    (records without vertical padding) is split by nearest anchor; a cluster without an anchor joins the
    nearest record.
    """
    ys = sorted({round((w.y0 + w.y1) / 2, 1) for w in body})
    clusters: list[list[float]] = []
    for y in ys:
        if clusters and y - clusters[-1][-1] <= RECORD_GAP:
            clusters[-1].append(y)
        else:
            clusters.append([y])
    ay = [(a.y0 + a.y1) / 2 for a in anchors]
    recs: list[list[Word]] = [[] for _ in anchors]
    yc_of = lambda w: round((w.y0 + w.y1) / 2, 1)
    for c in clusters:
        lo, hi = c[0] - 0.05, c[-1] + 0.05
        words = [w for w in body if lo <= yc_of(w) <= hi]
        inside = [i for i, a in enumerate(ay) if lo - 1 <= a <= hi + 1]
        if len(inside) == 1:
            for w in words: recs[inside[0]].append(w)
            continue
        if not inside:                       # stray text: nearest record
            for w in words: recs[min(range(len(ay)), key=lambda i: abs(ay[i] - yc_of(w)))].append(w)
            continue
        # several records without padding: per column, split its lines into contiguous blocks centred on anchors
        for col in {col_of(w) for w in words}:
            cw = [w for w in words if col_of(w) == col]
            lines = sorted({yc_of(w) for w in cw})
            assign = _split_lines(lines, [ay[i] for i in inside])
            for w in cw:
                recs[inside[assign[lines.index(yc_of(w))]]].append(w)
    return recs


def _split_lines(lines: list[float], anchors: list[float]) -> list[int]:
    """Assign sorted line positions to sorted anchors as contiguous blocks (some may be empty), minimising each
    line's distance to its anchor plus a penalty when a block is not centred on its anchor.
    Returns the anchor index per line."""
    n, m = len(lines), len(anchors)
    INF = float('inf')
    # best[j][i]: min cost assigning first i lines to first j anchors; back[j][i]: start of the j-th block
    best = [[INF] * (n + 1) for _ in range(m + 1)]
    back = [[0] * (n + 1) for _ in range(m + 1)]
    best[0][0] = 0.0
    for j in range(1, m + 1):
        for i in range(n + 1):
            for s in range(i + 1):
                if best[j - 1][s] == INF:
                    continue
                block = lines[s:i]
                a = anchors[j - 1]
                # distance of every line to its anchor + penalty for an off-centre block (cells are centred)
                cost = (sum(abs(l - a) for l in block) + 2 * abs(sum(block) / len(block) - a) * len(block)
                        if block else 0.0)
                if best[j - 1][s] + cost < best[j][i]:
                    best[j][i], back[j][i] = best[j - 1][s] + cost, s
    out, i = [0] * n, n
    for j in range(m, 0, -1):
        s = back[j][i]
        for k in range(s, i):
            out[k] = j - 1
        i = s
    return out


def _body(words: list[Word], hdr_bottom: float) -> list[Word]:
    return [w for w in words if w.y0 > hdr_bottom + 1 and not TITLE_RE.search(w.text)]


def _borders(cols: list[Column], pages_body: list[list[Word]], width: int) -> list[float]:
    """x borders between consecutive columns at the coverage minimum between their centres."""
    cov = [0] * (width + 2)
    for body in pages_body:
        for w in body:
            for x in range(max(0, int(w.x0)), min(width + 1, int(w.x1) + 1)):
                cov[x] += 1
    borders = []
    for a, b in zip(cols, cols[1:]):
        lo, hi = int(a.centre) + 1, int(b.centre)
        if hi <= lo:
            borders.append((a.centre + b.centre) / 2); continue
        m = min(cov[lo:hi])
        run = [x for x in range(lo, hi) if cov[x] == m]
        # middle of the longest minimum run
        best, cur = [], []
        for x in run:
            cur = cur + [x] if cur and x == cur[-1] + 1 else [x]
            if len(cur) > len(best): best = cur
        borders.append((best[0] + best[-1]) / 2)
    return borders


def parse_matrix(pages: list[list[Word]]) -> tuple[pd.DataFrame, MatrixStats]:
    stats = MatrixStats(pages=len(pages))
    headers = [_header(p) for p in pages]
    ref = next((h for h in headers if h), None)
    if ref is None:
        return pd.DataFrame(), stats
    cols = ref[0]
    stats.columns = [c.label for c in cols]
    width = int(max(w.x1 for p in pages for w in p)) + 1
    bodies = [(_body(p, h[1]) if h else []) for p, h in zip(pages, headers)]
    stats.pages_without_header = [i + 1 for i, h in enumerate(headers) if h is None]
    borders = _borders(cols, bodies, width)
    total_idx = next(i for i, c in enumerate(cols) if c.label in TOTAL_LABELS)

    rows = []
    for pno, body in enumerate(bodies, 1):
        col_of = lambda w: bisect.bisect_right(borders, (w.x0 + w.x1) / 2)
        anchors = sorted((w for w in body if w.text.isdigit() and col_of(w) == total_idx), key=lambda w: w.y0)
        if not anchors:
            continue
        recs = _group_records(body, anchors, col_of)
        if recs is None:
            stats.ambiguous_pages.append(pno)
            continue
        for rw in recs:
            cells: dict[str, list[Word]] = {}
            for w in rw:
                cells.setdefault(cols[col_of(w)].label, []).append(w)
            rec = {'page': pno}
            for label, ws in cells.items():
                rec[label] = vocab.clean(' '.join(w.text for w in sorted(ws, key=lambda w: (round(w.y0), w.x0))))
            rows.append(rec)
    stats.records = len(rows)
    return _to_long(rows, stats), stats


def _to_long(rows: list[dict], stats: MatrixStats) -> pd.DataFrame:
    out = []
    for r in rows:
        inst = r.get('INSTITUTE', '')
        # the 6-digit MCC institute code is printed after the name; it can wrap into a neighbouring cell
        codes = CODE_RE.findall(inst) or [c for k, v in r.items() if k != 'page' for c in CODE_RE.findall(str(v))]
        if not codes:
            stats.missing_institute_code += 1
        name = vocab.clean(CODE_RE.sub(' ', inst).strip(' ,'))
        course_txt = r.get('PROGRAM', r.get('BRANCH', ''))
        crs = vocab.course(course_txt)
        if crs is None:
            stats.unknown_course[course_txt] = stats.unknown_course.get(course_txt, 0) + 1
        q = vocab.quota_code(r.get('QUOTA', ''))
        if q is None:
            stats.unknown_quota[r.get('QUOTA', '')] = stats.unknown_quota.get(r.get('QUOTA', ''), 0) + 1
        base = dict(page=r['page'], institute_name=name, mcc_code=codes[-1] if codes else None,
                    course_name=course_txt, course_code=crs['code'] if crs else None, quota_code=q,
                    institute_type=r.get('INSTITUTETYPE'), state_printed=r.get('STATENAME'))
        total_txt = next((r[k] for k in TOTAL_LABELS if k in r), '0')
        total = int(total_txt) if total_txt.isdigit() else 0
        stats.seats_total += total
        cats = {WIDE_CATEGORY_LABELS[k]: int(v) for k, v in r.items() if k in WIDE_CATEGORY_LABELS and str(v).isdigit()}
        if any(k in WIDE_CATEGORY_LABELS for k in stats.columns):          # wide format
            if sum(cats.values()) != total or len(cats) != len(WIDE_CATEGORY_LABELS):
                stats.total_mismatch += 1
            for c, n in cats.items():
                if n:
                    out.append(base | {'seat_category_code': c, 'seats': n})
        elif 'CATEGORY' in stats.columns:                     # long format: 'EW NO', 'OP PH' (PH = PwD)
            parts = r.get('CATEGORY', '').split()
            c = LONG_CATEGORY.get(parts[0]) if parts else None
            if c is None or len(parts) != 2 or parts[1] not in ('NO', 'YES', 'PH'):
                stats.bad_category[r.get('CATEGORY', '')] = stats.bad_category.get(r.get('CATEGORY', ''), 0) + 1
            else:
                out.append(base | {'seat_category_code': c + ('' if parts[1] == 'NO' else '_PWD'), 'seats': total})
        else:                                                              # totals only (deemed)
            out.append(base | {'seat_category_code': None, 'seats': total})
    return pd.DataFrame(out)
