"""Greenhouse ATS job source."""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from job_agent.models import CompanyConfig, RawJob, RemoteType
from job_agent.sources.base import JobSource
from job_agent.utils.dates import parse_date

logger = logging.getLogger("job_agent.sources.greenhouse")

AI_KEYWORDS = re.compile(
    r"\b(ai|ml|machine learning|artificial intelligence|computer vision|"
    r"deep learning|llm|genai|inference|ml engineer|ai engineer)\b",
    re.I,
)


class GreenhouseSource(JobSource):
    source_name = "greenhouse"

    def fetch_jobs(self, company: CompanyConfig) -> list[RawJob]:
        token = company.board_token
        if not token:
            raise ValueError(f"No board_token for {company.name}")

        url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
        params = {"content": "true"}
        data = self.http.get_json(url, params=params, check_robots=False)

        jobs: list[RawJob] = []
        for item in data.get("jobs", [])[: self.config.max_jobs_per_company]:
            title = item.get("title", "")
            if not AI_KEYWORDS.search(title):
                content = item.get("content", "") or ""
                if not AI_KEYWORDS.search(content):
                    continue

            location = item.get("location", {})
            loc_name = location.get("name") if isinstance(location, dict) else str(location or "")

            job_id = str(item.get("id", ""))
            job_url = item.get("absolute_url") or f"https://boards.greenhouse.io/{token}/jobs/{job_id}"

            jobs.append(
                RawJob(
                    company=company.name,
                    title=title,
                    url=job_url,
                    application_url=job_url,
                    source=self.source_name,
                    source_job_id=f"greenhouse:{token}:{job_id}",
                    location=loc_name,
                    description=self._strip_html(item.get("content", "")),
                    date_posted=parse_date(item.get("updated_at") or item.get("created_at")),
                    company_priority=company.priority,
                    metadata={"greenhouse_id": job_id},
                )
            )

        return jobs

    @staticmethod
    def _strip_html(html: str) -> str:
        if not html:
            return ""
        text = BeautifulSoup(html, "lxml").get_text(" ", strip=True)
        return re.sub(r"\s+", " ", text).strip()
