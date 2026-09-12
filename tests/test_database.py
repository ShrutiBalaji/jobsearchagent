"""Tests for database operations."""

import tempfile
from datetime import date, timedelta
from pathlib import Path

from job_agent.database import Database
from job_agent.models import JobRecord, JobStatus, RemoteType, ScoreBreakdown


def test_upsert_and_deduplicate():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        db = Database(str(db_path))

        job = JobRecord(
            company="TestCo",
            title="ML Engineer",
            url="https://example.com/job/1",
            application_url="https://example.com/job/1/apply",
            source="test",
            source_job_id="test:1",
            match_score=85.0,
            score_breakdown=ScoreBreakdown(role_title=90),
            content_hash="abc123",
            remote_type=RemoteType.REMOTE,
        )

        stored, is_new = db.upsert_job(job, dedup_key="testco|ml engineer|", url_canonical=job.url)
        assert is_new is True
        assert stored.id is not None

        stored2, is_new2 = db.upsert_job(job, dedup_key="testco|ml engineer|", url_canonical=job.url)
        assert is_new2 is False

        stats = db.get_stats()
        assert stats["total_jobs"] == 1


def test_get_qualifying_jobs():
    with tempfile.TemporaryDirectory() as tmp:
        db = Database(str(Path(tmp) / "test.db"))
        job = JobRecord(
            company="Co",
            title="AI Engineer",
            url="https://example.com/2",
            application_url="https://example.com/2",
            source="test",
            match_score=75.0,
            score_breakdown=ScoreBreakdown(),
            content_hash="def456",
            status=JobStatus.NEW,
            date_posted=date.today(),
        )
        db.upsert_job(job, dedup_key="co|ai engineer|", url_canonical=job.url)
        qualifying = db.get_all_qualifying_jobs(70, max_age_days=7)
        assert len(qualifying) == 1


def test_get_qualifying_jobs_excludes_stale_and_unknown_dates():
    with tempfile.TemporaryDirectory() as tmp:
        db = Database(str(Path(tmp) / "test.db"))
        recent = JobRecord(
            company="RecentCo",
            title="AI Engineer",
            url="https://example.com/recent",
            application_url="https://example.com/recent",
            source="test",
            match_score=80.0,
            score_breakdown=ScoreBreakdown(),
            content_hash="recent",
            status=JobStatus.NEW,
            date_posted=date.today(),
        )
        stale = JobRecord(
            company="StaleCo",
            title="AI Engineer",
            url="https://example.com/stale",
            application_url="https://example.com/stale",
            source="test",
            match_score=85.0,
            score_breakdown=ScoreBreakdown(),
            content_hash="stale",
            status=JobStatus.NEW,
            date_posted=date.today() - timedelta(days=10),
        )
        unknown = JobRecord(
            company="UnknownCo",
            title="AI Engineer",
            url="https://example.com/unknown",
            application_url="https://example.com/unknown",
            source="test",
            match_score=90.0,
            score_breakdown=ScoreBreakdown(),
            content_hash="unknown",
            status=JobStatus.NEW,
        )
        for job, key in (
            (recent, "recent"),
            (stale, "stale"),
            (unknown, "unknown"),
        ):
            db.upsert_job(job, dedup_key=key, url_canonical=job.url)

        qualifying = db.get_all_qualifying_jobs(70, max_age_days=7, require_posting_date=True)
        assert len(qualifying) == 1
        assert qualifying[0].company == "RecentCo"
