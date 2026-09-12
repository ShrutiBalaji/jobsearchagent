"""URL normalization and validation utilities."""

from __future__ import annotations

import hashlib
import logging
import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

logger = logging.getLogger("job_agent.urls")

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "ref",
    "source",
    "gh_src",
    "lever-source",
}


def normalize_url(url: str | None) -> str:
    """Normalize URL for deduplication."""
    if not url:
        return ""
    url = url.strip()
    parsed = urlparse(url)
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"

    query_params = parse_qs(parsed.query, keep_blank_values=False)
    filtered = {
        k: v for k, v in query_params.items() if k.lower() not in TRACKING_PARAMS
    }
    sorted_query = urlencode(sorted(filtered.items()), doseq=True)

    return urlunparse((scheme, netloc, path, "", sorted_query, ""))


def canonical_job_url(url: str) -> str:
    """Produce canonical job posting URL."""
    normalized = normalize_url(url)
    # Strip common job-board suffixes that don't affect identity
    normalized = re.sub(r"/apply/?$", "", normalized, flags=re.I)
    return normalized


def url_hash(url: str) -> str:
    """Hash a normalized URL."""
    return hashlib.sha256(normalize_url(url).encode()).hexdigest()


def is_valid_http_url(url: str | None) -> bool:
    """Check if string looks like a valid HTTP(S) URL."""
    if not url:
        return False
    parsed = urlparse(url.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def is_generic_careers_url(url: str) -> bool:
    """Detect generic careers pages vs direct job links."""
    if not url:
        return True
    parsed = urlparse(url.lower())
    path = parsed.path.rstrip("/")

    generic_patterns = [
        r"/careers/?$",
        r"/jobs/?$",
        r"/job-search/?$",
        r"/search-results/?$",
        r"/en-us/search/?$",
    ]
    for pattern in generic_patterns:
        if re.search(pattern, path):
            return True

    # Direct job indicators
    direct_patterns = [
        r"/jobs/\d+",
        r"/job/\d+",
        r"/postings/",
        r"/gh_jid=",
        r"lever\.co/[^/]+/[a-f0-9-]+$",
        r"ashbyhq\.com/[^/]+/[a-f0-9-]+$",
    ]
    for pattern in direct_patterns:
        if re.search(pattern, url, re.I):
            return False

    return len(path.split("/")) <= 3


def normalize_company_name(name: str) -> str:
    """Normalize company name for deduplication."""
    if not name:
        return ""
    normalized = name.lower().strip()
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"[^\w\s&.-]", "", normalized)
    suffixes = [
        " inc",
        " inc.",
        " llc",
        " ltd",
        " corp",
        " corporation",
        " co",
        " company",
    ]
    for suffix in suffixes:
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)].strip()
    return normalized
