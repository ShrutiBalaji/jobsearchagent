"""Lever ATS job source."""

from __future__ import annotations

import logging
import re

from job_agent.models import CompanyConfig, RawJob
from job_agent.sources.base import JobSource
from job_agent.utils.dates import parse_date

logger = logging.getLogger("job_agent.sources.lever")

AI_KEYWORDS = re.compile(
    r"\b(ai|ml|machine learning|artificial intelligence|computer vision|"
    r"deep learning|llm|genai|inference|ml engineer|ai engineer)\b",
    re.I,
)


class LeverSource(JobSource):
    source_name = "lever"

    def fetch_jobs(self, company: CompanyConfig) -> list[RawJob]:
        slug = company.company_slug
        if not slug:
            raise ValueError(f"No company_slug for {company.name}")

        url = f"https://api.lever.co/v0/postings/{slug}"
        data = self.http.get_json(url, params={"mode": "json"}, check_robots=False)

        if not isinstance(data, list):
            data = data.get("data", []) if isinstance(data, dict) else []

        jobs: list[RawJob] = []
        for item in data[: self.config.max_jobs_per_company]:
            title = item.get("text", "") or item.get("title", "")
            description = item.get("descriptionPlain", "") or item.get("description", "")

            if not AI_KEYWORDS.search(f"{title} {description}"):
                continue

            job_id = item.get("id", "")
            job_url = item.get("hostedUrl") or item.get("applyUrl", "")

            categories = item.get("categories", {})
            location = categories.get("location", "") if isinstance(categories, dict) else ""

            jobs.append(
                RawJob(
                    company=company.name,
                    title=title,
                    url=job_url,
                    application_url=item.get("applyUrl") or job_url,
                    source=self.source_name,
                    source_job_id=f"lever:{slug}:{job_id}",
                    location=location,
                    description=description if isinstance(description, str) else str(description),
                    date_posted=parse_date(item.get("createdAt")),
                    employment_type=categories.get("commitment") if isinstance(categories, dict) else None,
                    company_priority=company.priority,
                )
            )

        return jobs
