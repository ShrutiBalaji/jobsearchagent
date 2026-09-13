"""Main job search pipeline orchestration."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

from job_agent.config import AppConfig, load_config
from job_agent.database import Database
from job_agent.deduplication import deduplicate_raw_jobs, prepare_job_identity
from job_agent.llm_scorer import LLMScorer
from job_agent.models import JobRecord, JobStatus, RawJob, SearchSummary
from job_agent.normalization import content_hash, filter_qualifying_jobs, normalize_raw_job
from job_agent.excel_export import rebuild_jobs_in_excel
from job_agent.reporting import generate_report, save_report
from job_agent.scoring import evaluate_job, sort_jobs
from job_agent.sources.base import get_source_for_company
from job_agent.sources.discovery import DiscoverySource
from job_agent.utils.dates import today_utc
from job_agent.utils.http import HttpClient
from job_agent.utils.salary import meets_salary_threshold, parse_salary
from job_agent.utils.urls import is_generic_careers_url, is_valid_http_url

logger = logging.getLogger("job_agent.scheduler")


def validate_application_url(http: HttpClient, url: str) -> str:
    """Validate application URL; return status string."""
    if not is_valid_http_url(url):
        return "invalid"
    if is_generic_careers_url(url):
        return "generic"
    try:
        response = http.head(url, check_robots=False)
        if response.status_code < 400:
            return "verified"
    except Exception:
        pass
    return "unverified"


class JobAgentPipeline:
    """Orchestrates the full job search pipeline."""

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or load_config()
        self.http = HttpClient(
            timeout=self.config.request_timeout_seconds,
            retries=self.config.request_retries,
            rate_limit_delay=self.config.rate_limit_delay_seconds,
        )
        self.db = Database(self.config.database_path)
        self.llm = LLMScorer(self.config)

    def collect_jobs(self) -> tuple[list[RawJob], SearchSummary]:
        """Fetch jobs from all configured sources."""
        summary = SearchSummary()
        all_jobs: list[RawJob] = []

        for company in self.config.companies:
            summary.companies_searched += 1
            source = get_source_for_company(company, self.http, self.config)
            jobs, error = source.safe_fetch(company)
            if error:
                summary.companies_failed += 1
                summary.failures.append({"company": company.name, "error": error})
                self.db.record_source_failure(company.name, source.source_name, error)
            else:
                summary.companies_succeeded += 1
                all_jobs.extend(jobs)

        if self.config.discovery_enabled:
            discovery = DiscoverySource(self.http, self.config)
            discovered = discovery.discover_all()
            all_jobs.extend(discovered)

        summary.jobs_collected = len(all_jobs)
        return all_jobs, summary

    def process_jobs(self, raw_jobs: list[RawJob], summary: SearchSummary) -> list[JobRecord]:
        """Normalize, deduplicate, score, and store jobs."""
        deduped = deduplicate_raw_jobs(raw_jobs)
        summary.jobs_after_dedup = len(deduped)

        qualifying: list[JobRecord] = []
        new_qualifying: list[JobRecord] = []

        for raw in deduped:
            normalized = normalize_raw_job(raw, self.config)
            if not normalized:
                continue

            scored, qualifies = evaluate_job(normalized, self.config)
            if not scored:
                continue

            parsed = parse_salary(normalized.salary_text or scored.description)
            salary_ok, _ = meets_salary_threshold(
                parsed,
                self.config.salary_threshold,
                include_unknown_if_excellent=self.config.include_unknown_compensation_if_excellent,
                match_score=scored.match_score,
                excellent_threshold=self.config.excellent_match_threshold,
            )
            if salary_ok and not parsed.compensation_unknown:
                summary.jobs_above_salary += 1

            scored.content_hash = content_hash(
                scored.company, scored.title, scored.description
            )
            if qualifies:
                scored.application_url_status = validate_application_url(
                    self.http, scored.application_url
                )
                scored = self.llm.enhance(scored)
            else:
                scored.application_url_status = "unverified"

            url_canonical, dedup_key, _ = prepare_job_identity(scored)
            stored, is_new = self.db.upsert_job(
                scored, dedup_key=dedup_key, url_canonical=url_canonical
            )

            if qualifies and stored.match_score >= self.config.minimum_match_score:
                summary.jobs_score_qualifying += 1
                qualifying.append(stored)
                if is_new or stored.status == JobStatus.NEW:
                    new_qualifying.append(stored)

        summary.new_qualifying_jobs = len(new_qualifying)
        return qualifying

    def run(
        self,
        mode: Literal["run", "dry-run", "search"] = "run",
    ) -> SearchSummary:
        """Execute full pipeline."""
        raw_jobs, summary = self.collect_jobs()
        qualifying = self.process_jobs(raw_jobs, summary)

        date_filter = {
            "max_age_days": self.config.max_job_age_days,
            "require_posting_date": self.config.require_posting_date,
        }
        new_jobs = self.db.get_new_qualifying_jobs(
            self.config.minimum_match_score, **date_filter
        )
        all_qualifying = self.db.get_all_qualifying_jobs(
            self.config.minimum_match_score, **date_filter
        )
        all_qualifying = filter_qualifying_jobs(all_qualifying, self.config)
        new_jobs = [j for j in all_qualifying if j.status.value == "NEW"]

        report_date = today_utc()
        html, text, json_data = generate_report(new_jobs, all_qualifying, summary, report_date)
        save_report(self.config.report_dir, report_date, html, json_data)

        if mode == "run":
            if all_qualifying:
                written, excel_path = rebuild_jobs_in_excel(
                    self.config.excel_path, all_qualifying
                )
                summary.excel_rows_appended = written
                summary.excel_path = str(excel_path)
            else:
                summary.excel_path = str(Path(self.config.excel_path).resolve())

            if new_jobs:
                job_ids = [j.id for j in new_jobs if j.id]
                if job_ids:
                    self.db.mark_reported(job_ids)

        self._print_summary(summary)
        return summary

    @staticmethod
    def _print_summary(summary: SearchSummary) -> None:
        print("\n" + "=" * 50)
        print("AI JOB AGENT — RUN SUMMARY")
        print("=" * 50)
        print(f"Companies searched: {summary.companies_searched}")
        print(f"Companies succeeded: {summary.companies_succeeded}")
        print(f"Companies failed: {summary.companies_failed}")
        print(f"Jobs collected: {summary.jobs_collected}")
        print(f"Jobs after deduplication: {summary.jobs_after_dedup}")
        print(f"Jobs above salary threshold: {summary.jobs_above_salary}")
        print(f"Jobs score >=70: {summary.jobs_score_qualifying}")
        print(f"New qualifying jobs: {summary.new_qualifying_jobs}")
        if summary.excel_path:
            print(f"Excel tracker: {summary.excel_path}")
            print(f"Rows appended this run: {summary.excel_rows_appended}")
        if summary.failures:
            print(f"\nFailures ({len(summary.failures)}):")
            for f in summary.failures[:10]:
                print(f"  - {f['company']}: {f['error'][:80]}")
        print("=" * 50)
