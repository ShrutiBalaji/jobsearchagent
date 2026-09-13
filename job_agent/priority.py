"""Job search priority tiers and filtering."""

from __future__ import annotations

from job_agent.config import AppConfig
from job_agent.models import JobRecord, RemoteType
from job_agent.normalization import is_excluded_role, is_usa_job_eligible
from job_agent.scoring import (
    _extract_max_years_requirement,
    _extract_years_requirement,
    _is_high_seniority_title,
)

TIER_LABELS = {
    1: "Tier 1: Target company · junior / ≤3 yrs",
    2: "Tier 2: US market · ≤3 yrs",
    3: "Tier 3: US market · ≤5 yrs",
}

JUNIOR_ROLE_MARKERS = (
    "junior",
    "entry level",
    "entry-level",
    "early career",
    "new grad",
    "new graduate",
    "recent graduate",
    "associate data",
    "associate ml",
    "associate ai",
    "associate scientist",
    "associate engineer",
)


def configured_company_names(cfg: AppConfig) -> set[str]:
    return {company.name.lower() for company in cfg.companies}


def job_text(job: JobRecord) -> str:
    return f"{job.title} {job.description} {job.requirements}"


def is_target_role(title: str, cfg: AppConfig) -> bool:
    """True for AI engineering, data science, ML, and closely related roles."""
    title_lower = title.lower()
    for role in cfg.target_roles:
        role_lower = role.lower()
        if role_lower in title_lower or title_lower in role_lower:
            return True
    return any(kw.lower() in title_lower for kw in cfg.role_keywords)


def is_junior_role(title: str, description: str = "") -> bool:
    text = f"{title} {description}".lower()
    return any(marker in text for marker in JUNIOR_ROLE_MARKERS)


def is_senior_over_experience_limit(title: str, text: str, cfg: AppConfig) -> bool:
    """Exclude senior/staff roles that require more than the allowed maximum years."""
    max_years = _extract_max_years_requirement(text)
    if max_years is not None and max_years > cfg.max_allowed_job_years:
        return True
    if _is_high_seniority_title(title):
        return True
    title_lower = title.lower()
    is_senior = any(term in title_lower for term in cfg.senior_indicators)
    if is_senior and max_years is not None and max_years >= cfg.max_allowed_job_years:
        return True
    return False


def compute_priority_tier(job: JobRecord, cfg: AppConfig) -> int:
    """Return priority tier (1 best, 3 broadest) or 0 if the job should be excluded."""
    text = job_text(job)
    title = job.title

    if is_excluded_role(title, job.description, cfg):
        return 0
    if not is_target_role(title, cfg):
        return 0

    remote_type = job.remote_type
    if isinstance(remote_type, str):
        remote_type = RemoteType(remote_type)
    if not is_usa_job_eligible(job.location, remote_type, job.description, title):
        return 0
    if is_senior_over_experience_limit(title, text, cfg):
        return 0

    max_years = _extract_max_years_requirement(text)
    if max_years is not None and max_years > cfg.max_allowed_job_years:
        return 0

    in_target_company = job.company.lower() in configured_company_names(cfg)
    junior = is_junior_role(title, job.description)
    years_unlisted = max_years is None

    if in_target_company and (years_unlisted or junior or (max_years is not None and max_years <= cfg.tier1_max_years)):
        return 1

    if years_unlisted or (max_years is not None and max_years <= cfg.tier2_max_years):
        return 2

    if max_years is not None and max_years <= cfg.tier3_max_years:
        return 3

    return 0


def enrich_job_priority(job: JobRecord, cfg: AppConfig) -> JobRecord:
    tier = compute_priority_tier(job, cfg)
    job.search_priority_tier = tier
    job.search_priority_label = TIER_LABELS.get(tier, "")
    return job


def filter_and_rank_jobs(jobs: list[JobRecord], cfg: AppConfig) -> list[JobRecord]:
    """Keep eligible jobs, assign priority tiers, and sort best-first."""
    from job_agent.scoring import sort_jobs

    kept: list[JobRecord] = []
    for job in jobs:
        enrich_job_priority(job, cfg)
        if job.search_priority_tier > 0:
            kept.append(job)
    return sort_jobs(kept, cfg)
