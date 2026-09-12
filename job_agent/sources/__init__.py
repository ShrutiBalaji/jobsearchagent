"""Job source adapters."""

from job_agent.sources.ashby import AshbySource
from job_agent.sources.base import JobSource
from job_agent.sources.company_page import CompanyPageSource
from job_agent.sources.discovery import DiscoverySource
from job_agent.sources.greenhouse import GreenhouseSource
from job_agent.sources.lever import LeverSource
from job_agent.sources.smartrecruiters import SmartRecruitersSource
from job_agent.sources.workday import WorkdaySource

__all__ = [
    "JobSource",
    "GreenhouseSource",
    "LeverSource",
    "AshbySource",
    "WorkdaySource",
    "SmartRecruitersSource",
    "CompanyPageSource",
    "DiscoverySource",
]
