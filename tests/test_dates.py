"""Tests for date parsing."""

from datetime import date

from job_agent.utils.dates import parse_date


def test_parse_iso_date():
    assert parse_date("2024-03-15") == date(2024, 3, 15)


def test_parse_iso_datetime():
    assert parse_date("2024-03-15T10:30:00Z") == date(2024, 3, 15)


def test_parse_unix_timestamp():
    # 2024-01-01 00:00:00 UTC
    assert parse_date(1704067200) == date(2024, 1, 1)


def test_parse_none():
    assert parse_date(None) is None
    assert parse_date("") is None
