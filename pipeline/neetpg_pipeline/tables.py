"""Rebuild the allotment result tables from word coordinates.

Each record starts at a number in the layout's anchor (rank) column and continues – including wrapped
lines – until the next rank. Words are assigned to a column by their x position.
"""
from __future__ import annotations

import bisect
from dataclasses import dataclass, field

import pandas as pd

from .pdfwords import Word

CATEGORY_WORDS = {'Open', 'OBC', 'EWS', 'SC', 'ST'}


@dataclass
class ParseStats:
    pages_total: int = 0
    first_table_page: int | None = None
    records: int = 0
    orphan_words: int = 0          # words above the first record of a page (should be 0)
    straddling_words: int = 0      # words crossing into the next column (should be 0)
    straddle_examples: list = field(default_factory=list)


def _is_footer_start(words: list[Word], j: int) -> bool:
    return words[j].text == 'Page' and j + 1 < len(words) and words[j + 1].text == 'No.'


def parse_table(pages: list[list[Word]], layout: dict) -> tuple[pd.DataFrame, ParseStats]:
    names = [c for c, _ in layout['columns']]
    starts = [float(x) for _, x in layout['columns']]
    ax0, ax1 = layout['anchor']
    is_anchor = lambda w: ax0 <= w.x0 < ax1 and w.text.isdigit()
    allotted_idx = {i for i, n in enumerate(names) if n.endswith('allotted_cat')}

    stats = ParseStats(pages_total=len(pages))
    records = []
    started = False
    for pno, words in enumerate(pages, 1):
        if not started:
            # legend pages come first; the table starts on the first page with a 'Rank' header
            rank_hdr = [w for w in words if w.text == 'Rank']
            if not rank_hdr:
                continue
            started = True
            stats.first_table_page = pno
            hdr_bottom = max(w.y1 for w in rank_hdr)
            words = [w for w in words if w.y0 > hdr_bottom + 1]
            anchors = [w for w in words if is_anchor(w)]
            if not anchors:
                continue
            first = min(a.y0 for a in anchors)
            words = [w for w in words if w.y0 >= first - 4]
        footer = [words[j].y0 for j in range(len(words)) if _is_footer_start(words, j)]
        if footer:
            words = [w for w in words if w.y0 < min(footer) - 3]
        anchors = sorted((w for w in words if is_anchor(w)), key=lambda w: w.y0)
        if not anchors:
            continue
        stats.orphan_words += sum(w.y0 < anchors[0].y0 - 4 for w in words)
        for i, a in enumerate(anchors):
            y0 = a.y0 - 4
            y1 = anchors[i + 1].y0 - 4 if i + 1 < len(anchors) else float('inf')
            cells: dict[str, list[str]] = {n: [] for n in names}
            for w in sorted((w for w in words if y0 <= w.y0 < y1), key=lambda w: (round(w.y0), w.x0)):
                idx = bisect.bisect_right(starts, w.x0) - 1
                # e.g. 'Open' of 'Open PwD' sometimes starts a few points left of the category column
                if idx + 1 in allotted_idx and w.text in CATEGORY_WORDS and w.x1 > starts[idx + 1]:
                    idx += 1
                if idx + 1 < len(starts) and w.x1 > starts[idx + 1] + 2:
                    stats.straddling_words += 1
                    if len(stats.straddle_examples) < 10:
                        stats.straddle_examples.append({'page': pno, 'word': w.text, 'column': names[idx]})
                cells[names[idx]].append(w.text)
            rec = {n: ' '.join(v) for n, v in cells.items()}
            rec['page'] = pno
            records.append(rec)
    stats.records = len(records)
    return pd.DataFrame(records, columns=names + ['page']), stats
