"""Tests for email rendering."""

from datetime import date

from job_agent.models import JobRecord, JobStatus, RemoteType, ScoreBreakdown, SearchSummary
from job_agent.reporting import generate_report


def test_email_rendering():
    job = JobRecord(
        company="OpenAI",
        title="ML Engineer",
        url="https://example.com/job",
        application_url="https://example.com/apply",
        source="greenhouse",
        match_score=92.0,
        score_breakdown=ScoreBreakdown(technical_stack=90, production_ai=85, role_title=95),
        why_match="Strong AI/ML fit",
        missing_requirements="None",
        location="San Francisco, CA",
        remote_type=RemoteType.HYBRID,
        salary_min=180_000,
        salary_max=250_000,
        compensation_unknown=False,
        status=JobStatus.NEW,
        date_posted=date(2024, 3, 1),
    )
    summary = SearchSummary(
        companies_searched=10,
        companies_succeeded=8,
        new_qualifying_jobs=1,
    )
    html, text, json_data = generate_report([job], [job], summary)
    assert "OpenAI" in html
    assert "ML Engineer" in html
    assert "92" in html
    assert "OpenAI" in text
    assert json_data["new_jobs"][0]["company"] == "OpenAI"
