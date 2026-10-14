"""Crawl the MCC PG counselling pages and download the documents needed by the platform.

Usage:
    python scripts/fetch_mcc_documents.py               # download everything in DOCS
    python scripts/fetch_mcc_documents.py --dry-run     # only show what would be downloaded
    python scripts/fetch_mcc_documents.py --list        # print every PDF title found on the MCC pages

Files go to data/raw/<counselling year>/<kind>/<name>.pdf and every download is recorded in
data/raw/manifest.csv (title, source page, URL, size, sha256, download time).
Already-downloaded files are skipped, so the script can be re-run safely.

To add another year, add entries to DOCS (title regex -> year, kind, file name).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data' / 'raw'
MANIFEST = RAW / 'manifest.csv'
UA = {'User-Agent': 'Mozilla/5.0'}  # the MCC server rejects unusual user-agent strings
PAGES = [
    'https://mcc.nic.in/archive-pg/',
    'https://mcc.nic.in/news-events-pg/',
    'https://mcc.nic.in/current-events-pg/',
    'https://mcc.nic.in/pg-medical-counselling/',
]

# (title regex, counselling year, kind, file name). Regexes are matched case-insensitively against the
# link title on the MCC pages. Kinds: allotments, seat_matrix, rules, notices, admitted.
DOCS = [
    # ------------------------------------------------------------------ 2024 counselling
    (r'^Final Allotment Result Round 1 of PG Counselling 2024$',      2024, 'allotments', 'round1'),
    (r'^Final Result for Round 2 of PG Counselling 2024$',            2024, 'allotments', 'round2'),
    (r'^Final Allotment Result for Round 3 of PG Counselling 2024$',  2024, 'allotments', 'round3'),
    (r'^FINAL RESULT OF STRAY VACANCY ROUND NEET PG 2024$',           2024, 'allotments', 'stray'),
    (r'^Final Result for Special Stray Vacancy Round PG 2024$',       2024, 'allotments', 'special_stray'),
    (r'^All India Quota Seats Matrix PG 2024 Counselling$',           2024, 'seat_matrix', 'aiq_round1'),
    (r'^Central Internal Quota Seats Matrix PG 2024 Counselling$',    2024, 'seat_matrix', 'central_internal_round1'),
    (r'^Deemed University Seats Matrix PG 2024 Counselling$',         2024, 'seat_matrix', 'deemed_round1'),
    (r'^FINAL DNB SEAT MATRIX FOR PG 2024$',                          2024, 'seat_matrix', 'dnb_round1'),
    (r'^NOTICE FOR ADDITION OF DNB SEATS IN ROUND 1 OF PG COUNSELLING 2024$', 2024, 'seat_matrix', 'round1_dnb_added'),
    (r'^NOTICE FOR REMOVE THE SEATS FROM THE SEAT MATRIX ROUND 1 PG DNB 2024$', 2024, 'seat_matrix', 'round1_dnb_removed'),
    (r'^Notice for withdrawal / changed /addition in category seat$', 2024, 'seat_matrix', 'round1_category_changes'),
    (r'^CLEAR VACANY ROUND 2 PG 2024$',                               2024, 'seat_matrix', 'round2_clear_vacancy'),
    (r'^VIRTUAL VACANY ROUND 2 PG 2024$',                             2024, 'seat_matrix', 'round2_virtual_vacancy'),
    (r'^NEWLY ADDED SEATS ROUND 2 PG 2024$',                          2024, 'seat_matrix', 'round2_added'),
    (r'^Notice for addition of seats in Round 2 of PG Counselling$',  2024, 'seat_matrix', 'round2_added_notice'),
    (r'^CLEAR VACANY ROUND 3 PG 2024$',                               2024, 'seat_matrix', 'round3_clear_vacancy'),
    (r'^VIRTUAL VACANY ROUND 3 PG 2024$',                             2024, 'seat_matrix', 'round3_virtual_vacancy'),
    (r'^NEWLY ADDED SEATS ROUND 3 PG 2024$',                          2024, 'seat_matrix', 'round3_added'),
    (r'^Notice for contribution of seats for Round 3 PG 2024$',       2024, 'seat_matrix', 'round3_contributed'),
    (r'^Notice for withdrawal of Seats from Round III$',              2024, 'seat_matrix', 'round3_withdrawn'),
    (r'^Notice for withdrawal Addition of Seats for Round 3$',        2024, 'seat_matrix', 'round3_withdrawn_added'),
    (r'^VACANT SEATS STRAY ROUND PG 2024$',                           2024, 'seat_matrix', 'stray_vacant'),
    (r'^Notice for withdrawal of seat from Stray Vacancy Round$',     2024, 'seat_matrix', 'stray_withdrawn'),
    (r'^CLEAR VACANY SPECIAL STRAY VACANCY ROUND PG COUNSELLING 2024$', 2024, 'seat_matrix', 'special_stray_vacant'),
    (r'^Notice for withdrawal of Seats from Special Stray vacancy Round PG 2024$', 2024, 'seat_matrix', 'special_stray_withdrawn_1'),
    (r'^Notice for withdrawal of Seats from Special Stray vacany Round PG 2024 dated 11.03.2025$', 2024, 'seat_matrix', 'special_stray_withdrawn_2'),
    (r'^Revised PG Information Bulletin 2024$',                       2024, 'rules', 'mcc_information_bulletin'),
    (r'^Notice for reduction of Percentile$',                         2024, 'rules', 'percentile_reduction_notice'),
    (r'^Notice for eligibility of Stray Round PG Counselling 2024$',  2024, 'rules', 'stray_eligibility'),
    (r'^Eligibility for Special Stray Vacancy Round of NEET PG 2024$', 2024, 'rules', 'special_stray_eligibility'),
    (r'^Clarification regarding eligibility for Stray vacancy round of state counselling', 2024, 'rules', 'stray_state_eligibility_clarification'),
    (r'^AIQ and State Schedule PG 2024 dated 01-11-2024$',            2024, 'notices', 'schedule_2024-11-01'),
    (r'^PG Counselling 2024 Schedule dated 09.12.2024$',              2024, 'notices', 'schedule_2024-12-09'),
    (r'^Modified PG Counselling 2024 Schedule after percentile reduction Dated 20.01.2025$', 2024, 'notices', 'schedule_2025-01-20'),
    (r'^Modified PG Counselling 2024 Schedule after percentile reduction Dated 08.02.2025$', 2024, 'notices', 'schedule_2025-02-08'),
    (r'^Schedule for Special Stray Vacancy Round of NEET PG-2024$',   2024, 'notices', 'schedule_special_stray'),
    (r'^NRI LIST OF ELIGIBLE CANDIDATES FOR PG \(ROUND 1\) 2024-25$', 2024, 'notices', 'nri_list_round1'),
    (r'^NRI LIST II OF ELIGIBLE CANDIDATES FOR PG Round 1$',          2024, 'notices', 'nri_list_round1_ii'),
    (r'^NRI list for Round 2 of PG Counselling 2024$',                2024, 'notices', 'nri_list_round2'),
    (r'^NRI list for Round 3 of PG Counselling 2024$',                2024, 'notices', 'nri_list_round3'),
    (r'^Admitted Candidates List upto Round 3 in PG 2024 Counselling$', 2024, 'admitted', 'upto_round3'),
    (r'^Admitted Candidates List upto Stray Vacancy Round PG 2024',   2024, 'admitted', 'upto_stray'),
    # ------------------------------------------------------------------ 2025 counselling
    (r'^Final Result of Round 1 for PG Counselling 2025$',            2025, 'allotments', 'round1'),
    (r'^Final Result for Round 2 of PG counselling 2025$',            2025, 'allotments', 'round2'),
    (r'^Final Result for Round-III of NEET PG Counselling 2025$',     2025, 'allotments', 'round3'),
    (r'^Final Result for Stray Round of PG counselling 2025$',        2025, 'allotments', 'stray'),
    (r'^ALL INDIA QUOTA SEATS MATRIX PG 2025 COUNSELLING$',           2025, 'seat_matrix', 'aiq_round1'),
    (r'^CENTRAL INTERNAL QUOTA SEATS MATRIX PG 2025 COUNSELLING$',    2025, 'seat_matrix', 'central_internal_round1'),
    (r'^UPDATED SEATS MATRIX DEEMED PG 2025 19.11.2025$',             2025, 'seat_matrix', 'deemed_round1'),
    (r'^UPDATED SEATS MATRIX DNB PG 2025 19.11.2025$',                2025, 'seat_matrix', 'dnb_round1'),
    (r'^NOTICE FOR REMOVAL OF SEATS ROUND 1 OF PG 2025$',             2025, 'seat_matrix', 'round1_removed'),
    (r'^New list of withdrawal seats in round 1 & 2$',                2025, 'seat_matrix', 'round1_2_withdrawn'),
    (r'^CLEAR VACANCY ROUND 2 \(MD MS AND DNB\)',                     2025, 'seat_matrix', 'round2_clear_vacancy'),
    (r'^VIRTUAL VACANCY ROUND 2 \(MD MS AND DNB\)',                   2025, 'seat_matrix', 'round2_virtual_vacancy'),
    (r'^NEWLY ADDED SEATS ROUND 2 \(MD MS AND DNB\)',                 2025, 'seat_matrix', 'round2_added'),
    (r'^NEWLY ADDED SEATS ROUND 2 \(MD MS\) .*11\.12\.2025',          2025, 'seat_matrix', 'round2_added_2025-12-11'),
    (r'^21\.01\.2026_UPDATED CLEAR VACANCY ROUND 3',                  2025, 'seat_matrix', 'round3_clear_vacancy'),
    (r'^21\.01\.2026_UPDATED VIRTUAL VACANCY ROUND 3',                2025, 'seat_matrix', 'round3_virtual_vacancy'),
    (r'^NEWLY ADDED SEATS ROUND 3 \(MD MS AND DNB\)',                 2025, 'seat_matrix', 'round3_added'),
    (r'^NOTICE FOR ADDITION OF SEATS ROUND 3 OF PG 2025$',            2025, 'seat_matrix', 'round3_added_notice'),
    (r'^Notice for addition of seat dated 23.01.2026',                2025, 'seat_matrix', 'round3_added_2026-01-23'),
    (r'^NOTICE FOR ADDITION AND REMOVAL OF SEATS ROUND 3 PG 2025$',   2025, 'seat_matrix', 'round3_added_removed'),
    (r'^Notice for addition and deletion of Seats in Round 3 seat matrix 28.01.2026$', 2025, 'seat_matrix', 'round3_added_removed_2026-01-28'),
    (r'^NOTICE FOR REMOVAL OF SEATS ROUND 3 OF PG 2025 21.01.2026$',  2025, 'seat_matrix', 'round3_removed'),
    (r'^Notice for Withdrawal of seat for Round 3 of PG Counselling 2025$', 2025, 'seat_matrix', 'round3_withdrawn'),
    (r'^WITHDRAWAL SEATS AVAILABLE FOR CHOICE FILLING ROUND 3 PG 2025$', 2025, 'seat_matrix', 'round3_withdrawn_available'),
    (r'^PG VACANT SEATS FOR STRAY ROUND PG 2025$',                    2025, 'seat_matrix', 'stray_vacant'),
    (r'^NOTICE FOR ADD OR REMOVAL OF SEATS IN STRAY ROUND OF PG 2025', 2025, 'seat_matrix', 'stray_added_removed'),
    (r'^Revised PG Information Bulletin 2025 dated 27.11.2025$',      2025, 'rules', 'mcc_information_bulletin'),
    (r'^Notice for PwD candidates for Round 1 of PG Counselling 2025', 2025, 'rules', 'pwd_notice_round1'),
    (r'^PG Counselling 2025 Schedule dated 25.11.25$',                2025, 'notices', 'schedule_2025-11-25'),
    (r'^AIQ and State Schedule PG 2025 dated 17.12.2025$',            2025, 'notices', 'schedule_aiq_state_2025-12-17'),
    (r'^Schedule for Round 2 of PG Counselling dated 13.12.2025$',    2025, 'notices', 'schedule_round2'),
    (r'^Schedule of AIQ and State PG Counselling 2025 dated 09.02.2026$', 2025, 'notices', 'schedule_aiq_state_2026-02-09'),
    (r'^ADMITTED CANDIDATES LIST UPTO ROUND 3 PG 2025$',              2025, 'admitted', 'upto_round3'),
    # ------------------------------------------------------------------ cross-year rules
    (r'^Final Guidelines with respect to Persons with Benchmark Disabilities \(PwBD\) for Post Graduate Medical Courses', 'common', 'rules', 'nmc_pwbd_guidelines_pg'),
    (r'^Public Notice for eligibility of NRI candidature for Academic Year 2026-27$', 'common', 'rules', 'nri_eligibility_notice_2026-27'),
]


# Documents not listed on the MCC pages, fetched from fixed URLs (found on natboard.edu.in -> NEET-PG).
# (title, url, counselling year, kind, file name)
FIXED = [
    ('NBEMS Information Bulletin NEET-PG 2024',
     'https://natboard.edu.in/viewUpload?xyz=VU8rdjBwMzBGRjRNSDhhRHlsMWdXdz09', 2024, 'rules', 'nbems_information_bulletin'),
    ('NBEMS Information Bulletin NEET-PG 2025',
     'https://nbe.edu.in/IB/IB%20NEET-PG%202025.pdf', 2025, 'rules', 'nbems_information_bulletin'),
]
NBEMS_PAGE = 'https://natboard.edu.in/viewnbeexam?exam=neetpg'


def fetch(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def crawl() -> list[dict]:
    """Return every (title, year, url, page) row with a PDF link on the MCC pages."""
    rows, seen = [], set()
    for page in PAGES:
        s = fetch(page).decode('utf-8', 'ignore')
        for tr in re.findall(r'<tr.*?</tr>', s, re.S):
            links = re.findall(r'href="([^"]+\.pdf)"', tr, re.I)
            tds = [re.sub(r'\s+', ' ', html.unescape(re.sub('<[^>]+>', ' ', t))).strip()
                   for t in re.findall(r'<td.*?</td>', tr, re.S)]
            if links and tds and links[0] not in seen:
                seen.add(links[0])
                rows.append({'title': tds[0], 'pub_year': tds[1] if len(tds) > 1 else '', 'url': links[0], 'page': page})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--list', action='store_true')
    args = ap.parse_args()

    rows = crawl()
    print(f'Found {len(rows)} PDF links on {len(PAGES)} MCC pages')
    if args.list:
        for r in rows:
            print(f"{r['pub_year']} | {r['title']}")
        return 0

    plan, missing = [], []
    for pat, year, kind, name in DOCS:
        hits = [r for r in rows if re.search(pat, r['title'], re.I)]
        if isinstance(year, int):   # counselling for year Y is published in Y or Y+1
            hits = [r for r in hits if r['pub_year'] in (str(year), str(year + 1))]
        if not hits:
            missing.append(pat); continue
        for i, r in enumerate(hits):          # several links can share a title -> number them
            fname = f'{name}.pdf' if len(hits) == 1 else f'{name}_{i + 1}.pdf'
            plan.append((r, RAW / str(year) / kind / fname))
    for title, url, year, kind, name in FIXED:
        plan.append(({'title': title, 'pub_year': '', 'url': url, 'page': NBEMS_PAGE}, RAW / str(year) / kind / f'{name}.pdf'))

    done = {}
    if MANIFEST.exists():
        with MANIFEST.open() as fh:
            done = {d['path']: d for d in csv.DictReader(fh)}

    new_rows = []
    for r, path in plan:
        rel = str(path.relative_to(RAW))
        if path.exists() and rel in done:
            print(f'skip  {rel}'); continue
        if args.dry_run:
            print(f'would {rel}  <- {r["title"]}'); continue
        try:
            data = fetch(r['url'], timeout=180)
        except Exception as e:  # keep going; report at the end
            print(f'FAIL  {rel}: {e}'); missing.append(r['title']); continue
        if not data.startswith(b'%PDF'):
            print(f'FAIL  {rel}: not a PDF'); missing.append(r['title']); continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        new_rows.append({'path': rel, 'title': r['title'], 'pub_year': r['pub_year'], 'source_page': r['page'],
                         'url': r['url'], 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                         'downloaded_utc': datetime.now(timezone.utc).isoformat(timespec='seconds')})
        print(f'ok    {rel}  ({len(data) / 1e6:.1f} MB)')
        time.sleep(1)  # be polite to the server

    if new_rows:
        done.update({d['path']: d for d in new_rows})
        RAW.mkdir(parents=True, exist_ok=True)
        with MANIFEST.open('w', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=list(new_rows[0]))
            w.writeheader(); w.writerows(sorted(done.values(), key=lambda d: d['path']))
    if missing:
        print('\nNot found / failed:'); [print('  ', m) for m in missing]
    return 1 if missing else 0


if __name__ == '__main__':
    sys.exit(main())
