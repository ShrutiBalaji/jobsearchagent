"""Salary parsing and normalization utilities."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

SalaryPeriod = Literal["yearly", "hourly", "monthly", "weekly", "unknown"]
SalaryStatus = Literal["known", "unknown", "estimated"]


@dataclass
class ParsedSalary:
    """Parsed compensation information."""

    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str = "USD"
    salary_period: SalaryPeriod = "yearly"
    status: SalaryStatus = "unknown"
    raw_text: str | None = None
    compensation_unknown: bool = True
    hourly_estimated_annual: bool = False


# Common patterns for salary extraction
RANGE_PATTERNS = [
    # $150,000 - $200,000
    re.compile(
        r"\$\s*([\d,]+(?:\.\d{2})?)\s*[-–—to]+\s*\$\s*([\d,]+(?:\.\d{2})?)",
        re.I,
    ),
    # $150k - $200k
    re.compile(
        r"\$\s*([\d,]+(?:\.\d+)?)\s*[kK]\s*[-–—to]+\s*\$\s*([\d,]+(?:\.\d+)?)\s*[kK]",
        re.I,
    ),
    # 150,000 - 200,000 USD
    re.compile(
        r"([\d,]+(?:\.\d{2})?)\s*[-–—to]+\s*([\d,]+(?:\.\d{2})?)\s*(USD|usd|\$)",
        re.I,
    ),
    # $150k+
    re.compile(r"\$\s*([\d,]+(?:\.\d+)?)\s*[kK]\+", re.I),
    # $150,000+
    re.compile(r"\$\s*([\d,]+(?:\.\d{2})?)\+", re.I),
    # Up to $200,000
    re.compile(r"up\s+to\s+\$\s*([\d,]+(?:\.\d{2})?)", re.I),
]

HOURLY_PATTERNS = [
    re.compile(
        r"\$\s*([\d,]+(?:\.\d{2})?)\s*[-–—to]+\s*\$\s*([\d,]+(?:\.\d{2})?)\s*/?\s*hr",
        re.I,
    ),
    re.compile(r"\$\s*([\d,]+(?:\.\d{2})?)\s*/?\s*hour", re.I),
    re.compile(r"([\d,]+(?:\.\d{2})?)\s*USD\s*/?\s*hour", re.I),
]

SINGLE_AMOUNT = re.compile(r"\$\s*([\d,]+(?:\.\d{2})?)", re.I)
K_NOTATION = re.compile(r"\$\s*([\d,]+(?:\.\d+)?)\s*[kK](?:\s|$|/|\)|,)", re.I)


def _parse_amount(text: str, is_k: bool = False) -> int:
    """Parse numeric amount to integer dollars."""
    cleaned = text.replace(",", "").strip()
    value = float(cleaned)
    if is_k or (value < 1000 and "." in cleaned):
        if value < 1000:
            value *= 1000
    return int(value)


def _annualize_hourly(amount: int) -> int:
    """Convert hourly rate to annual (2080 hours)."""
    return int(amount * 2080)


def parse_salary(text: str | None) -> ParsedSalary:
    """Parse compensation from job description or metadata."""
    if not text or not text.strip():
        return ParsedSalary(status="unknown", compensation_unknown=True)

    raw = text.strip()
    result = ParsedSalary(raw_text=raw, status="unknown", compensation_unknown=True)

    # Check hourly first
    for pattern in HOURLY_PATTERNS:
        match = pattern.search(raw)
        if match:
            groups = match.groups()
            if len(groups) >= 2:
                min_h = _parse_amount(groups[0])
                max_h = _parse_amount(groups[1])
                result.salary_min = _annualize_hourly(min_h)
                result.salary_max = _annualize_hourly(max_h)
            else:
                hourly = _parse_amount(groups[0])
                result.salary_min = _annualize_hourly(hourly)
                result.salary_max = result.salary_min
            result.salary_period = "hourly"
            result.status = "estimated"
            result.hourly_estimated_annual = True
            result.compensation_unknown = False
            return result

    # Range patterns
    for pattern in RANGE_PATTERNS:
        match = pattern.search(raw)
        if match:
            groups = match.groups()
            is_k = "k" in pattern.pattern.lower()
            if len(groups) >= 2:
                result.salary_min = _parse_amount(groups[0], is_k)
                result.salary_max = _parse_amount(groups[1], is_k)
            else:
                amount = _parse_amount(groups[0], is_k)
                result.salary_min = amount
                result.salary_max = amount
            result.salary_period = "yearly"
            result.status = "known"
            result.compensation_unknown = False
            return result

    # K notation single
    k_match = K_NOTATION.search(raw)
    if k_match:
        amount = _parse_amount(k_match.group(1), is_k=True)
        result.salary_min = amount
        result.salary_max = amount
        result.salary_period = "yearly"
        result.status = "known"
        result.compensation_unknown = False
        return result

    # Single dollar amount
    single = SINGLE_AMOUNT.search(raw)
    if single:
        amount = _parse_amount(single.group(1))
        if amount >= 30000:  # Likely annual if >= 30k
            result.salary_min = amount
            result.salary_max = amount
            result.salary_period = "yearly"
            result.status = "known"
            result.compensation_unknown = False
            return result

    return result


def meets_salary_threshold(
    parsed: ParsedSalary,
    threshold: int,
    *,
    include_unknown_if_excellent: bool = False,
    match_score: float = 0,
    excellent_threshold: float = 85,
) -> tuple[bool, str]:
    """
    Check if job meets salary threshold.

    Returns (passes, reason).
    """
    if parsed.compensation_unknown or parsed.salary_min is None:
        if include_unknown_if_excellent and match_score >= excellent_threshold:
            return True, "compensation_unknown_excellent_match"
        return True, "compensation_unknown"

    effective_min = parsed.salary_min
    if effective_min >= threshold:
        return True, "meets_threshold"

    if parsed.salary_max and parsed.salary_max >= threshold:
        return True, "range_max_meets_threshold"

    return False, "below_threshold"


def format_compensation(parsed: ParsedSalary) -> str:
    """Human-readable compensation string."""
    if parsed.compensation_unknown:
        return "Unknown (compensation_unknown)"

    if parsed.salary_min is None:
        return "Unknown (compensation_unknown)"

    prefix = "~" if parsed.hourly_estimated_annual else ""
    period_note = " (est. from hourly)" if parsed.hourly_estimated_annual else ""

    if parsed.salary_max and parsed.salary_max != parsed.salary_min:
        return (
            f"{prefix}${parsed.salary_min:,} - ${parsed.salary_max:,}/yr{period_note}"
        )

    return f"{prefix}${parsed.salary_min:,}/yr{period_note}"
