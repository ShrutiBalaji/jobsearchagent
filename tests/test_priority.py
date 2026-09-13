"""Tests for job priority tiers."""

from job_agent.config import load_config
from job_agent.models import JobRecord, RemoteType, ScoreBreakdown
from job_agent.priority import compute_priority_tier, filter_and_rank_jobs


def _job(**kwargs) -> JobRecord:
    defaults = dict(
        company="Anthropic",
        title="Machine Learning Engineer",
        url="https://example.com/job",
        application_url="https://example.com/job",
        source="test",
        location="San Francisco, CA",
        remote_type=RemoteType.HYBRID,
        description="Python, PyTorch, production ML.",
        match_score=80.0,
        score_breakdown=ScoreBreakdown(),
        company_priority="A",
    )
    defaults.update(kwargs)
    return JobRecord(**defaults)


def test_tier1_target_company_junior(config):
    tier = compute_priority_tier(
        _job(title="Junior Machine Learning Engineer", description="1-2 years preferred."),
        config,
    )
    assert tier == 1


def test_tier1_target_company_three_years(config):
    tier = compute_priority_tier(
        _job(
            title="Machine Learning Engineer",
            description="Requires 3+ years of experience.",
        ),
        config,
    )
    assert tier == 1


def test_tier2_market_role_under_three_years(config):
    tier = compute_priority_tier(
        _job(
            company="OtherCo",
            title="Data Scientist",
            description="Requires 2+ years of experience.",
        ),
        config,
    )
    assert tier == 2


def test_tier3_market_role_under_five_years(config):
    tier = compute_priority_tier(
        _job(
            company="OtherCo",
            title="Machine Learning Engineer",
            description="Requires 4+ years of experience.",
        ),
        config,
    )
    assert tier == 3


def test_exclude_senior_over_five_years(config):
    tier = compute_priority_tier(
        _job(
            title="Senior Machine Learning Engineer",
            description="Requires 7+ years of experience.",
        ),
        config,
    )
    assert tier == 0


def test_filter_and_rank_jobs_sorts_by_tier(config):
    jobs = [
        _job(
            company="OtherCo",
            title="Data Scientist",
            description="Requires 4+ years of experience.",
            match_score=75.0,
        ),
        _job(
            title="Junior Machine Learning Engineer",
            description="Python and PyTorch.",
            match_score=70.0,
        ),
    ]
    ranked = filter_and_rank_jobs(jobs, config)
    assert len(ranked) == 2
    assert ranked[0].search_priority_tier == 1
    assert ranked[1].search_priority_tier == 3
