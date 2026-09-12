"""Tests for deduplication."""

from job_agent.deduplication import deduplicate_raw_jobs, make_dedup_key
from job_agent.models import RawJob
from job_agent.utils.urls import normalize_url, normalize_company_name


def test_dedup_key():
    key = make_dedup_key("OpenAI Inc.", "ML Engineer", "New York, NY")
    assert "openai" in key
    assert "ml engineer" in key


def test_deduplicate_raw_jobs():
    jobs = [
        RawJob(company="Co", title="ML Engineer", url="https://a.com/1", source="gh", source_job_id="1"),
        RawJob(company="Co", title="ML Engineer", url="https://a.com/1", source="gh", source_job_id="1"),
        RawJob(company="Co", title="AI Engineer", url="https://a.com/2", source="gh", source_job_id="2"),
    ]
    result = deduplicate_raw_jobs(jobs)
    assert len(result) == 2


def test_normalize_url_strips_tracking():
    url = "https://jobs.example.com/123?utm_source=linkedin&ref=abc"
    normalized = normalize_url(url)
    assert "utm_source" not in normalized
    assert "ref" not in normalized


def test_normalize_company_name():
    assert normalize_company_name("OpenAI, Inc.") == "openai"
    assert normalize_company_name("  Scale AI  ") == "scale ai"
