"""Tests for skill gap detection."""

from job_agent.config import load_config
from job_agent.scoring import exceeds_max_experience_requirement, format_skills_missing


def test_format_skills_missing_lists_job_only_skills(config):
    text = "Looking for Kubernetes, PyTorch, and Java experience in production ML."
    missing = format_skills_missing(text, config)
    assert "kubernetes" in missing.lower() or "Kubernetes" in missing
    assert "Java" in missing
    assert "PyTorch" not in missing


def test_exceeds_max_experience_requirement(config):
    assert exceeds_max_experience_requirement("Requires 7+ years experience", 5) is True
    assert exceeds_max_experience_requirement("Requires 3-5 years experience", 5) is False
    assert exceeds_max_experience_requirement("Requires 3-7 years experience", 5) is True
    assert exceeds_max_experience_requirement("Requires 5+ years experience", 5) is False
