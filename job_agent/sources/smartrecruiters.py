"""SmartRecruiters ATS job source."""

from __future__ import annotations

import logging
import re

from job_agent.models import CompanyConfig, RawJob
from job_agent.sources.base import JobSource
from job_agent.utils.dates import parse_date

logger = logging.getLogger("job_agent.sources.smartrecruiters")

AI_KEYWORDS = re.compile(
    r"\b(ai|ml|machine learning|artificial intelligence|computer vision|"
    r"deep learning|llm|genai|inference|ml engineer|ai engineer)\b",
    re.I,
)


class SmartRecruitersSource(JobSource):
    source_name = "smartrecruiters"

    def fetch_jobs(self, company: CompanyConfig) -> list[RawJob]:
        company_id = company.company_id
        if not company_id:
            raise ValueError(f"No company_id for {company.name}")

        url = f"https://api.smartrecruiters.com/v1/companies/{company_id}/postings"
        data = self.http.get_json(
            url, params={"limit": self.config.max_jobs_per_company}, check_robots=False
        )

        jobs: list[RawJob] = []
        for item in data.get("content", []):
            title = item.get("name", "")
            if not AI_KEYWORDS.search(title):
                continue

            job_id = item.get("id", "")
            ref = item.get("ref", "")
            job_url = ref or f"https://jobs.smartrecruiters.com/{company_id}/{job_id}"

            location = item.get("location", {})
            loc_str = ""
            if isinstance(location, dict):
                parts = [location.get("city"), location.get("region"), location.get("country")]
                loc_str = ", ".join(p for p in parts if p)

            jobs.append(
                RawJob(
                    company=company.name,
                    title=title,
                    url=job_url,
                    application_url=job_url,
                    source=self.source_name,
                    source_job_id=f"smartrecruiters:{company_id}:{job_id}",
                    location=loc_str,
                    date_posted=parse_date(item.get("releasedDate")),
                    company_priority=company.priority,
                )
            )

        return jobs
