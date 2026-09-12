"""Tests for job posting freshness filter."""

from datetime import date, timedelta

from job_agent.config import load_config
from job_agent.models import RawJob, RemoteType
from job_agent.scoring import evaluate_job
from job_agent.utils.dates import is_recent_posting, today_utc


def test_is_recent_within_week():
    assert is_recent_posting(today_utc(), 7) is True
    assert is_recent_posting(today_utc() - timedelta(days=3), 7) is True


def test_is_stale_beyond_week():
    assert is_recent_posting(today_utc() - timedelta(days=8), 7) is False


def test_unknown_date_excluded_by_default():
    assert is_recent_posting(None, 7) is False


def test_unknown_date_allowed_when_configured():
    assert is_recent_posting(None, 7, allow_unknown=True) is True


def test_job_without_posting_date_not_qualified(config):
    raw = RawJob(
        company="TestCo",
        title="Machine Learning Engineer",
        url="https://example.com/jobs/3",
        source="test",
        description="Python, PyTorch, production ML systems. 1-3 years.",
        salary_text="$150,000 - $200,000",
        remote_type=RemoteType.REMOTE,
        company_priority="A",
    )
    record, qualifies = evaluate_job(raw, config)
    assert record is not None
    assert qualifies is False
    assert "posting_date_unknown" in record.risk_flags


def test_stale_job_not_qualified(config):
    raw = RawJob(
        company="TestCo",
        title="Machine Learning Engineer",
        url="https://example.com/jobs/1",
        source="test",
        description="Python, PyTorch, production ML systems. 1-3 years.",
        salary_text="$150,000 - $200,000",
        date_posted=date.today() - timedelta(days=30),
        remote_type=RemoteType.REMOTE,
        company_priority="A",
    )
    record, qualifies = evaluate_job(raw, config)
    assert record is not None
    assert qualifies is False
    assert any("posted_over" in f for f in record.risk_flags)


def test_recent_job_without_salary_qualifies(config):
    raw = RawJob(
        company="TestCo",
        title="Machine Learning Engineer",
        url="https://example.com/jobs/2",
        source="test",
        description="Python, PyTorch, CUDA, Docker, FastAPI, distributed ML inference.",
        location="New York, NY",
        date_posted=date.today() - timedelta(days=2),
        company_priority="A",
    )
    record, qualifies = evaluate_job(raw, config)
    assert record is not None
    assert qualifies is True
    assert "compensation_unknown" in record.risk_flags
