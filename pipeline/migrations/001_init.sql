-- 001_init.sql – core schema for the NEET PG counselling platform.
-- Every fact is scoped to a counselling year through `round` or a direct `year` column, so new years can be
-- added by importing more data – no schema change needed.

-- ---------------------------------------------------------------- provenance
CREATE TABLE counselling_year (
    year        integer PRIMARY KEY CHECK (year BETWEEN 2015 AND 2100),
    label       text NOT NULL,                 -- e.g. 'NEET PG 2024'
    notes       text
);

CREATE TABLE source_document (
    id          serial PRIMARY KEY,
    year        integer REFERENCES counselling_year(year),   -- NULL = applies to several years
    path        text NOT NULL UNIQUE,          -- relative to data/raw, e.g. '2024/allotments/round1.pdf'
    kind        text NOT NULL,                 -- allotments | seat_matrix | rules | notices | admitted
    title       text,
    url         text,
    sha256      char(64) NOT NULL,
    pages       integer
);

CREATE TABLE import_run (
    id          serial PRIMARY KEY,
    year        integer NOT NULL REFERENCES counselling_year(year),
    started_at  timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    status      text NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'succeeded', 'failed')),
    report      jsonb                          -- validation results and counts
);

-- ---------------------------------------------------------------- reference data
CREATE TABLE round (
    id          serial PRIMARY KEY,
    year        integer NOT NULL REFERENCES counselling_year(year) ON DELETE CASCADE,
    code        text NOT NULL,                 -- R1, R2, R3, STRAY, SPECIAL_STRAY ...
    seq         integer NOT NULL,              -- order within the year
    name        text NOT NULL,
    kind        text NOT NULL CHECK (kind IN ('regular', 'stray')),
    UNIQUE (year, code),
    UNIQUE (year, seq)
);

CREATE TABLE quota (
    code        text PRIMARY KEY,              -- MCC abbreviation: AI, AD, PS, NR, DU, IP, AM, BH, JM, MM, AF
    name        text NOT NULL
);

CREATE TABLE seat_category (                   -- category of the seat (column "Allotted Category")
    code        text PRIMARY KEY,              -- OPEN, OPEN_PWD, OBC, OBC_PWD, SC, SC_PWD, ST, ST_PWD, EWS, EWS_PWD
    base        text NOT NULL,                 -- OPEN | OBC | SC | ST | EWS
    is_pwd      boolean NOT NULL,
    name        text NOT NULL
);

CREATE TABLE candidate_category (              -- category of the candidate (column "Candidate Category")
    code        text PRIMARY KEY,              -- GEN, GEN_PWD, OBC, OBC_PWD, SC, SC_PWD, ST, ST_PWD, EWS, EWS_PWD
    base        text NOT NULL,                 -- GEN | OBC | SC | ST | EWS
    is_pwd      boolean NOT NULL,
    name        text NOT NULL
);

CREATE TABLE institute (
    id          serial PRIMARY KEY,
    key         text NOT NULL UNIQUE,          -- upper-case alphanumerics of the full printed name
    name        text NOT NULL,                 -- full name as printed (latest year wins)
    short_name  text NOT NULL,
    state       text,
    mcc_code    text,                          -- 6-digit code from the seat matrix, when matched
    last_year   integer NOT NULL               -- latest counselling year the name was printed in
);

CREATE TABLE course (
    id          serial PRIMARY KEY,
    code        text NOT NULL UNIQUE,          -- MCC programme code, e.g. GMED, RADD, DMED (config/courses.yaml)
    name        text NOT NULL,
    branch      text NOT NULL,                 -- e.g. 'General Medicine'
    branch_group text NOT NULL CHECK (branch_group IN ('Clinical', 'Para-clinical', 'Pre-clinical')),
    degree      text NOT NULL                  -- MD/MS, DNB, DNB Diploma, Diploma, M.Ch (6 yr), MPH
);

-- ---------------------------------------------------------------- facts
-- One row per candidate rank appearing in a round's own result PDF (allotted or not).
CREATE TABLE round_result (
    round_id    integer NOT NULL REFERENCES round(id) ON DELETE CASCADE,
    rank        integer NOT NULL CHECK (rank > 0),
    allotted    boolean NOT NULL,
    remarks     text,                          -- 'Fresh Allotted in 2nd Round', 'No Upgradation', 'Not Allotted.' ...
    source_document_id integer NOT NULL REFERENCES source_document(id),
    source_page integer NOT NULL,
    PRIMARY KEY (round_id, rank)
);

-- The seat allotted to a candidate in a round (subset of round_result with allotted = true).
CREATE TABLE allotment (
    round_id    integer NOT NULL,
    rank        integer NOT NULL,
    quota_code  text NOT NULL REFERENCES quota(code),
    institute_id integer NOT NULL REFERENCES institute(id),
    course_id   integer NOT NULL REFERENCES course(id),
    seat_category_code text NOT NULL REFERENCES seat_category(code),
    candidate_category_code text REFERENCES candidate_category(code),
    option_no   integer,
    PRIMARY KEY (round_id, rank),
    FOREIGN KEY (round_id, rank) REFERENCES round_result(round_id, rank) ON DELETE CASCADE
);
CREATE INDEX allotment_lookup ON allotment (quota_code, seat_category_code, institute_id, course_id);
CREATE INDEX allotment_rank ON allotment (rank);

-- Joining status of a round's seat, as printed in the NEXT round's PDF (Reported, Not Reported, Seat Surrendered ...).
CREATE TABLE reporting_status (
    round_id    integer NOT NULL,
    rank        integer NOT NULL,
    status      text NOT NULL,
    source_document_id integer NOT NULL REFERENCES source_document(id),
    PRIMARY KEY (round_id, rank),
    FOREIGN KEY (round_id, rank) REFERENCES allotment(round_id, rank) ON DELETE CASCADE
);

-- Seats offered at the start of a round (Round-1 seat matrices in Milestone 1).
CREATE TABLE seat_matrix (
    id          bigserial PRIMARY KEY,
    round_id    integer NOT NULL REFERENCES round(id) ON DELETE CASCADE,
    matrix      text NOT NULL,                 -- aiq | central_internal | deemed | dnb
    institute_name text NOT NULL,              -- as printed in the seat matrix
    mcc_code    text,
    institute_id integer REFERENCES institute(id),   -- NULL when not matched to an allotment institute
    course_name text NOT NULL,
    course_id   integer REFERENCES course(id),
    quota_code  text NOT NULL REFERENCES quota(code),
    seat_category_code text REFERENCES seat_category(code),   -- NULL = total only (deemed matrix)
    seats       integer NOT NULL CHECK (seats >= 0),
    source_document_id integer NOT NULL REFERENCES source_document(id),
    source_page integer NOT NULL
);
CREATE INDEX seat_matrix_lookup ON seat_matrix (round_id, institute_id, course_id);

-- ---------------------------------------------------------------- rules
-- Which seat categories a candidate category may be allotted, per year, with the source clause.
CREATE TABLE category_eligibility (
    year        integer NOT NULL REFERENCES counselling_year(year) ON DELETE CASCADE,
    candidate_category_code text NOT NULL REFERENCES candidate_category(code),
    seat_category_code text NOT NULL REFERENCES seat_category(code),
    source_document_id integer REFERENCES source_document(id),
    source_clause text NOT NULL,               -- section / page reference in the source document
    confirmed   boolean NOT NULL DEFAULT false,   -- reviewed by a person
    notes       text,
    PRIMARY KEY (year, candidate_category_code, seat_category_code)
);

-- ---------------------------------------------------------------- derived
-- Opening / closing rank per seat group and round, rebuilt after each import.
CREATE MATERIALIZED VIEW cutoff AS
SELECT r.year, a.round_id, r.code AS round_code, r.seq AS round_seq,
       a.quota_code, a.institute_id, a.course_id, a.seat_category_code,
       count(*)    AS seats_allotted,
       min(a.rank) AS opening_rank,
       max(a.rank) AS closing_rank
FROM allotment a JOIN round r ON r.id = a.round_id
GROUP BY r.year, a.round_id, r.code, r.seq, a.quota_code, a.institute_id, a.course_id, a.seat_category_code;
CREATE UNIQUE INDEX cutoff_pk ON cutoff (round_id, quota_code, institute_id, course_id, seat_category_code);
CREATE INDEX cutoff_search ON cutoff (year, quota_code, seat_category_code, closing_rank);

-- ---------------------------------------------------------------- vocabularies
INSERT INTO quota (code, name) VALUES
 ('AI', 'All India'), ('AD', 'DNB Quota'), ('PS', 'Self-Financed Merit Seat / Management-Paid Seats Quota'),
 ('NR', 'Non-Resident Indian'), ('DU', 'Delhi University Quota'), ('IP', 'IP University Quota'),
 ('AM', 'Aligarh Muslim University'), ('BH', 'Banaras Hindu University'), ('JM', 'Jain Minority Quota'),
 ('MM', 'Muslim Minority Quota'), ('AF', 'Armed Forces Medical');

INSERT INTO seat_category (code, base, is_pwd, name) VALUES
 ('OPEN', 'OPEN', false, 'Open Seat'), ('OPEN_PWD', 'OPEN', true, 'Open Seat (PwD)'),
 ('OBC', 'OBC', false, 'OBC-NCL'),     ('OBC_PWD', 'OBC', true, 'OBC-NCL (PwD)'),
 ('SC', 'SC', false, 'Scheduled Caste'), ('SC_PWD', 'SC', true, 'Scheduled Caste (PwD)'),
 ('ST', 'ST', false, 'Scheduled Tribe'), ('ST_PWD', 'ST', true, 'Scheduled Tribe (PwD)'),
 ('EWS', 'EWS', false, 'General-EWS'),  ('EWS_PWD', 'EWS', true, 'General-EWS (PwD)');

INSERT INTO candidate_category (code, base, is_pwd, name) VALUES
 ('GEN', 'GEN', false, 'General'), ('GEN_PWD', 'GEN', true, 'General (PwD)'),
 ('OBC', 'OBC', false, 'OBC-NCL'), ('OBC_PWD', 'OBC', true, 'OBC-NCL (PwD)'),
 ('SC', 'SC', false, 'Scheduled Caste'), ('SC_PWD', 'SC', true, 'Scheduled Caste (PwD)'),
 ('ST', 'ST', false, 'Scheduled Tribe'), ('ST_PWD', 'ST', true, 'Scheduled Tribe (PwD)'),
 ('EWS', 'EWS', false, 'General-EWS'), ('EWS_PWD', 'EWS', true, 'General-EWS (PwD)');
