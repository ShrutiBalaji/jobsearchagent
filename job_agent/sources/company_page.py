"""Generic company career page scraper fallback."""

from __future__ import annotations

import logging
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from job_agent.models import CompanyConfig, RawJob
from job_agent.sources.base import JobSource

logger = logging.getLogger("job_agent.sources.company_page")

AI_KEYWORDS = re.compile(
    r"\b(ai|ml|machine learning|artificial intelligence|computer vision|"
    r"deep learning|llm|genai|inference|ml engineer|ai engineer|data scientist)\b",
    re.I,
)

JOB_LINK_PATTERNS = [
    re.compile(r"/jobs?/\d+", re.I),
    re.compile(r"/job/\d+", re.I),
    re.compile(r"/careers?/[^/]+/\d+", re.I),
    re.compile(r"/positions?/\d+", re.I),
    re.compile(r"gh_jid=", re.I),
    re.compile(r"greenhouse\.io", re.I),
    re.compile(r"lever\.co", re.I),
    re.compile(r"ashbyhq\.com", re.I),
]


class CompanyPageSource(JobSource):
    source_name = "company_page"

    def fetch_jobs(self, company: CompanyConfig) -> list[RawJob]:
        url = company.careers_url
        if not url:
            raise ValueError(f"No careers_url for {company.name}")

        # Strip URL fragment (#careers) — HTTP fetch uses the base page.
        fetch_url = url.split("#", 1)[0]
        response = self.http.get(fetch_url, check_robots=True)
        soup = BeautifulSoup(response.text, "lxml")

        jobs: list[RawJob] = []
        seen_urls: set[str] = set()
        base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"

        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            text = link.get_text(strip=True)
            if not text or len(text) < 5:
                continue

            full_url = urljoin(base, href)
            if full_url in seen_urls:
                continue

            is_job_link = any(p.search(href) or p.search(full_url) for p in JOB_LINK_PATTERNS)
            is_ai_title = AI_KEYWORDS.search(text)

            if not is_job_link and not is_ai_title:
                continue
            if not is_ai_title:
                continue

            seen_urls.add(full_url)
            jobs.append(
                RawJob(
                    company=company.name,
                    title=text[:200],
                    url=full_url,
                    application_url=full_url,
                    source=self.source_name,
                    source_job_id=f"company_page:{company.name}:{hash(full_url)}",
                    company_priority=company.priority,
                )
            )

            if len(jobs) >= self.config.max_jobs_per_company:
                break

        return jobs
