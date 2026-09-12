"""Job normalization from raw source data."""

from __future__ import annotations

import hashlib
import re

from job_agent.config import AppConfig
from job_agent.models import RawJob, RemoteType
from job_agent.utils.salary import parse_salary
from job_agent.utils.urls import canonical_job_url, is_valid_http_url, normalize_company_name


REMOTE_PATTERNS = {
    RemoteType.REMOTE: [
        r"\bremote\b",
        r"\bwork from home\b",
        r"\bwfh\b",
        r"\btelecommute\b",
        r"\banywhere\b",
        r"\bus remote\b",
        r"\bunited states remote\b",
    ],
    RemoteType.HYBRID: [
        r"\bhybrid\b",
        r"\bflexible\b",
        r"\bpartially remote\b",
    ],
    RemoteType.ONSITE: [
        r"\bonsite\b",
        r"\bon-site\b",
        r"\bin-office\b",
        r"\bin office\b",
    ],
}

LOCATION_PARTS = re.compile(r",\s*")

US_STATE_ABBREVS = (
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA",
    "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT",
    "VA", "WA", "WV", "WI", "WY", "DC",
)

US_LOCATION_PATTERNS = [
    r"\bunited states\b",
    r"\bremote\s*[-–—]?\s*(?:usa|u\.s\.a\.|u\.s\.)\b",
    r"\b(?:usa|u\.s\.a\.|u\.s\.)\s*[-–—]?\s*remote\b",
    r"\bremote-usa\b",
    r"\bremote-us\b",
    r"\bus remote\b",
    r"\bunited states remote\b",
    r"\bunited states\s*\(\s*remote\s*\)",
    rf",\s*(?:{'|'.join(US_STATE_ABBREVS)})\b",
    r"\b(?:alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida|"
    r"georgia|hawaii|idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|"
    r"massachusetts|michigan|minnesota|mississippi|missouri|montana|nebraska|nevada|"
    r"new hampshire|new jersey|new mexico|new york|north carolina|north dakota|ohio|oklahoma|"
    r"oregon|pennsylvania|rhode island|south carolina|south dakota|tennessee|texas|utah|"
    r"vermont|virginia|washington|west virginia|wisconsin|wyoming)\b",
    r"\b(?:alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida|"
    r"georgia|hawaii|idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|"
    r"massachusetts|michigan|minnesota|mississippi|missouri|montana|nebraska|nevada|"
    r"new hampshire|new jersey|new mexico|new york|north carolina|north dakota|ohio|oklahoma|"
    r"oregon|pennsylvania|rhode island|south carolina|south dakota|tennessee|texas|utah|"
    r"vermont|virginia|washington|west virginia|wisconsin|wyoming)\s*[-–—]\s*remote\b",
    r"\b(?:new york|san francisco|los angeles|boston|chicago|seattle|austin|denver|atlanta|"
    r"miami|philadelphia|washington|palo alto|mountain view|bay area|brooklyn|manhattan|"
    r"cambridge|redwood city)\b",
    r"\b(?:ny|sf|nyc)\b(?:\s|,|$|\)|;)",
]

NON_US_LOCATION_PATTERNS = [
    r"\bremote\s*[-–—]\s*(?!\s*(?:usa|u\.s\.a\.|u\.s\.|united states)\b)",
    r"\bindia\b",
    r"\bbangalore\b",
    r"\bbengaluru\b",
    r"\bgurugram\b",
    r"\bpune\b",
    r"\bunited kingdom\b",
    r"\b(?:^|[^a-z])uk(?:$|[^a-z])",
    r"\blondon\b",
    r"\bparis\b",
    r"\bfrance\b",
    r"\bgermany\b",
    r"\bmunich\b",
    r"\bamsterdam\b",
    r"\bnetherlands\b",
    r"\bdublin\b",
    r"\bireland\b",
    r"\bcanada\b",
    r"\btoronto\b",
    r"\baustralia\b",
    r"\bsydney\b",
    r"\bmelbourne\b",
    r"\bbrisbane\b",
    r"\bperth\b",
    r"\bkorea\b",
    r"\bturkish\b",
    r"\barabic\b",
    r"\bchina\b",
    r"\bjapan\b",
    r"\btokyo\b",
    r"\bsingapore\b",
    r"\bsouth korea\b",
    r"\bseoul\b",
    r"\bargentina\b",
    r"\buruguay\b",
    r"\bqatar\b",
    r"\bsaudi arabia\b",
    r"\briyadh\b",
    r"\bhungary\b",
    r"\bbudapest\b",
    r"\beurope\b",
    r"\bemea\b",
    r"\bapac\b",
    r"\blatam\b",
    r"\bmena\b",
    r"\bdoha\b",
]

GLOBAL_REMOTE_PATTERNS = [
    r"\bwork from anywhere\b",
    r"\banywhere in the world\b",
    r"\bworldwide\b",
    r"\bglobal(?:ly)?\s+remote\b",
    r"\bremote\s+global\b",
]

AMBIGUOUS_REMOTE_LOCATIONS = frozenset({"remote", "distributed", "work from home", "wfh"})


def _location_text(location: str | None, description: str = "") -> str:
    return f"{location or ''} {description}".lower()


def _has_us_location_indicator(text: str) -> bool:
    return any(re.search(pattern, text, re.I) for pattern in US_LOCATION_PATTERNS)


def is_usa_job_eligible(
    location: str | None,
    remote_type: RemoteType,
    description: str = "",
    title: str = "",
) -> bool:
    """Return True only when the job explicitly points to a US location."""
    text = f"{title} {_location_text(location, description)}"

    if any(re.search(pattern, text, re.I) for pattern in NON_US_LOCATION_PATTERNS):
        return False

    if remote_type == RemoteType.REMOTE:
        if any(re.search(pattern, text, re.I) for pattern in GLOBAL_REMOTE_PATTERNS):
            return False
        if re.search(r"\banywhere\b", text, re.I):
            return False

    return _has_us_location_indicator(text)


def should_include_job(
    *,
    title: str,
    location: str | None,
    remote_type: RemoteType,
    description: str = "",
    cfg: AppConfig,
) -> bool:
    """Return True if a job passes role, US-location, and experience filters."""
    from job_agent.scoring import exceeds_max_experience_requirement

    if is_excluded_role(title, description, cfg):
        return False
    if not is_usa_job_eligible(location, remote_type, description, title):
        return False
    combined = f"{title} {description}"
    return not exceeds_max_experience_requirement(combined, cfg.max_allowed_job_years)


def filter_qualifying_jobs(jobs, cfg: AppConfig):
    """Apply role and US-location filters to stored job records."""
    from job_agent.models import JobRecord

    filtered: list[JobRecord] = []
    for job in jobs:
        remote_type = job.remote_type
        if isinstance(remote_type, str):
            remote_type = RemoteType(remote_type)
        if should_include_job(
            title=job.title,
            location=job.location,
            remote_type=remote_type,
            description=job.description,
            cfg=cfg,
        ):
            filtered.append(job)
    return filtered


def detect_remote_type(location: str | None, description: str = "") -> RemoteType:
    """Detect remote/hybrid/onsite from location and description."""
    text = f"{location or ''} {description}".lower()
    for remote_type, patterns in REMOTE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text, re.I):
                return remote_type
    return RemoteType.UNKNOWN


def parse_location(location: str | None) -> tuple[str | None, str | None, str | None, str | None]:
    """Parse location into city, state, country."""
    if not location:
        return None, None, None, None

    loc = location.strip()
    parts = [p.strip() for p in LOCATION_PARTS.split(loc) if p.strip()]

    city = state = country = None
    if len(parts) == 1:
        if parts[0].lower() in ("remote", "us remote", "united states"):
            return "Remote", None, "US", loc
        city = parts[0]
    elif len(parts) == 2:
        city, state = parts
    elif len(parts) >= 3:
        city, state, country = parts[0], parts[1], parts[-1]

    return city, state, country, loc


def normalize_employment_type(text: str | None) -> str | None:
    if not text:
        return None
    return text.strip().lower()


def is_excluded_job_type(employment_type: str | None, title: str, description: str, cfg: AppConfig) -> bool:
    """Check if job should be excluded based on type."""
    combined = f"{employment_type or ''} {title} {description}".lower()
    for excluded in cfg.exclude_job_types:
        if excluded.lower() in combined:
            return True
    return False


def is_excluded_role(title: str, description: str, cfg: AppConfig) -> bool:
    """Check if role is obviously irrelevant based primarily on the job title."""
    title_lower = title.lower()
    for kw in cfg.excluded_role_keywords:
        kw_lower = kw.lower().strip()
        if not kw_lower:
            continue

        # Allow applied scientist roles when the title is AI/ML focused.
        if "applied scientist" in kw_lower and any(
            ai in title_lower
            for ai in ("machine learning", "ai", "ml", "computer vision", "research")
        ):
            continue

        # Match multi-word exclusions as phrases in the title.
        if " " in kw_lower:
            if kw_lower in title_lower:
                return True
            continue

        # Single-word exclusions require a whole-word title match to avoid
        # false positives from descriptions (e.g. "sales" in long JD text).
        if re.search(rf"\b{re.escape(kw_lower)}\b", title_lower):
            return True

    return False


def content_hash(company: str, title: str, description: str) -> str:
    """Generate content hash for deduplication."""
    normalized = f"{normalize_company_name(company)}|{title.lower().strip()}|{description[:2000].lower()}"
    return hashlib.sha256(normalized.encode()).hexdigest()


def normalize_raw_job(raw: RawJob, cfg: AppConfig) -> RawJob | None:
    """Normalize and validate a raw job."""
    if not raw.title or not raw.company:
        return None

    raw.title = raw.title.strip()
    raw.company = raw.company.strip()
    raw.url = canonical_job_url(raw.url) if raw.url else ""

    if not raw.application_url or not is_valid_http_url(raw.application_url):
        raw.application_url = raw.url

    if not is_valid_http_url(raw.url):
        return None

    if is_excluded_job_type(raw.employment_type, raw.title, raw.description, cfg):
        return None

    if is_excluded_role(raw.title, raw.description, cfg):
        return None

    if cfg.prefer_full_time:
        et = (raw.employment_type or "").lower()
        title_lower = raw.title.lower()
        if any(x in et or x in title_lower for x in ("intern", "part-time", "part time", "contract", "temporary")):
            if "full" not in et and "full-time" not in title_lower and "full time" not in title_lower:
                return None

    city, state, country, full_loc = parse_location(raw.location)
    raw.city = city
    raw.state = state
    raw.country = country
    raw.location = full_loc
    raw.remote_type = detect_remote_type(raw.location, raw.description)

    if not should_include_job(
        title=raw.title,
        location=raw.location,
        remote_type=raw.remote_type,
        description=raw.description,
        cfg=cfg,
    ):
        return None

    return raw
