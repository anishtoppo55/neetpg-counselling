"""Read word bounding boxes from a PDF with poppler's `pdftotext -bbox`."""
from __future__ import annotations

import hashlib
import html
import pickle
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import settings

WORD_RE = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>')


@dataclass(frozen=True, slots=True)
class Word:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def read_words(path: Path, first: int | None = None, last: int | None = None) -> list[list[Word]]:
    """Return one list of words per page (pages first..last, 1-based, inclusive)."""
    cmd = ['pdftotext', '-bbox']
    if first: cmd += ['-f', str(first)]
    if last: cmd += ['-l', str(last)]
    out = subprocess.run(cmd + [str(path), '-'], capture_output=True, text=True, check=True).stdout
    pages: list[list[Word]] = []
    for line in out.splitlines():
        if line.lstrip().startswith('<page '):
            pages.append([])
        elif pages:
            m = WORD_RE.search(line)
            if m:
                pages[-1].append(Word(float(m[1]), float(m[2]), float(m[3]), float(m[4]), html.unescape(m[5])))
    return pages


def read_words_cached(path: Path) -> list[list[Word]]:
    """read_words() with an on-disk cache keyed by the file's SHA-256 (cache dir is safe to delete)."""
    digest = sha256(path)
    cache = settings.CACHE_DIR / 'words' / f'{digest}.pkl'
    if cache.exists():
        with open(cache, 'rb') as fh:
            return pickle.load(fh)
    pages = read_words(path)
    cache.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache.with_suffix('.tmp')
    with open(tmp, 'wb') as fh:
        pickle.dump(pages, fh, protocol=pickle.HIGHEST_PROTOCOL)
    tmp.replace(cache)
    return pages


def page_text(path: Path, first: int, last: int) -> str:
    """Plain text of a page range in layout mode (used for legends)."""
    return subprocess.run(['pdftotext', '-layout', '-f', str(first), '-l', str(last), str(path), '-'],
                          capture_output=True, text=True, check=True).stdout
