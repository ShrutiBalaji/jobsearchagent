"""Structured logging configuration."""

from __future__ import annotations

import logging
import re
from pathlib import Path


SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(password|passwd|secret|token|api_key|apikey)\s*[=:]\s*\S+", re.I), r"\1=***REDACTED***"),
    (re.compile(r"Bearer\s+\S+", re.I), "Bearer ***REDACTED***"),
]


class SecretFilter(logging.Filter):
    """Redact potential secrets from log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            msg = record.msg
            for pattern, replacement in SECRET_PATTERNS:
                msg = pattern.sub(replacement, msg)
            record.msg = msg
        return True


def setup_logging(log_dir: str | Path, level: str = "INFO") -> logging.Logger:
    """Configure application logging to file and console."""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    log_file = log_path / "job_agent.log"

    logger = logging.getLogger("job_agent")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.addFilter(SecretFilter())

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(SecretFilter())

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger
