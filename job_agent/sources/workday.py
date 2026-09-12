"""Workday career site job source (limited public API support)."""

from __future__ import annotations

import json
import logging
import re

from job_agent.models import CompanyConfig, RawJob
from job_agent.sources.base import JobSource
from job_agent.utils.dates import parse_date

logger = logging.getLogger("job_agent.sources.workday")

AI_KEYWORDS = re.compile(
    r"\b(ai|ml|machine learning|artificial intelligence|computer vision|"
    r"deep learning|llm|genai|inference|ml engineer|ai engineer)\b",
    re.I,
)


class WorkdaySource(JobSource):
    source_name = "workday"

    def fetch_jobs(self, company: CompanyConfig) -> list[RawJob]:
        careers_url = company.careers_url
        if not careers_url:
            raise ValueError(f"No careers_url for Workday company {company.name}")

        # Attempt Workday CXS API pattern
        # e.g. https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite/jobs
        parsed_match = re.search(
            r"(https://([^.]+)\.(wd\d+)\.myworkdayjobs\.com)/([^/?#]+)",
            careers_url,
            re.I,
        )

        if not parsed_match:
            # Fall back to company page scraping
            from job_agent.sources.company_page import CompanyPageSource

            return CompanyPageSource(self.http, self.config).fetch_jobs(company)

        base, tenant, wd_instance, site = parsed_match.groups()
        api_url = f"{base}/wday/cxs/{tenant}/{site}/jobs"

        try:
            data = self.http.get_json(
                api_url,
                params={"limit": 50, "offset": 0},
                headers={"Accept": "application/json"},
            )
        except Exception:
            from job_agent.sources.company_page import CompanyPageSource

            return CompanyPageSource(self.http, self.config).fetch_jobs(company)

        jobs: list[RawJob] = []
        postings = data.get("jobPostings", []) if isinstance(data, dict) else []

        for item in postings[: self.config.max_jobs_per_company]:
            title = item.get("title", "")
            if not AI_KEYWORDS.search(title):
                continue

            ext_path = item.get("externalPath", "")
            job_url = f"{base}{ext_path}" if ext_path else careers_url
            bullet_fields = item.get("bulletFields", [])

            location = ""
            if bullet_fields:
                location = str(bullet_fields[0])

            job_id = item.get("jobPostingId") or ext_path

            jobs.append(
                RawJob(
                    company=company.name,
                    title=title,
                    url=job_url,
                    application_url=job_url,
                    source=self.source_name,
                    source_job_id=f"workday:{tenant}:{job_id}",
                    location=location,
                    date_posted=parse_date(item.get("postedOn")),
                    company_priority=company.priority,
                )
            )

        return jobs
