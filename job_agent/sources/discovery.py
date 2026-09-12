"""Optional company/job discovery from public ATS boards."""

from __future__ import annotations

import logging
from typing import Any

from job_agent.config import AppConfig
from job_agent.models import CompanyConfig, RawJob
from job_agent.sources.base import JobSource, get_source_for_company
from job_agent.utils.http import HttpClient

logger = logging.getLogger("job_agent.sources.discovery")

# Additional high-value AI companies not already in config/companies.yaml
DISCOVERY_COMPANIES: list[dict[str, Any]] = [
    {
        "name": "Modular",
        "priority": "B",
        "ats": "company_page",
        "careers_url": "https://www.modular.com/company/careers#open-roles",
    },
    {
        "name": "Character.AI",
        "priority": "B",
        "ats": "ashby",
        "org_slug": "character",
    },
    {
        "name": "Adept",
        "priority": "B",
        "ats": "smartrecruiters",
        "company_id": "Adept",
    },
    {
        "name": "Runway",
        "priority": "B",
        "ats": "ashby",
        "org_slug": "runway",
    },
    {
        "name": "Stability AI",
        "priority": "B",
        "ats": "greenhouse",
        "board_token": "stabilityai",
    },
    {
        "name": "Inflection AI",
        "priority": "B",
        "ats": "greenhouse",
        "board_token": "inflectionai",
    },
    {
        "name": "Snorkel AI",
        "priority": "B",
        "ats": "greenhouse",
        "board_token": "snorkelai",
    },
    {
        "name": "Labelbox",
        "priority": "C",
        "ats": "greenhouse",
        "board_token": "labelbox",
    },
    {
        "name": "Tecton",
        "priority": "C",
        "ats": "lever",
        "company_slug": "tecton",
    },
    {
        "name": "Anyscale",
        "priority": "B",
        "ats": "ashby",
        "org_slug": "anyscale",
    },
    {
        "name": "Replicate",
        "priority": "C",
        "ats": "smartrecruiters",
        "company_id": "Replicate",
    },
    {
        "name": "Baseten",
        "priority": "C",
        "ats": "ashby",
        "org_slug": "baseten",
    },
    {
        "name": "Roboflow",
        "priority": "C",
        "ats": "ashby",
        "org_slug": "roboflow",
    },
    {
        "name": "Pinecone",
        "priority": "B",
        "ats": "ashby",
        "org_slug": "pinecone",
    },
    {
        "name": "Weaviate",
        "priority": "C",
        "ats": "ashby",
        "org_slug": "weaviate",
    },
    {
        "name": "Glean",
        "priority": "B",
        "ats": "greenhouse",
        "board_token": "gleanwork",
    },
    {
        "name": "Harvey",
        "priority": "B",
        "ats": "ashby",
        "org_slug": "harvey",
    },
    {
        "name": "Ambience Healthcare",
        "priority": "A",
        "ats": "ashby",
        "org_slug": "ambiencehealthcare",
    },
    {
        "name": "Freenome",
        "priority": "B",
        "ats": "greenhouse",
        "board_token": "freenome",
    },
    {
        "name": "Butterfly Network",
        "priority": "B",
        "ats": "greenhouse",
        "board_token": "butterflynetwork",
    },
]


class DiscoverySource(JobSource):
    """Discover additional companies/jobs from known AI hiring boards."""

    source_name = "discovery"

    def fetch_jobs(self, company: CompanyConfig) -> list[RawJob]:
        return []

    def discover_all(self) -> list[RawJob]:
        """Discover jobs from additional AI companies."""
        if not self.config.discovery_enabled:
            logger.info("Discovery disabled in config")
            return []

        all_jobs: list[RawJob] = []
        configured_names = {c.name.lower() for c in self.config.companies}

        for entry in DISCOVERY_COMPANIES:
            name = entry["name"]
            if name.lower() in configured_names:
                continue

            company = CompanyConfig(
                name=name,
                priority=entry.get("priority", "D"),
                category="discovered",
                ats=entry.get("ats", "greenhouse"),
                board_token=entry.get("board_token"),
                company_slug=entry.get("company_slug"),
                org_slug=entry.get("org_slug"),
                company_id=entry.get("company_id"),
                careers_url=entry.get("careers_url"),
            )
            source = get_source_for_company(company, self.http, self.config)
            jobs, error = source.safe_fetch(company)
            if error:
                logger.debug("Discovery failed for %s: %s", name, error)
                continue
            all_jobs.extend(jobs)

        logger.info("Discovery found %d jobs from additional companies", len(all_jobs))
        return all_jobs
