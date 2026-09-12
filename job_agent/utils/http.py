"""HTTP client with retries, rate limiting, and robots.txt respect."""

from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger("job_agent.http")

DEFAULT_HEADERS = {
    "User-Agent": "AIJobAgent/1.0 (+https://github.com/jobsearchagent; job-search-bot)",
    "Accept": "application/json, text/html, */*",
}

# Public ATS/job-board APIs intended for programmatic access.
ROBOTS_EXEMPT_DOMAINS = frozenset(
    {
        "boards-api.greenhouse.io",
        "api.lever.co",
        "api.ashbyhq.com",
        "api.smartrecruiters.com",
        "apply.workable.com",
    }
)


class HttpClient:
    """HTTP client with exponential backoff and optional robots.txt checks."""

    def __init__(
        self,
        timeout: float = 30.0,
        retries: int = 3,
        rate_limit_delay: float = 0.5,
        respect_robots: bool = True,
    ) -> None:
        self.timeout = timeout
        self.rate_limit_delay = rate_limit_delay
        self.respect_robots = respect_robots
        self._robots_cache: dict[str, RobotFileParser] = {}
        self._last_request_time: dict[str, float] = {}

        retry_strategy = Retry(
            total=retries,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _domain(self, url: str) -> str:
        return urlparse(url).netloc

    def _can_fetch(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        domain = self._domain(url)
        if domain in ROBOTS_EXEMPT_DOMAINS:
            return True
        if domain not in self._robots_cache:
            rp = RobotFileParser()
            robots_url = f"{urlparse(url).scheme}://{domain}/robots.txt"
            try:
                rp.set_url(robots_url)
                rp.read()
                self._robots_cache[domain] = rp
            except Exception as exc:
                logger.debug("Could not read robots.txt for %s: %s", domain, exc)
                self._robots_cache[domain] = rp
        rp = self._robots_cache[domain]
        try:
            return rp.can_fetch(DEFAULT_HEADERS["User-Agent"], url)
        except Exception:
            return True

    def _rate_limit(self, url: str) -> None:
        domain = self._domain(url)
        now = time.monotonic()
        last = self._last_request_time.get(domain, 0.0)
        elapsed = now - last
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self._last_request_time[domain] = time.monotonic()

    def get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        check_robots: bool = True,
    ) -> requests.Response:
        """Perform GET with rate limiting and optional robots.txt check."""
        if check_robots and not self._can_fetch(url):
            raise PermissionError(f"robots.txt disallows fetching: {url}")

        self._rate_limit(url)
        merged_headers = {**self.session.headers}
        if headers:
            merged_headers.update(headers)

        logger.debug("GET %s", url)
        response = self.session.get(
            url, params=params, headers=merged_headers, timeout=self.timeout
        )
        response.raise_for_status()
        return response

    def head(self, url: str, *, check_robots: bool = False) -> requests.Response:
        """Perform HEAD request (typically for URL validation)."""
        if check_robots and not self._can_fetch(url):
            raise PermissionError(f"robots.txt disallows fetching: {url}")
        self._rate_limit(url)
        response = self.session.head(url, timeout=self.timeout, allow_redirects=True)
        return response

    def get_json(self, url: str, **kwargs: Any) -> Any:
        """GET and parse JSON response."""
        return self.get(url, **kwargs).json()
