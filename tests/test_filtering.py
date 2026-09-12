"""Tests for job filtering and normalization."""

import pytest

from job_agent.config import load_config
from job_agent.models import JobRecord, RawJob, RemoteType, ScoreBreakdown
from job_agent.normalization import (
    filter_qualifying_jobs,
    is_excluded_role,
    is_usa_job_eligible,
    normalize_raw_job,
    should_include_job,
)


def test_exclude_internship(config):
    raw = RawJob(
        company="Co",
        title="ML Engineering Intern",
        url="https://example.com/intern",
        source="test",
        description="Summer internship in machine learning.",
        employment_type="internship",
    )
    result = normalize_raw_job(raw, config)
    assert result is None


def test_allow_data_analyst_role(config):
    assert is_excluded_role("Senior Data Analyst", "SQL and Python ML", config) is False


def test_exclude_presales_customer_engineer(config):
    assert is_excluded_role("Presales Customer Engineer (Sydney)", "", config) is True
    assert is_excluded_role("Customer Engineer, Korea", "", config) is True


def test_allow_ml_engineer(config):
    raw = RawJob(
        company="Co",
        title="Machine Learning Engineer",
        url="https://example.com/job",
        source="test",
        description="Build ML systems with Python and PyTorch.",
        employment_type="full-time",
        location="San Francisco, CA",
    )
    result = normalize_raw_job(raw, config)
    assert result is not None


def test_exclude_non_us_remote_job(config):
    raw = RawJob(
        company="Co",
        title="Machine Learning Engineer",
        url="https://example.com/job",
        source="test",
        location="Remote - India",
        description="Build ML systems with Python and PyTorch.",
        employment_type="full-time",
    )
    assert normalize_raw_job(raw, config) is None


def test_allow_us_remote_job(config):
    raw = RawJob(
        company="Co",
        title="Machine Learning Engineer",
        url="https://example.com/job",
        source="test",
        location="Remote - USA",
        description="Build ML systems with Python and PyTorch.",
        employment_type="full-time",
    )
    result = normalize_raw_job(raw, config)
    assert result is not None
    assert result.remote_type == RemoteType.REMOTE


def test_exclude_ambiguous_remote_without_us_indicator(config):
    raw = RawJob(
        company="Co",
        title="Machine Learning Engineer",
        url="https://example.com/job",
        source="test",
        location="Remote",
        description="Build ML systems with Python and PyTorch.",
        employment_type="full-time",
    )
    assert normalize_raw_job(raw, config) is None


def test_allow_us_remote_explicit(config):
    raw = RawJob(
        company="Co",
        title="Data Scientist",
        url="https://example.com/job",
        source="test",
        location="Remote - USA",
        description="Python, SQL, machine learning.",
        employment_type="full-time",
    )
    assert normalize_raw_job(raw, config) is not None


def test_exclude_job_requiring_more_than_five_years(config):
    raw = RawJob(
        company="Co",
        title="Machine Learning Engineer",
        url="https://example.com/job",
        source="test",
        location="San Francisco, CA",
        description="Requires 7+ years of machine learning experience.",
        employment_type="full-time",
    )
    assert normalize_raw_job(raw, config) is None


def test_exclude_non_us_hybrid_job(config):
    raw = RawJob(
        company="Co",
        title="Machine Learning Engineer",
        url="https://example.com/job",
        source="test",
        location="London, UK",
        description="Hybrid role in our London office.",
        employment_type="full-time",
    )
    assert normalize_raw_job(raw, config) is None


def test_exclude_hybrid_job_with_foreign_city_in_title(config):
    raw = RawJob(
        company="Cloudflare",
        title="Presales Customer Engineer (Sydney)",
        url="https://example.com/job",
        source="test",
        location="Hybrid",
        description="Support enterprise customers.",
        employment_type="full-time",
    )
    assert normalize_raw_job(raw, config) is None


def test_filter_qualifying_jobs_removes_stored_non_us_roles(config):
    jobs = [
        JobRecord(
            company="Cloudflare",
            title="Presales Customer Engineer (Sydney)",
            url="https://example.com/1",
            application_url="https://example.com/1",
            source="test",
            location="Hybrid",
            remote_type=RemoteType.HYBRID,
            match_score=75.0,
            score_breakdown=ScoreBreakdown(),
        ),
        JobRecord(
            company="Co",
            title="Machine Learning Engineer",
            url="https://example.com/2",
            application_url="https://example.com/2",
            source="test",
            location="San Francisco, CA",
            remote_type=RemoteType.HYBRID,
            match_score=80.0,
            score_breakdown=ScoreBreakdown(),
        ),
    ]
    filtered = filter_qualifying_jobs(jobs, config)
    assert len(filtered) == 1
    assert filtered[0].title == "Machine Learning Engineer"


@pytest.mark.parametrize(
    ("location", "title", "remote_type", "expected"),
    [
        ("Remote - USA", "ML Engineer", RemoteType.REMOTE, True),
        ("US Remote", "ML Engineer", RemoteType.REMOTE, True),
        ("Remote - India", "ML Engineer", RemoteType.REMOTE, False),
        ("Remote", "ML Engineer", RemoteType.REMOTE, False),
        ("Remote - USA", "Data Scientist", RemoteType.REMOTE, True),
        ("London, UK", "ML Engineer", RemoteType.HYBRID, False),
        ("San Francisco, CA", "ML Engineer", RemoteType.ONSITE, True),
        ("NY, SF or Remote", "ML Engineer", RemoteType.REMOTE, True),
        ("Work from anywhere", "ML Engineer", RemoteType.REMOTE, False),
        ("Hybrid", "Presales Customer Engineer (Sydney)", RemoteType.HYBRID, False),
        ("Hybrid", "Customer Engineer, Korea (Based in Seoul)", RemoteType.HYBRID, False),
    ],
)
def test_is_usa_job_eligible(location, title, remote_type, expected):
    assert is_usa_job_eligible(location, remote_type, title=title) is expected


def test_should_include_job_excludes_sales_roles(config):
    assert (
        should_include_job(
            title="Presales Customer Engineer (Sydney)",
            location="Hybrid",
            remote_type=RemoteType.HYBRID,
            cfg=config,
        )
        is False
    )
