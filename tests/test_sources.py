"""Mocked tests for ATS adapters."""

import json

import responses

from job_agent.config import load_config
from job_agent.models import CompanyConfig
from job_agent.sources.ashby import AshbySource
from job_agent.sources.greenhouse import GreenhouseSource
from job_agent.sources.lever import LeverSource
from job_agent.utils.http import HttpClient


GREENHOUSE_RESPONSE = {
    "jobs": [
        {
            "id": 123,
            "title": "Machine Learning Engineer",
            "absolute_url": "https://boards.greenhouse.io/test/jobs/123",
            "location": {"name": "Remote, US"},
            "content": "<p>Python, PyTorch, LLM, production ML systems. $150k-$200k</p>",
            "updated_at": "2024-03-01T00:00:00Z",
        },
        {
            "id": 456,
            "title": "Office Manager",
            "absolute_url": "https://boards.greenhouse.io/test/jobs/456",
            "location": {"name": "NYC"},
            "content": "<p>Administrative role</p>",
        },
    ]
}

LEVER_RESPONSE = [
    {
        "id": "abc-123",
        "text": "AI Engineer",
        "hostedUrl": "https://jobs.lever.co/test/abc-123",
        "applyUrl": "https://jobs.lever.co/test/abc-123/apply",
        "descriptionPlain": "Machine learning, computer vision, PyTorch",
        "categories": {"location": "New York, NY", "commitment": "Full-time"},
        "createdAt": 1709251200000,
    }
]

ASHBY_RESPONSE = {
    "jobs": [
        {
            "id": "job-1",
            "title": "ML Infrastructure Engineer",
            "jobUrl": "https://jobs.ashbyhq.com/test/job-1",
            "applyUrl": "https://jobs.ashbyhq.com/test/job-1/apply",
            "location": "Remote",
            "descriptionPlain": "GPU inference, CUDA, distributed systems",
            "publishedAt": "2024-03-01",
            "employmentType": "FullTime",
        }
    ]
}


@responses.activate
def test_greenhouse_source():
    config = load_config()
    http = HttpClient(respect_robots=False)
    source = GreenhouseSource(http, config)
    company = CompanyConfig(name="TestCo", board_token="testco", ats="greenhouse")

    responses.add(
        responses.GET,
        "https://boards-api.greenhouse.io/v1/boards/testco/jobs",
        json=GREENHOUSE_RESPONSE,
        status=200,
    )

    jobs = source.fetch_jobs(company)
    assert len(jobs) == 1
    assert jobs[0].title == "Machine Learning Engineer"
    assert jobs[0].source == "greenhouse"


@responses.activate
def test_lever_source():
    config = load_config()
    http = HttpClient(respect_robots=False)
    source = LeverSource(http, config)
    company = CompanyConfig(name="TestCo", company_slug="testco", ats="lever")

    responses.add(
        responses.GET,
        "https://api.lever.co/v0/postings/testco",
        json=LEVER_RESPONSE,
        status=200,
    )

    jobs = source.fetch_jobs(company)
    assert len(jobs) == 1
    assert "AI Engineer" in jobs[0].title


@responses.activate
def test_ashby_source():
    config = load_config()
    http = HttpClient(respect_robots=False)
    source = AshbySource(http, config)
    company = CompanyConfig(name="TestCo", org_slug="testco", ats="ashby")

    responses.add(
        responses.GET,
        "https://api.ashbyhq.com/posting-api/job-board/testco",
        json=ASHBY_RESPONSE,
        status=200,
    )

    jobs = source.fetch_jobs(company)
    assert len(jobs) == 1
    assert "ML Infrastructure" in jobs[0].title
