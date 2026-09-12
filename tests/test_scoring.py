"""Tests for job scoring."""

from datetime import date

from job_agent.config import load_config
from job_agent.models import RawJob, RemoteType
from job_agent.scoring import score_job


def test_score_ai_engineer_job(sample_job_description, config):
    raw = RawJob(
        company="TestCo",
        title="Machine Learning Engineer",
        url="https://example.com/jobs/123",
        source="test",
        source_job_id="test:123",
        description=sample_job_description,
        salary_text="$150,000 - $200,000",
        location="New York, NY",
        remote_type=RemoteType.REMOTE,
        date_posted=date.today(),
        company_priority="A",
    )
    result = score_job(raw, config)
    assert result is not None
    assert result.match_score >= 70
    assert result.why_match
    assert "Machine Learning Engineer" in result.title


def test_reject_non_target_role(config):
    raw = RawJob(
        company="TestCo",
        title="Product Manager",
        url="https://example.com/jobs/456",
        source="test",
        description="Roadmaps, stakeholders, and sprint planning. No ML required.",
        salary_text="$110,000",
        location="San Francisco, CA",
        date_posted=date.today(),
    )
    result = score_job(raw, config)
    assert result is None


def test_reject_senior_without_flexibility(config):
    raw = RawJob(
        company="TestCo",
        title="Senior Staff ML Engineer",
        url="https://example.com/jobs/789",
        source="test",
        description="10+ years experience required. Principal level.",
        salary_text="$200,000",
    )
    result = score_job(raw, config)
    assert result is None


def test_allow_senior_ml_engineer_with_five_years(config, sample_job_description):
    raw = RawJob(
        company="TestCo",
        title="Senior Machine Learning Engineer",
        url="https://example.com/jobs/790",
        source="test",
        description=f"{sample_job_description}\n5+ years of ML engineering experience.",
        salary_text="$180,000 - $220,000",
        location="Remote - USA",
        date_posted=date.today(),
    )
    result = score_job(raw, config)
    assert result is not None
    assert result.score_breakdown.experience_level >= 70


def test_experience_score_matches_candidate_years(config):
    from job_agent.scoring import _experience_score

    low_years_score, _ = _experience_score(
        "Machine Learning Engineer",
        "Looking for 1-2 years of Python and PyTorch experience.",
        config,
    )
    mid_years_score, flags = _experience_score(
        "Machine Learning Engineer",
        "Looking for 3+ years of Python and PyTorch experience.",
        config,
    )
    high_years_score, _ = _experience_score(
        "Machine Learning Engineer",
        "Looking for 5+ years of Python and PyTorch experience.",
        config,
    )

    assert low_years_score == 100.0
    assert mid_years_score >= 84.0
    assert high_years_score < mid_years_score
    assert not any("Requires" in flag for flag in flags)

    low_score, high_flags = _experience_score(
        "Principal ML Engineer",
        "Minimum of 12 years experience required.",
        config,
    )
    assert low_score < 40
    assert high_flags


def test_sort_jobs_prefers_lower_experience_requirement(config, sample_job_description):
    from job_agent.models import JobRecord, ScoreBreakdown
    from job_agent.scoring import sort_jobs

    high_years = JobRecord(
        company="A",
        title="ML Engineer",
        url="https://example.com/a",
        application_url="https://example.com/a",
        source="test",
        description="Requires 5+ years of ML experience.",
        match_score=80.0,
        score_breakdown=ScoreBreakdown(),
    )
    low_years = JobRecord(
        company="B",
        title="ML Engineer",
        url="https://example.com/b",
        application_url="https://example.com/b",
        source="test",
        description=f"{sample_job_description}\n1-2 years experience preferred.",
        match_score=80.0,
        score_breakdown=ScoreBreakdown(),
    )
    assert sort_jobs([high_years, low_years])[0].company == "B"


def test_score_breakdown_weights(config, sample_job_description):
    raw = RawJob(
        company="Healthcare AI",
        title="AI Engineer - Medical Imaging",
        url="https://example.com/jobs/100",
        source="test",
        description=sample_job_description,
        salary_text="$130,000 - $170,000",
        date_posted=date.today(),
    )
    result = score_job(raw, config)
    assert result is not None
    breakdown = result.score_breakdown.to_dict()
    assert "technical_stack" in breakdown
    assert "total" in breakdown
    assert breakdown["total"] == result.match_score
