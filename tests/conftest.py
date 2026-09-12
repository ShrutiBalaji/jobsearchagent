"""Shared test fixtures."""

from __future__ import annotations

import pytest

from job_agent.config import AppConfig, load_config


@pytest.fixture
def config() -> AppConfig:
    return load_config()


@pytest.fixture
def sample_job_description() -> str:
    return """
    We are looking for a Machine Learning Engineer to build production AI systems.
    Requirements: Python, PyTorch, CUDA, Docker, FastAPI, distributed systems.
    Experience with medical imaging, DICOM, computer vision preferred.
    LLM and multimodal AI experience a plus. 1-3 years experience.
    Salary: $150,000 - $200,000 per year. Full-time. Remote US.
    """
