"""Base class for job sources."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from job_agent.config import AppConfig
from job_agent.models import CompanyConfig, RawJob
from job_agent.utils.http import HttpClient

logger = logging.getLogger("job_agent.sources")


class JobSource(ABC):
    """Abstract job source adapter."""

    source_name: str = "base"

    def __init__(self, http: HttpClient, config: AppConfig) -> None:
        self.http = http
        self.config = config

    @abstractmethod
    def fetch_jobs(self, company: CompanyConfig) -> list[RawJob]:
        """Fetch jobs for a company."""

    def safe_fetch(self, company: CompanyConfig) -> tuple[list[RawJob], str | None]:
        """Fetch with error isolation."""
        try:
            jobs = self.fetch_jobs(company)
            logger.info(
                "Fetched %d jobs from %s (%s)", len(jobs), company.name, self.source_name
            )
            return jobs, None
        except Exception as exc:
            msg = f"{type(exc).__name__}: {exc}"
            logger.warning("Failed to fetch %s via %s: %s", company.name, self.source_name, msg)
            return [], msg


def get_source_for_company(
    company: CompanyConfig, http: HttpClient, config: AppConfig
) -> JobSource:
    """Factory to get appropriate source adapter."""
    from job_agent.sources.ashby import AshbySource
    from job_agent.sources.company_page import CompanyPageSource
    from job_agent.sources.greenhouse import GreenhouseSource
    from job_agent.sources.lever import LeverSource
    from job_agent.sources.smartrecruiters import SmartRecruitersSource
    from job_agent.sources.workable import WorkableSource
    from job_agent.sources.workday import WorkdaySource

    mapping = {
        "greenhouse": GreenhouseSource,
        "lever": LeverSource,
        "ashby": AshbySource,
        "workday": WorkdaySource,
        "smartrecruiters": SmartRecruitersSource,
        "workable": WorkableSource,
        "company_page": CompanyPageSource,
    }
    cls = mapping.get(company.ats, CompanyPageSource)
    return cls(http, config)
