"""Job deduplication logic."""

from __future__ import annotations

from job_agent.models import JobRecord, RawJob
from job_agent.normalization import content_hash
from job_agent.utils.urls import canonical_job_url, normalize_company_name, normalize_url


def make_dedup_key(company: str, title: str, location: str | None) -> str:
    """Create deduplication key from company + title + location."""
    parts = [
        normalize_company_name(company),
        title.lower().strip(),
        (location or "").lower().strip(),
    ]
    return "|".join(parts)


def deduplicate_raw_jobs(jobs: list[RawJob]) -> list[RawJob]:
    """Deduplicate raw jobs in-memory before processing."""
    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    seen_keys: set[str] = set()
    result: list[RawJob] = []

    for job in jobs:
        if job.source_job_id:
            sid = f"{job.source}:{job.source_job_id}"
            if sid in seen_ids:
                continue
            seen_ids.add(sid)

        url_key = canonical_job_url(job.url)
        if url_key and url_key in seen_urls:
            continue
        if url_key:
            seen_urls.add(url_key)

        key = make_dedup_key(job.company, job.title, job.location)
        if key in seen_keys:
            continue
        seen_keys.add(key)

        result.append(job)

    return result


def prepare_job_identity(job: JobRecord) -> tuple[str, str, str]:
    """Return (url_canonical, dedup_key, content_hash) for a job."""
    url_canonical = canonical_job_url(job.url)
    dedup_key = make_dedup_key(job.company, job.title, job.location)
    chash = job.content_hash or content_hash(job.company, job.title, job.description)
    return url_canonical, dedup_key, chash
