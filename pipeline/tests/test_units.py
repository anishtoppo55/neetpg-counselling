"""Unit tests for normalisation and parsing helpers (no PDFs, no database)."""
import pytest

from neetpg_pipeline import seatmatrix, tables, vocab
from neetpg_pipeline.pdfwords import Word


@pytest.mark.parametrize('printed,code', [
    ('All India', 'AI'), ('DNB Quota', 'AD'), ('Self- Financed Merit Seat', 'PS'),
    ('Management/ Paid Seats Quota', 'PS'), ('Manageme nt/Paid Seats Quota', 'PS'),
    ('Self-Financed Merit Seat/(Paid Seat Quota)', 'PS'), ('Non- Resident Indian', 'NR'), ('AF', 'AF'), ('-', None),
])
def test_quota_codes(printed, code):
    assert vocab.quota_code(printed) == code


def test_unknown_quota_is_none():
    assert vocab.quota_code('Some New Quota') is None


@pytest.mark.parametrize('printed,code', [('Open', 'OPEN'), ('Open PwD', 'OPEN_PWD'), ('ST', 'ST'), ('EWS PwD', 'EWS_PWD')])
def test_seat_categories(printed, code):
    assert vocab.seat_category(printed) == code


@pytest.mark.parametrize('printed,code', [('General', 'GEN'), ('GNYes', 'GEN_PWD'), ('General PwD', 'GEN_PWD'),
                                          ('ST PwD', 'ST_PWD'), ('-', None)])
def test_candidate_categories(printed, code):
    assert vocab.candidate_category(printed) == code


@pytest.mark.parametrize('printed,code,branch', [
    ('M.D. (GENERAL MEDICINE)', 'GMED', 'General Medicine'),
    ('M.D. (RADIO- DIAGNOSIS)', 'RADD', 'Radiology'),                         # word broken across lines
    ('(NBEMS) ANAESTHESIOLOG Y', 'DANS', 'Anaesthesiology'),
    ('(NBEMS) GENERAL MEDICINE (DMED)', 'DMED', 'General Medicine'),          # DNB seat-matrix style suffix
    ('M.D. (Obst. and Gynae)/MS (Obstetrics and Gynaecology)', 'OBGY', 'Obstetrics & Gynaecology'),
])
def test_course_lookup(printed, code, branch):
    c = vocab.course(printed)
    assert c['code'] == code and c['branch'] == branch


def test_course_catalogue_is_complete():
    cat = {c['code']: c for c in vocab.course_catalog().values()}
    assert len(cat) == 100
    assert all(c['branch'] != 'Other' for c in cat.values())
    assert {c['branch_group'] for c in cat.values()} == {'Clinical', 'Para-clinical', 'Pre-clinical'}


def test_state_and_short_name():
    name = 'GOVT. MEDICAL COLLEGE, THIRUVANANTHAPURAM,GOVT. MEDICAL COLLEGE, THIRUVANANTHAPURAM, Kerala, 695011'
    assert vocab.state_of(name) == 'Kerala'
    assert vocab.short_name(name) == 'GOVT. MEDICAL COLLEGE, THIRUVANANTHAPURAM'
    assert vocab.state_of('GOVERNMENT MEDICAL COLLEGE, AZAMGARH,Chakrapanpur, Azamgarh (U.P.), Uttar Pradesh, 276128') == 'Uttar Pradesh'


def _w(x0, y0, text, width=20):
    return Word(x0, y0, x0 + width, y0 + 8, text)


def test_parse_table_wrapped_rows_and_footer():
    layout = {'anchor': [0, 40], 'columns': [['rank', 0], ['cur_quota', 40], ['cur_institute', 100], ['cur_allotted_cat', 300]]}
    page = [
        _w(5, 10, 'Rank'),                                            # header
        _w(5, 30, '7'), _w(45, 30, 'All'), _w(70, 30, 'India'), _w(105, 30, 'Some'), _w(130, 30, 'College,'), _w(305, 30, 'Open'),
        _w(105, 39, 'Delhi'),                                         # wrapped institute line
        _w(5, 52, '9'), _w(45, 52, 'DNB'), _w(105, 52, 'Other'), _w(305, 52, 'ST'),
        _w(200, 800, 'Page'), _w(225, 800, 'No.'), _w(250, 800, '4'),  # footer
    ]
    df, st = tables.parse_table([page], layout)
    assert st.orphan_words == 0 and st.straddling_words == 0
    assert df['rank'].tolist() == ['7', '9']
    assert df.loc[0, 'cur_institute'] == 'Some College, Delhi'
    assert df.loc[1, 'cur_allotted_cat'] == 'ST'


def test_split_lines_keeps_centred_blocks_together():
    # a 3-line cell centred on anchor 100 followed by a 1-line cell on anchor 115
    assert seatmatrix._split_lines([90, 100, 110, 115], [100, 115]) == [0, 0, 0, 1]
    ys = [119.3 + 20 * i for i in range(24)]
    assert seatmatrix._split_lines(ys, [y + 0.01 for y in ys]) == list(range(24))
