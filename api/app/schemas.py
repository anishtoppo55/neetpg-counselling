"""Request and response models (Pydantic v2). These define the OpenAPI contract at /docs."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CandidateCategory = Literal['GEN', 'GEN_PWD', 'OBC', 'OBC_PWD', 'SC', 'SC_PWD', 'ST', 'ST_PWD', 'EWS', 'EWS_PWD']
Status = Literal['safe', 'good', 'borderline', 'later_round', 'reach', 'unlikely']
# 'closing_rank' is kept as an alias of 'closing_rank_desc' so older links keep working.
Sort = Literal['desirability', 'chance', 'closing_rank_desc', 'closing_rank_asc', 'closing_rank',
               'branch_demand', 'college_demand', 'college', 'branch']
Group = Literal['Clinical', 'Para-clinical', 'Pre-clinical']
Degree = Literal['MD/MS', 'DNB', 'DNB Diploma', 'Diploma', 'M.Ch (6 yr)', 'MPH']


class ThresholdsIn(BaseModel):
    """Multiples of the candidate's rank. Status uses the first considered round's closing rank."""
    model_config = ConfigDict(extra='forbid')
    safe: float = Field(1.5, gt=0, le=20)
    good: float = Field(1.15, gt=0, le=20)
    borderline: float = Field(0.95, gt=0, le=20)
    reach: float = Field(0.75, gt=0, le=20)

    @model_validator(mode='after')
    def ordered(self):
        if not (self.safe > self.good > self.borderline > self.reach):
            raise ValueError('thresholds must satisfy safe > good > borderline > reach')
        return self


class PredictRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', json_schema_extra={'examples': [{
        'rank': 30000, 'category': 'ST', 'quota': 'AI', 'year': 2025,
        'groups': ['Clinical'], 'degrees': ['MD/MS']}]})

    rank: int = Field(..., ge=1, le=1_000_000, description='NEET PG All India Rank')
    category: CandidateCategory = Field(..., description='Candidate category (PwD variants included)')
    quota: str = Field('AI', description='MCC quota code; see GET /api/meta for supported quotas')
    year: int | None = Field(None, description='Counselling year of the historical data (default: latest loaded)')
    rounds: list[str] | None = Field(None, description='Round codes to consider, e.g. ["R1","R2","R3"] '
                                                       '(default: regular rounds). Status is based on the first.')
    branches: list[str] | None = None
    states: list[str] | None = None
    groups: list[Group] | None = None
    degrees: list[Degree] | None = None
    statuses: list[Status] | None = Field(None, description='Default: safe, good, borderline, later_round, reach')
    thresholds: ThresholdsIn = Field(default_factory=ThresholdsIn)
    branch_weight: float = Field(0.6, ge=0, le=1, description='Weight of branch demand vs institute demand')
    sort: Sort = Field('desirability', description='Order of the returned options; see GET /api/meta for labels')
    limit: int = Field(500, ge=1, le=5000)
    offset: int = Field(0, ge=0)


class InstituteOut(BaseModel):
    id: int
    name: str
    short_name: str
    state: str | None
    mcc_code: str | None = None


class CourseOut(BaseModel):
    id: int
    code: str
    name: str
    branch: str
    group: str
    degree: str


class CategoryCutoff(BaseModel):
    seats: int
    opening_rank: int
    closing_rank: int


class RoundCutoffOut(BaseModel):
    round: str
    round_name: str
    best_close: int | None = Field(None, description='Worst rank allotted on any eligible seat category')
    best_category: str | None = None
    by_category: dict[str, CategoryCutoff] = {}


class OptionOut(BaseModel):
    institute: InstituteOut
    course: CourseOut
    status: Status
    status_label: str
    desirability: float
    ratio_first_round: float | None = Field(None, description='First-round best closing rank / your rank')
    best_close_later_rounds: int | None
    rounds: list[RoundCutoffOut]
    institute_median_air: float | None = None
    branch_median_air: float | None = None
    reason: str


class EligibilityOut(BaseModel):
    seat_categories: list[str]
    confirmed: bool
    source: str | None
    clauses: list[str]


class PredictResponse(BaseModel):
    year: int
    quota: str
    quota_name: str
    category: str
    rank: int
    rounds: list[dict]
    eligibility: EligibilityOut
    thresholds: ThresholdsIn
    sort: str = Field(description='Order actually applied to `options`')
    summary: dict = Field(description='Counts after branch/state/group/degree filters: by status, and by branch × status')
    total: int = Field(description='Options matching all filters including statuses (before limit/offset)')
    options: list[OptionOut]
    notices: list[str]
