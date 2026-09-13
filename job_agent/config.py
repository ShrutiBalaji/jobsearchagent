"""Configuration loading and management."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from job_agent.models import CompanyConfig


@dataclass
class AppConfig:
    """Application configuration."""

    salary_threshold: int = 100_000
    salary_currency: str = "USD"
    minimum_match_score: float = 70.0
    prefer_full_time: bool = True
    exclude_job_types: list[str] = field(default_factory=list)
    location_priorities: list[str] = field(default_factory=list)
    remote_preference: str = "hybrid_or_remote_ok"
    discovery_enabled: bool = True
    max_jobs_per_company: int = 200
    request_timeout_seconds: float = 30.0
    request_retries: int = 3
    rate_limit_delay_seconds: float = 0.5
    email_to: str = "shrutibalaji17@gmail.com"
    report_dir: str = "reports"
    excel_path: str = "reports/ai_job_matches.xlsx"
    log_dir: str = "logs"
    database_path: str = "jobs.db"
    default_company_priority: str = "D"
    candidate_years_experience: int = 5
    max_preferred_years: int = 5
    max_allowed_job_years: int = 5
    tier1_max_years: int = 3
    tier2_max_years: int = 3
    tier3_max_years: int = 5
    reject_senior_unless_flexible: bool = True
    candidate_skills: list[str] = field(default_factory=list)
    candidate_skills_text: str = ""
    include_unknown_compensation_if_excellent: bool = True
    excellent_match_threshold: float = 85.0
    max_job_age_days: int = 7
    require_posting_date: bool = True

    # Keywords
    target_roles: list[str] = field(default_factory=list)
    role_keywords: list[str] = field(default_factory=list)
    excluded_role_keywords: list[str] = field(default_factory=list)
    technical_stack: list[str] = field(default_factory=list)
    production_ai: list[str] = field(default_factory=list)
    medical_ai: list[str] = field(default_factory=list)
    llm_genai: list[str] = field(default_factory=list)
    systems_infra: list[str] = field(default_factory=list)
    senior_indicators: list[str] = field(default_factory=list)
    flexibility_indicators: list[str] = field(default_factory=list)

    companies: list[CompanyConfig] = field(default_factory=list)
    excluded_companies: list[str] = field(default_factory=list)

    # Environment
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    email_from: str = ""
    llm_provider: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    log_level: str = "INFO"


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_config(config_dir: str | Path | None = None) -> AppConfig:
    """Load configuration from YAML files and environment."""
    load_dotenv()

    base = Path(config_dir or os.getenv("JOB_AGENT_CONFIG_DIR", "config"))
    settings = _load_yaml(base / "settings.yaml")
    keywords = _load_yaml(base / "keywords.yaml")
    profile = _load_yaml(base / "candidate_profile.yaml")
    companies_data = _load_yaml(base / "companies.yaml")

    cfg = AppConfig()

    for key, value in settings.items():
        if hasattr(cfg, key):
            setattr(cfg, key, value)

    keyword_fields = [
        "target_roles",
        "role_keywords",
        "excluded_role_keywords",
        "technical_stack",
        "production_ai",
        "medical_ai",
        "llm_genai",
        "systems_infra",
        "senior_indicators",
        "flexibility_indicators",
    ]
    for key in keyword_fields:
        if key in keywords:
            setattr(cfg, key, keywords[key])

    cfg.candidate_skills = profile.get("core_skills", [])
    profile_parts = list(cfg.candidate_skills)
    for highlight in profile.get("highlights", []):
        profile_parts.append(str(highlight))
    cfg.candidate_skills_text = " ".join(profile_parts).lower()

    excluded = {c.lower() for c in companies_data.get("excluded_companies", [])}
    cfg.excluded_companies = list(excluded)

    companies: list[CompanyConfig] = []
    for entry in companies_data.get("companies", []):
        name = entry.get("name", "")
        if name.lower() in excluded:
            continue
        companies.append(
            CompanyConfig(
                name=name,
                priority=entry.get("priority", cfg.default_company_priority),
                category=entry.get("category", "other"),
                ats=entry.get("ats", "company_page"),
                board_token=entry.get("board_token"),
                company_slug=entry.get("company_slug"),
                org_slug=entry.get("org_slug"),
                company_id=entry.get("company_id"),
                careers_url=entry.get("careers_url"),
            )
        )
    cfg.companies = companies

    # Environment overrides
    cfg.smtp_host = os.getenv("SMTP_HOST", cfg.smtp_host)
    cfg.smtp_port = int(os.getenv("SMTP_PORT", str(cfg.smtp_port)))
    cfg.smtp_username = os.getenv("SMTP_USERNAME", cfg.smtp_username)
    cfg.smtp_password = os.getenv("SMTP_PASSWORD", cfg.smtp_password)
    cfg.email_from = os.getenv("EMAIL_FROM", cfg.email_from or cfg.smtp_username)
    cfg.email_to = os.getenv("EMAIL_TO", cfg.email_to)
    cfg.database_path = os.getenv("JOB_AGENT_DB_PATH", cfg.database_path)
    cfg.log_level = os.getenv("JOB_AGENT_LOG_LEVEL", cfg.log_level)
    cfg.llm_provider = os.getenv("LLM_PROVIDER")
    cfg.llm_api_key = os.getenv("LLM_API_KEY")
    cfg.llm_model = os.getenv("LLM_MODEL")

    return cfg
