"""Data models for job agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any


class JobStatus(str, Enum):
    NEW = "NEW"
    SEEN = "SEEN"
    UPDATED = "UPDATED"
    CLOSED = "CLOSED"


class RemoteType(str, Enum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    UNKNOWN = "unknown"


@dataclass
class ScoreBreakdown:
    """Individual scoring components (0-100 each)."""

    technical_stack: float = 0.0
    production_ai: float = 0.0
    role_title: float = 0.0
    medical_cv: float = 0.0
    llm_genai: float = 0.0
    systems_infra: float = 0.0
    experience_level: float = 0.0
    compensation: float = 0.0

    WEIGHTS = {
        "technical_stack": 0.25,
        "production_ai": 0.20,
        "role_title": 0.15,
        "medical_cv": 0.10,
        "llm_genai": 0.10,
        "systems_infra": 0.10,
        "experience_level": 0.05,
        "compensation": 0.05,
    }

    @property
    def total(self) -> float:
        total = 0.0
        for key, weight in self.WEIGHTS.items():
            total += getattr(self, key) * weight
        return round(min(100.0, max(0.0, total)), 1)

    def to_dict(self) -> dict[str, float]:
        return {
            "technical_stack": self.technical_stack,
            "production_ai": self.production_ai,
            "role_title": self.role_title,
            "medical_cv": self.medical_cv,
            "llm_genai": self.llm_genai,
            "systems_infra": self.systems_infra,
            "experience_level": self.experience_level,
            "compensation": self.compensation,
            "total": self.total,
        }


@dataclass
class RawJob:
    """Job as fetched from a source before full processing."""

    company: str
    title: str
    url: str
    source: str
    source_job_id: str | None = None
    application_url: str | None = None
    location: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    remote_type: RemoteType = RemoteType.UNKNOWN
    description: str = ""
    requirements: str = ""
    salary_text: str | None = None
    date_posted: date | None = None
    employment_type: str | None = None
    company_priority: str = "D"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class JobRecord:
    """Fully processed job ready for storage/reporting."""

    company: str
    title: str
    url: str
    application_url: str
    source: str
    source_job_id: str | None = None
    location: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    remote_type: RemoteType = RemoteType.UNKNOWN
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str = "USD"
    salary_period: str = "yearly"
    compensation_unknown: bool = True
    date_posted: date | None = None
    description: str = ""
    requirements: str = ""
    match_score: float = 0.0
    score_breakdown: ScoreBreakdown = field(default_factory=ScoreBreakdown)
    why_match: str = ""
    missing_requirements: str = ""
    risk_flags: list[str] = field(default_factory=list)
    status: JobStatus = JobStatus.NEW
    content_hash: str = ""
    application_url_status: str = "unverified"
    company_priority: str = "D"
    employment_type: str | None = None
    search_priority_tier: int = 0
    search_priority_label: str = ""
    id: int | None = None
    date_first_seen: datetime | None = None
    date_last_seen: datetime | None = None

    def tier(self) -> str:
        if self.match_score >= 90:
            return "exceptional"
        if self.match_score >= 80:
            return "strong"
        if self.match_score >= 70:
            return "good"
        return "reject"


@dataclass
class SearchSummary:
    """Summary statistics from a search run."""

    companies_searched: int = 0
    companies_succeeded: int = 0
    companies_failed: int = 0
    jobs_collected: int = 0
    jobs_after_dedup: int = 0
    jobs_above_salary: int = 0
    jobs_score_qualifying: int = 0
    new_qualifying_jobs: int = 0
    excel_rows_appended: int = 0
    excel_path: str = ""
    failures: list[dict[str, str]] = field(default_factory=list)


@dataclass
class CompanyConfig:
    """Configuration for a target company."""

    name: str
    priority: str = "D"
    category: str = "other"
    ats: str = "company_page"
    board_token: str | None = None
    company_slug: str | None = None
    org_slug: str | None = None
    company_id: str | None = None
    careers_url: str | None = None
