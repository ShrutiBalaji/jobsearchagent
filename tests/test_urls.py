"""Tests for URL utilities."""

from job_agent.utils.urls import canonical_job_url, is_generic_careers_url, is_valid_http_url


def test_valid_url():
    assert is_valid_http_url("https://boards.greenhouse.io/openai/jobs/123")
    assert not is_valid_http_url("not-a-url")


def test_generic_careers_url():
    assert is_generic_careers_url("https://company.com/careers")
    assert not is_generic_careers_url("https://boards.greenhouse.io/co/jobs/12345")


def test_canonical_job_url():
    url = "https://jobs.example.com/apply/123?utm_source=x"
    canonical = canonical_job_url(url)
    assert "utm_source" not in canonical
