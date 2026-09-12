"""Deterministic job match scoring."""

from __future__ import annotations

import re
from typing import Iterable

from job_agent.config import AppConfig
from job_agent.models import JobRecord, RawJob, ScoreBreakdown
from job_agent.utils.dates import is_recent_posting
from job_agent.utils.salary import ParsedSalary, format_compensation, meets_salary_threshold, parse_salary


def _keyword_score(text: str, keywords: Iterable[str]) -> float:
    """Score based on keyword presence (0-100).

    Uses match-count tiers rather than ratio-to-full-list so strong AI/ML
    postings are not penalized for omitting niche keywords.
    """
    if not text:
        return 0.0
    kw_list = list(keywords)
    if not kw_list:
        return 0.0
    text_lower = text.lower()
    matches = sum(1 for kw in kw_list if kw.lower() in text_lower)
    if matches == 0:
        return 0.0
    if matches >= 8:
        return 100.0
    if matches >= 6:
        return 90.0
    if matches >= 4:
        return 78.0
    if matches >= 3:
        return 68.0
    if matches >= 2:
        return 52.0
    return 38.0


def _medical_cv_score(text: str, cfg: AppConfig) -> float:
    """Score medical/CV fit; neutral when job is not healthcare-focused."""
    text_lower = text.lower()
    medical_job = any(
        term in text_lower
        for term in ("healthcare", "medical", "clinical", "radiology", "dicom", "diagnostic")
    )
    match = _keyword_score(text, cfg.medical_ai)
    if not medical_job:
        # Non-healthcare roles should not lose points for lacking medical keywords.
        return max(match, 55.0)
    return match


def _apply_title_baselines(breakdown: ScoreBreakdown, title: str) -> None:
    """Raise component scores when the title clearly indicates an AI/ML role."""
    title_lower = title.lower()
    ai_role_markers = (
        "machine learning",
        "ml engineer",
        "ai engineer",
        "data scientist",
        "data analyst",
        "quantitative analyst",
        "quant analyst",
        "ai analyst",
        "analytics engineer",
        "ml ",
        " ai ",
        "computer vision",
        "deep learning",
        "llm",
        "genai",
        "generative ai",
        "inference",
        "applied scientist",
        "research engineer",
        "ml systems",
        "ml infrastructure",
        "ml platform",
        "member of technical staff",
        "forward deployed",
        "applied ai",
        "ml research",
    )
    if breakdown.role_title < 55 and not any(m in title_lower for m in ai_role_markers):
        return

    breakdown.technical_stack = max(breakdown.technical_stack, 72.0)
    breakdown.production_ai = max(breakdown.production_ai, 68.0)
    breakdown.systems_infra = max(breakdown.systems_infra, 55.0)
    if any(m in title_lower for m in ("llm", "genai", "generative", "multimodal")):
        breakdown.llm_genai = max(breakdown.llm_genai, 58.0)
    elif breakdown.role_title >= 70:
        breakdown.llm_genai = max(breakdown.llm_genai, 45.0)


def _title_match_score(title: str, cfg: AppConfig) -> float:
    title_lower = title.lower()
    best = 0.0
    for role in cfg.target_roles:
        role_lower = role.lower()
        if role_lower in title_lower or title_lower in role_lower:
            best = max(best, 95.0)
        else:
            role_words = set(role_lower.split())
            title_words = set(re.findall(r"\w+", title_lower))
            overlap = len(role_words & title_words) / max(len(role_words), 1)
            best = max(best, overlap * 100)

    kw_score = _keyword_score(title_lower, cfg.role_keywords)
    return round(max(best, kw_score * 0.8), 1)


def _extract_years_requirement(text: str) -> int | None:
    patterns = [
        r"(\d+)\+?\s*(?:\+?\s*)?years?\s*(?:of\s+)?(?:experience|exp)",
        r"(\d+)\+\s*years?\s+of",
        r"(\d+)\s*[-–]\s*(\d+)\s*years?",
        r"minimum\s+of\s+(\d+)\s+years?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return int(match.group(1))
    return None


def _extract_max_years_requirement(text: str) -> int | None:
    range_match = re.search(r"(\d+)\s*[-–]\s*(\d+)\s*years?", text, re.I)
    if range_match:
        return int(range_match.group(2))
    return _extract_years_requirement(text)


def exceeds_max_experience_requirement(text: str, max_years: int) -> bool:
    """Return True if the job requires more than max_years experience."""
    max_required = _extract_max_years_requirement(text)
    if max_required is None:
        return False
    return max_required > max_years


EXTRA_SKILL_CHECKS: dict[str, list[str]] = {
    "Kubernetes": ["kubernetes", "k8s"],
    "Java": ["java ", "java,"],
    "Scala": [" scala", "scala "],
    "C++": ["c++", "cpp"],
    "Go": [" golang", " go "],
    "PhD": ["ph.d", "phd required", "doctorate"],
    "Spark": ["apache spark", " pyspark", "spark "],
    "Snowflake": ["snowflake"],
    "Databricks platform": ["databricks"],
    "Terraform": ["terraform"],
    "React Native": ["react native"],
    "Swift": ["swift"],
    "Kotlin": ["kotlin"],
    "Ruby": ["ruby"],
    "PHP": ["php"],
    "GraphQL": ["graphql"],
    "Elasticsearch": ["elasticsearch"],
    "Redis production": ["redis"],
    "MLOps platform": ["mlflow", "kubeflow", "mlops"],
}


def _candidate_has_skill(candidate_text: str, patterns: list[str]) -> bool:
    return any(pattern.lower() in candidate_text for pattern in patterns)


def _job_mentions_skill(job_text: str, patterns: list[str]) -> bool:
    return any(pattern.lower() in job_text for pattern in patterns)


def format_skills_missing(text: str, cfg: AppConfig) -> str:
    """Return comma-separated skills mentioned in the job but absent from the candidate profile."""
    job_text = text.lower()
    candidate_text = cfg.candidate_skills_text or " ".join(cfg.candidate_skills).lower()
    missing: list[str] = []
    seen: set[str] = set()

    keyword_groups = [
        cfg.technical_stack,
        cfg.production_ai,
        cfg.medical_ai,
        cfg.llm_genai,
        cfg.systems_infra,
    ]
    for group in keyword_groups:
        for keyword in group:
            kw = keyword.lower().strip()
            if not kw or kw not in job_text:
                continue
            if kw in candidate_text:
                continue
            display = keyword.strip()
            if display.islower() or display.isupper():
                display = display.title() if len(display) > 3 else display.upper()
            key = display.lower()
            if key in seen:
                continue
            seen.add(key)
            missing.append(display)

    for label, patterns in EXTRA_SKILL_CHECKS.items():
        if not _job_mentions_skill(job_text, patterns):
            continue
        if _candidate_has_skill(candidate_text, patterns):
            continue
        if label.lower() in seen:
            continue
        seen.add(label.lower())
        missing.append(label)

    return ", ".join(missing) if missing else "None identified"


def format_experience_needed(text: str) -> str:
    """Return human-readable years of experience required, or 'Not listed'."""
    range_match = re.search(r"(\d+)\s*[-–]\s*(\d+)\s*years?", text, re.I)
    if range_match:
        return f"{range_match.group(1)}-{range_match.group(2)} years"

    years = _extract_years_requirement(text)
    if years is not None:
        if re.search(rf"\b{years}\s*\+\s*years?\b", text, re.I):
            return f"{years}+ years"
        if re.search(rf"\bminimum\s+of\s+{years}\s+years?\b", text, re.I):
            return f"{years}+ years"
        return f"{years} years"

    return "Not listed"


def _is_high_seniority_title(title: str) -> bool:
    title_lower = title.lower()
    return any(term in title_lower for term in ("staff", "principal", "director", "distinguished"))


def _experience_score(title: str, description: str, cfg: AppConfig) -> tuple[float, list[str]]:
    """Score how well the job's experience requirement fits the candidate profile."""
    combined = f"{title} {description}".lower()
    flags: list[str] = []
    years_required = _extract_years_requirement(combined)
    candidate_years = cfg.candidate_years_experience

    is_senior_title = any(s in title.lower() for s in cfg.senior_indicators)
    is_high_seniority = _is_high_seniority_title(title)
    is_flexible = any(f in combined for f in cfg.flexibility_indicators)

    if years_required is not None:
        if years_required < 3:
            score = 100.0
        elif years_required == 3:
            score = 88.0 if is_flexible else 84.0
        elif years_required <= candidate_years:
            score = 78.0
        elif years_required <= candidate_years + 2:
            score = 68.0 if is_flexible else 58.0
        elif years_required <= cfg.max_preferred_years + 1:
            score = 52.0 if is_flexible else 42.0
            flags.append(f"Requires {years_required}+ years experience")
        else:
            score = 35.0 if is_flexible else 22.0
            flags.append(f"Requires {years_required}+ years experience")
    elif is_high_seniority:
        score = 58.0 if is_flexible else 32.0
        flags.append("Staff/Principal-level title")
    elif is_senior_title:
        score = 72.0 if is_flexible else 58.0
    else:
        score = 88.0

    if is_high_seniority and cfg.reject_senior_unless_flexible and not is_flexible:
        flags.append("Staff/Principal role without flexibility indicators")
    elif is_senior_title and cfg.reject_senior_unless_flexible and not is_flexible:
        if years_required and years_required > candidate_years + 2:
            flags.append("Senior role without flexibility indicators")

    return round(score, 1), flags


def _compensation_score(parsed: ParsedSalary, threshold: int) -> float:
    if parsed.compensation_unknown:
        return 40.0
    if parsed.salary_min is None:
        return 40.0
    if parsed.salary_min >= threshold * 1.5:
        return 100.0
    if parsed.salary_min >= threshold * 1.2:
        return 90.0
    if parsed.salary_min >= threshold:
        return 80.0
    if parsed.salary_max and parsed.salary_max >= threshold:
        return 70.0
    return 20.0


def _build_why_match(breakdown: ScoreBreakdown, raw: RawJob, cfg: AppConfig) -> str:
    reasons: list[str] = []
    if breakdown.role_title >= 70:
        reasons.append(f"Strong role/title alignment with target AI/ML engineering roles")
    if breakdown.technical_stack >= 60:
        reasons.append("Technical stack matches Python, PyTorch, and ML tooling")
    if breakdown.production_ai >= 60:
        reasons.append("Production AI/ML engineering experience aligns well")
    if breakdown.medical_cv >= 50:
        reasons.append("Healthcare AI / medical imaging experience is relevant")
    if breakdown.llm_genai >= 50:
        reasons.append("LLM/GenAI/multimodal experience matches requirements")
    if breakdown.systems_infra >= 50:
        reasons.append("Distributed systems and deployment skills are applicable")
    if raw.company_priority in ("A", "B"):
        reasons.append(f"High-priority target company ({raw.company})")
    return "; ".join(reasons) if reasons else "General AI/ML engineering fit based on profile keywords"


def _missing_requirements(text: str, cfg: AppConfig) -> str:
    return format_skills_missing(text, cfg)


def _build_job_record(
    raw: RawJob,
    cfg: AppConfig,
    *,
    breakdown: ScoreBreakdown,
    parsed: ParsedSalary,
    risk_flags: list[str],
    salary_reason: str,
) -> JobRecord:
    """Build a JobRecord from computed scoring components."""
    combined_text = f"{raw.title} {raw.description} {raw.requirements} {raw.salary_text or ''}"
    why = _build_why_match(breakdown, raw, cfg)
    missing = _missing_requirements(combined_text, cfg)

    if parsed.compensation_unknown:
        if "compensation_unknown" not in risk_flags:
            risk_flags.append("compensation_unknown")
        if salary_reason == "compensation_unknown":
            why += "; Compensation not listed (compensation_unknown)"

    return JobRecord(
        company=raw.company,
        title=raw.title,
        url=raw.url,
        application_url=raw.application_url or raw.url,
        source=raw.source,
        source_job_id=raw.source_job_id,
        location=raw.location,
        city=raw.city,
        state=raw.state,
        country=raw.country,
        remote_type=raw.remote_type,
        salary_min=parsed.salary_min,
        salary_max=parsed.salary_max,
        salary_currency=parsed.salary_currency,
        salary_period=parsed.salary_period,
        compensation_unknown=parsed.compensation_unknown,
        date_posted=raw.date_posted,
        description=raw.description,
        requirements=raw.requirements,
        match_score=breakdown.total,
        score_breakdown=breakdown,
        why_match=why,
        missing_requirements=missing,
        risk_flags=risk_flags,
        company_priority=raw.company_priority,
        employment_type=raw.employment_type,
    )


def evaluate_job(raw: RawJob, cfg: AppConfig) -> tuple[JobRecord | None, bool]:
    """Score a job and return (record, qualifies_for_report).

    Returns (None, False) only for hard rejects (non-AI roles, incompatible seniority).
    """
    combined_text = f"{raw.title} {raw.description} {raw.requirements} {raw.salary_text or ''}"

    breakdown = ScoreBreakdown(
        technical_stack=_keyword_score(combined_text, cfg.technical_stack),
        production_ai=_keyword_score(combined_text, cfg.production_ai),
        role_title=_title_match_score(raw.title, cfg),
        medical_cv=_medical_cv_score(combined_text, cfg),
        llm_genai=_keyword_score(combined_text, cfg.llm_genai),
        systems_infra=_keyword_score(combined_text, cfg.systems_infra),
    )
    _apply_title_baselines(breakdown, raw.title)

    exp_score, risk_flags = _experience_score(raw.title, combined_text, cfg)
    breakdown.experience_level = exp_score

    parsed = parse_salary(raw.salary_text or combined_text)
    breakdown.compensation = _compensation_score(parsed, cfg.salary_threshold)

    # Hard reject: clearly non-AI roles with low role score
    if breakdown.role_title < 30 and breakdown.technical_stack < 30:
        return None, False

    # Hard reject: staff/principal-level or 8+ years without flexibility
    if breakdown.experience_level < 40 and cfg.reject_senior_unless_flexible:
        flexible = any(f in combined_text.lower() for f in cfg.flexibility_indicators)
        years_required = _extract_years_requirement(combined_text)
        if not flexible and (
            _is_high_seniority_title(raw.title)
            or (years_required is not None and years_required >= cfg.candidate_years_experience + 4)
        ):
            return None, False

    match_score = breakdown.total
    salary_pass, salary_reason = meets_salary_threshold(
        parsed,
        cfg.salary_threshold,
        include_unknown_if_excellent=cfg.include_unknown_compensation_if_excellent,
        match_score=match_score,
        excellent_threshold=cfg.excellent_match_threshold,
    )

    qualifies = True
    if not salary_pass:
        qualifies = False
    elif match_score < cfg.minimum_match_score:
        qualifies = False
    elif exceeds_max_experience_requirement(combined_text, cfg.max_allowed_job_years):
        risk_flags.append(f"requires_over_{cfg.max_allowed_job_years}_years_experience")
        qualifies = False
    elif not is_recent_posting(
        raw.date_posted,
        cfg.max_job_age_days,
        allow_unknown=not cfg.require_posting_date,
    ):
        if raw.date_posted is None:
            risk_flags.append("posting_date_unknown")
        else:
            risk_flags.append(f"posted_over_{cfg.max_job_age_days}_days_ago")
        qualifies = False

    record = _build_job_record(
        raw, cfg, breakdown=breakdown, parsed=parsed, risk_flags=risk_flags, salary_reason=salary_reason
    )
    return record, qualifies


def score_job(raw: RawJob, cfg: AppConfig) -> JobRecord | None:
    """Score a raw job and return JobRecord if it qualifies for reporting."""
    record, qualifies = evaluate_job(raw, cfg)
    if record is None or not qualifies:
        return None
    return record


def _years_required_sort_key(job: JobRecord) -> tuple[int, int]:
    """Prefer jobs requiring fewer years; unknown requirements sort last."""
    combined = f"{job.title} {job.description} {job.requirements}"
    years = _extract_years_requirement(combined)
    if years is None:
        return (1, 999)
    return (0, years)


def sort_jobs(jobs: list[JobRecord]) -> list[JobRecord]:
    """Sort jobs by new status, score, experience needed, compensation, company priority."""
    priority_order = {"A": 0, "B": 1, "C": 2, "D": 3}

    def sort_key(job: JobRecord) -> tuple:
        is_new = 0 if job.status.value == "NEW" else 1
        comp = job.salary_max or job.salary_min or 0
        exp_bucket, exp_years = _years_required_sort_key(job)
        return (
            is_new,
            -job.match_score,
            exp_bucket,
            exp_years,
            -comp,
            priority_order.get(job.company_priority, 9),
        )

    return sorted(jobs, key=sort_key)
