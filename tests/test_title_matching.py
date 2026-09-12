"""Tests for title matching."""

from job_agent.config import load_config
from job_agent.scoring import _title_match_score


def test_exact_title_match():
    config = load_config()
    score = _title_match_score("Machine Learning Engineer", config)
    assert score >= 80


def test_partial_title_match():
    config = load_config()
    score = _title_match_score("Software Engineer, AI/ML", config)
    assert score >= 60


def test_unrelated_title():
    config = load_config()
    score = _title_match_score("Office Administrator", config)
    assert score < 50
