"""Ashby ATS job source."""

from __future__ import annotations

import logging
import re

from job_agent.models import CompanyConfig, RawJob
from job_agent.sources.base import JobSource
from job_agent.utils.dates import parse_date

logger = logging.getLogger("job_agent.sources.ashby")

AI_KEYWORDS = re.compile(
    r"\b(ai|ml|machine learning|artificial intelligence|computer vision|"
    r"deep learning|llm|genai|inference|ml engineer|ai engineer)\b",
    re.I,
)


class AshbySource(JobSource):
    source_name = "ashby"

    def fetch_jobs(self, company: CompanyConfig) -> list[RawJob]:
        org = company.org_slug
        if not org:
            raise ValueError(f"No org_slug for {company.name}")

        url = f"https://api.ashbyhq.com/posting-api/job-board/{org}"
        data = self.http.get_json(url, check_robots=False)

        jobs: list[RawJob] = []
        for item in data.get("jobs", [])[: self.config.max_jobs_per_company]:
            title = item.get("title", "")
            if not AI_KEYWORDS.search(title):
                continue

            job_id = item.get("id", "")
            job_url = item.get("jobUrl") or item.get("applyUrl", "")

            location = item.get("location", "")
            if isinstance(location, dict):
                location = location.get("name", "")

            jobs.append(
                RawJob(
                    company=company.name,
                    title=title,
                    url=job_url,
                    application_url=item.get("applyUrl") or job_url,
                    source=self.source_name,
                    source_job_id=f"ashby:{org}:{job_id}",
                    location=str(location),
                    description=item.get("descriptionPlain", "") or "",
                    date_posted=parse_date(item.get("publishedAt")),
                    employment_type=item.get("employmentType"),
                    company_priority=company.priority,
                )
            )

        return jobs
