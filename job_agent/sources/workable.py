"""Workable ATS job source (public widget API)."""

from __future__ import annotations

import logging
import re

from job_agent.models import CompanyConfig, RawJob
from job_agent.sources.base import JobSource
from job_agent.utils.dates import parse_date

logger = logging.getLogger("job_agent.sources.workable")

AI_KEYWORDS = re.compile(
    r"\b(ai|ml|machine learning|artificial intelligence|computer vision|"
    r"deep learning|llm|genai|inference|ml engineer|ai engineer)\b",
    re.I,
)


class WorkableSource(JobSource):
    source_name = "workable"

    def fetch_jobs(self, company: CompanyConfig) -> list[RawJob]:
        account = company.board_token or company.org_slug
        if not account:
            raise ValueError(f"No workable account slug for {company.name}")

        url = f"https://apply.workable.com/api/v1/widget/accounts/{account}"
        data = self.http.get_json(url, check_robots=False)

        jobs: list[RawJob] = []
        for item in data.get("jobs", [])[: self.config.max_jobs_per_company]:
            title = item.get("title", "")
            description = item.get("description", "") or item.get("requirements", "") or ""
            if not AI_KEYWORDS.search(f"{title} {description}"):
                continue

            shortcode = item.get("shortcode", "")
            job_url = item.get("url") or f"https://apply.workable.com/j/{shortcode}"
            apply_url = item.get("application_url") or job_url

            location_parts = [
                item.get("city"),
                item.get("state"),
                item.get("country"),
            ]
            location = ", ".join(p for p in location_parts if p)

            jobs.append(
                RawJob(
                    company=company.name,
                    title=title,
                    url=job_url,
                    application_url=apply_url,
                    source=self.source_name,
                    source_job_id=f"workable:{account}:{shortcode}",
                    location=location or None,
                    description=description,
                    date_posted=parse_date(item.get("published_on") or item.get("created_at")),
                    employment_type=item.get("employment_type"),
                    company_priority=company.priority,
                )
            )

        return jobs
