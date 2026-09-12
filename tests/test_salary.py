"""Tests for salary parsing."""

from job_agent.utils.salary import format_compensation, meets_salary_threshold, parse_salary


def test_parse_salary_range():
    result = parse_salary("$150,000 - $200,000")
    assert result.salary_min == 150_000
    assert result.salary_max == 200_000
    assert result.compensation_unknown is False
    assert result.status == "known"


def test_parse_salary_k_notation():
    result = parse_salary("Compensation: $150k - $200k annually")
    assert result.salary_min == 150_000
    assert result.salary_max == 200_000


def test_parse_hourly_to_annual():
    result = parse_salary("$50 - $75/hr")
    assert result.salary_min == 50 * 2080
    assert result.salary_max == 75 * 2080
    assert result.hourly_estimated_annual is True
    assert result.status == "estimated"


def test_unknown_compensation():
    result = parse_salary("")
    assert result.compensation_unknown is True
    assert result.salary_min is None


def test_meets_threshold():
    parsed = parse_salary("$120,000 - $150,000")
    ok, reason = meets_salary_threshold(parsed, 100_000)
    assert ok is True
    assert reason == "meets_threshold"


def test_below_threshold():
    parsed = parse_salary("$80,000 - $90,000")
    ok, reason = meets_salary_threshold(parsed, 100_000)
    assert ok is False


def test_unknown_compensation_excellent_match():
    parsed = parse_salary("")
    ok, reason = meets_salary_threshold(
        parsed, 100_000, include_unknown_if_excellent=True, match_score=90
    )
    assert ok is True
    assert reason == "compensation_unknown_excellent_match"


def test_format_compensation():
    parsed = parse_salary("$150,000 - $200,000")
    assert "$150,000" in format_compensation(parsed)
