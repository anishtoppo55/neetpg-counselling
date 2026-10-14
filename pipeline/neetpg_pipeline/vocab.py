"""Normalisation of quotas, categories, courses, institutes and states."""
from __future__ import annotations

import re
from functools import lru_cache

import yaml

from . import settings


def key(s: str) -> str:
    """Upper-case alphanumerics only – identical for names printed with different spacing/punctuation."""
    return re.sub(r'[^A-Z0-9]', '', str(s).upper().replace('&', 'AND'))


def clean(s: str) -> str:
    s = re.sub(r'\s+', ' ', str(s)).strip()
    return s.replace('- ', '-').replace(' ,', ',')


def blank(s) -> bool:
    return s is None or str(s).strip() in ('', '-')


# ---------------------------------------------------------------- quotas
QUOTA_NAMES = {
    'AI': ['All India'],
    'AD': ['DNB Quota'],
    'PS': ['Self-Financed Merit Seat', 'Management/Paid Seats Quota', 'Self-Financed Merit Seat/(Paid Seat Quota)'],
    'NR': ['Non-Resident Indian'],
    'DU': ['Delhi University Quota'],
    'IP': ['IP University Quota'],
    'AM': ['Aligarh Muslim University'],
    'BH': ['Banaras Hindu University'],
    'JM': ['Jain Minority Quota'],
    'MM': ['Muslim Minority Quota'],
    'AF': ['Armed Forces Medical'],
}
_QUOTA_BY_KEY = {key(n): c for c, names in QUOTA_NAMES.items() for n in names} | {c: c for c in QUOTA_NAMES}


def quota_code(s: str) -> str | None:
    if blank(s):
        return None
    return _QUOTA_BY_KEY.get(key(s))


# ---------------------------------------------------------------- categories
SEAT_CATEGORIES = {
    'Open': 'OPEN', 'Open PwD': 'OPEN_PWD', 'OBC': 'OBC', 'OBC PwD': 'OBC_PWD', 'SC': 'SC', 'SC PwD': 'SC_PWD',
    'ST': 'ST', 'ST PwD': 'ST_PWD', 'EWS': 'EWS', 'EWS PwD': 'EWS_PWD',
    # legend abbreviations (seat matrices)
    'GN': 'OPEN', 'GN PwD': 'OPEN_PWD', 'BC': 'OBC', 'BC PwD': 'OBC_PWD', 'EW': 'EWS', 'EW PwD': 'EWS_PWD',
    'OP': 'OPEN', 'OP PwD': 'OPEN_PWD',
}
CANDIDATE_CATEGORIES = {
    'General': 'GEN', 'General PwD': 'GEN_PWD', 'GNYes': 'GEN_PWD', 'OBC': 'OBC', 'OBC PwD': 'OBC_PWD',
    'SC': 'SC', 'SC PwD': 'SC_PWD', 'ST': 'ST', 'ST PwD': 'ST_PWD', 'EWS': 'EWS', 'EWS PwD': 'EWS_PWD',
}


def seat_category(s: str) -> str | None:
    return None if blank(s) else SEAT_CATEGORIES.get(clean(s))


def candidate_category(s: str) -> str | None:
    return None if blank(s) else CANDIDATE_CATEGORIES.get(clean(s))


# ---------------------------------------------------------------- courses
BRANCH_RULES = [  # (regex on upper-case course name, branch) – first match wins
    (r'RADIO-?\s?DIAGNOSIS', 'Radiology'), (r'DERM', 'Dermatology'), (r'PAEDIATRIC SURGERY', 'Paediatric Surgery'),
    (r'PAEDIATRICS|CHILD HEALTH', 'Paediatrics'), (r'ORTHO', 'Orthopaedics'), (r'GENERAL SURGERY', 'General Surgery'),
    (r'TRAUMATOLOGY', 'Traumatology & Surgery'), (r'GENERAL MEDICINE', 'General Medicine'),
    (r'OBST|GYNAE', 'Obstetrics & Gynaecology'), (r'OPHTHAL|DOMS', 'Ophthalmology'), (r'E\.N\.T|OTO-?RHINO', 'ENT'),
    (r'PSYCH', 'Psychiatry'), (r'ANAESTH', 'Anaesthesiology'),
    (r'RESPIRATORY|TUBERCULOSIS|T\.B\.|PULMONARY', 'Respiratory Medicine'), (r'EMERGENCY', 'Emergency Medicine'),
    (r'RADIATION|RADIOTHERAPY|RADIO-THERAPY', 'Radiation Oncology'), (r'NUCLEAR', 'Nuclear Medicine'),
    (r'PHY(SICAL)?\.? MED', 'Physical Medicine & Rehab'), (r'FAMILY', 'Family Medicine'), (r'GERIATRIC', 'Geriatrics'),
    (r'PALLIATIVE', 'Palliative Medicine'), (r'SPORTS', 'Sports Medicine'), (r'TROPICAL', 'Tropical Medicine'),
    (r'DIABETOLOGY', 'Diabetology'), (r'NEURO SURGERY', 'Neurosurgery'), (r'CARDIO', 'CTVS'),
    (r'PLASTIC', 'Plastic Surgery'), (r'AEROSPACE', 'Aerospace Medicine'),
    (r'TRANSFUSION|IMMUNO-?HAEMATOLOGY', 'Transfusion Medicine'), (r'LABORATORY', 'Laboratory Medicine'),
    (r'PATHOLOGY', 'Pathology'), (r'MICROBIO|BACTERIO', 'Microbiology'), (r'PHARMACOLOGY', 'Pharmacology'),
    (r'FORENSIC', 'Forensic Medicine'),
    (r'HOSPITAL ADMIN|HEALTH ADMIN|COMMUNITY HEALTH AND ADMN', 'Hospital Administration'),
    (r'PREVENTIVE|COMMUNITY|PUBLIC HEALTH|EPIDEMIOLOGY', 'Community Medicine'), (r'BIOCHEM', 'Biochemistry'),
    (r'PHYSIOLOGY', 'Physiology'), (r'ANATOMY', 'Anatomy'),
]
PRE_CLINICAL = {'Anatomy', 'Physiology', 'Biochemistry'}
PARA_CLINICAL = {'Pathology', 'Microbiology', 'Pharmacology', 'Forensic Medicine', 'Community Medicine',
                 'Transfusion Medicine', 'Laboratory Medicine', 'Hospital Administration'}


def branch_of(course_name: str) -> str:
    u = course_name.upper()
    return next((b for pat, b in BRANCH_RULES if re.search(pat, u)), 'Other')


def group_of(branch: str) -> str:
    return 'Pre-clinical' if branch in PRE_CLINICAL else 'Para-clinical' if branch in PARA_CLINICAL else 'Clinical'


def degree_of(course_name: str) -> str:
    u = course_name.upper()
    if u.startswith('(NBEMS-DIPLOMA)'): return 'DNB Diploma'
    if u.startswith('(NBEMS)'): return 'DNB'
    if u.startswith(('DIP', 'PG DIPLOMA')): return 'Diploma'
    if u.startswith('M.CH'): return 'M.Ch (6 yr)'
    if u.startswith('M.P.H'): return 'MPH'
    return 'MD/MS'


def parse_course_legend(text: str) -> dict[str, str]:
    """'Program Abbrevations' section of an MCC result PDF (layout text) -> {code: name}."""
    out, last, on = {}, None, False
    for line in text.splitlines():
        s = line.strip()
        if 'Program Abbrevations' in s:
            on = True; continue
        if not on or not s or s.startswith('Abbrevation'):
            continue
        if s.startswith('Note*'):
            break
        if 'Page No.' in s:
            last = None; continue
        m = re.match(r'^(\S{3,6})\s{2,}(.+)$', s)
        if m:
            last = m[1]; out[last] = m[2].strip()
        elif last:
            out[last] += ' ' + s
    return {c: clean(n) for c, n in out.items()}


@lru_cache(maxsize=1)
def course_catalog() -> dict[str, dict]:
    """config/courses.yaml -> {course key: {code, name, branch, branch_group, degree}} incl. aliases."""
    with open(settings.CONFIG_DIR / 'courses.yaml') as fh:
        data = yaml.safe_load(fh)
    out = {}
    for c in data['courses']:
        for n in [c['name']] + c.get('aliases', []):
            out[key(n)] = c
        out[key(c['code'])] = c
    return out


def course(s: str) -> dict | None:
    """Look up a printed course name (or code); also accepts a trailing '(CODE)' as in DNB seat matrices."""
    if blank(s):
        return None
    cat = course_catalog()
    k = key(s)
    if k in cat:
        return cat[k]
    m = re.search(r'\(([A-Z][A-Z0-9-]{2,5})\)\s*$', clean(s))
    if m and key(m[1]) in cat:
        return cat[key(m[1])]
    return None


# ---------------------------------------------------------------- institutes & states
STATES = {
    'Andhra Pradesh': 'Andhra Pradesh', 'Arunachal Pradesh': 'Arunachal Pradesh', 'Assam': 'Assam', 'Bihar': 'Bihar',
    'Chhattisgarh': 'Chhattisgarh', 'Goa': 'Goa', 'Gujarat': 'Gujarat', 'Haryana': 'Haryana',
    'Himachal Pradesh': 'Himachal Pradesh', 'Jharkhand': 'Jharkhand', 'Karnataka': 'Karnataka', 'Kerala': 'Kerala',
    'Madhya Pradesh': 'Madhya Pradesh', 'Maharashtra': 'Maharashtra', 'Manipur': 'Manipur', 'Meghalaya': 'Meghalaya',
    'Mizoram': 'Mizoram', 'Nagaland': 'Nagaland', 'Odisha': 'Odisha', 'Orissa': 'Odisha', 'Punjab': 'Punjab',
    'Rajasthan': 'Rajasthan', 'Sikkim': 'Sikkim', 'Tamil Nadu': 'Tamil Nadu', 'Telangana': 'Telangana',
    'Tripura': 'Tripura', 'Uttar Pradesh': 'Uttar Pradesh', r'U\.P\.': 'Uttar Pradesh', 'Uttarakhand': 'Uttarakhand',
    'West Bengal': 'West Bengal', 'Andaman': 'Andaman & Nicobar', 'Chandigarh': 'Chandigarh',
    'Dadra': 'DNH & Daman Diu', 'Daman': 'DNH & Daman Diu', 'Delhi': 'Delhi', 'Jammu': 'Jammu & Kashmir',
    'Kashmir': 'Jammu & Kashmir', 'Ladakh': 'Ladakh', 'Puducherry': 'Puducherry', 'Pondicherry': 'Puducherry',
    'Lakshadweep': 'Lakshadweep',
}
_STATE_RE = re.compile(r'\b(' + '|'.join(STATES) + r')\b', re.I)
_STATE_LOOKUP = {k.replace('\\', '').lower(): v for k, v in STATES.items()}


def state_of(institute: str) -> str | None:
    hits = _STATE_RE.findall(str(institute))
    return _STATE_LOOKUP.get(hits[-1].lower()) if hits else None   # last mention = address


def short_name(inst: str) -> str:
    """Readable college name with city, e.g. 'Government Medical College, Theni'."""
    s = re.sub(r'\s*,\s*,', ',', str(inst))
    m = re.match(r'^(.+?),(?=\S)(.*)$', s)
    if m and len(m[1]) >= 8:
        name, rest = m[1].strip(' ,'), m[2]
        nxt = rest.split(',')[0].strip()
        if (',' not in name and nxt and not nxt[0].isdigit() and len(nxt) <= 25
                and key(nxt) not in key(name) and key(name) not in key(nxt)):
            name = f'{name}, {nxt}'
        return name[:80]
    parts = [p.strip() for p in s.split(',') if p.strip()]
    name = parts[0] if parts else s
    return (f'{parts[0]}, {parts[1]}' if len(name) < 12 and len(parts) > 1 else name)[:80]
