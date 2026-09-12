"""SQLite database layer using SQLAlchemy."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    func,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from job_agent.models import JobRecord, JobStatus, ScoreBreakdown
from job_agent.utils.dates import today_utc

logger = logging.getLogger("job_agent.database")


class Base(DeclarativeBase):
    pass


class JobORM(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company = Column(String(256), nullable=False, index=True)
    title = Column(String(512), nullable=False)
    url = Column(String(2048), nullable=False)
    application_url = Column(String(2048), nullable=False)
    source = Column(String(64), nullable=False)
    source_job_id = Column(String(256), index=True)
    location = Column(String(512))
    city = Column(String(128))
    state = Column(String(128))
    country = Column(String(128))
    remote_type = Column(String(32))
    salary_min = Column(Integer)
    salary_max = Column(Integer)
    salary_currency = Column(String(8), default="USD")
    salary_period = Column(String(32))
    compensation_unknown = Column(Integer, default=1)
    date_posted = Column(Date)
    date_first_seen = Column(DateTime, nullable=False)
    date_last_seen = Column(DateTime, nullable=False)
    description = Column(Text)
    requirements = Column(Text)
    match_score = Column(Float, default=0.0, index=True)
    score_breakdown = Column(Text)
    why_match = Column(Text)
    missing_requirements = Column(Text)
    risk_flags = Column(Text)
    status = Column(String(32), default=JobStatus.NEW.value, index=True)
    content_hash = Column(String(64), index=True)
    application_url_status = Column(String(32))
    company_priority = Column(String(4), default="D")
    employment_type = Column(String(64))
    reported_at = Column(DateTime)
    url_canonical = Column(String(2048), index=True)
    dedup_key = Column(String(512), index=True)


class SourceFailureORM(Base):
    __tablename__ = "source_failures"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company = Column(String(256), nullable=False)
    source = Column(String(64), nullable=False)
    error_message = Column(Text)
    occurred_at = Column(DateTime, nullable=False)


class Database:
    """Database operations for job storage."""

    def __init__(self, db_path: str) -> None:
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)

    def _session(self) -> Session:
        return self.SessionLocal()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _job_to_orm(job: JobRecord, *, dedup_key: str, url_canonical: str) -> JobORM:
        return JobORM(
            company=job.company,
            title=job.title,
            url=job.url,
            application_url=job.application_url,
            source=job.source,
            source_job_id=job.source_job_id,
            location=job.location,
            city=job.city,
            state=job.state,
            country=job.country,
            remote_type=job.remote_type.value if hasattr(job.remote_type, "value") else job.remote_type,
            salary_min=job.salary_min,
            salary_max=job.salary_max,
            salary_currency=job.salary_currency,
            salary_period=job.salary_period,
            compensation_unknown=1 if job.compensation_unknown else 0,
            date_posted=job.date_posted,
            date_first_seen=job.date_first_seen or Database._now(),
            date_last_seen=job.date_last_seen or Database._now(),
            description=job.description,
            requirements=job.requirements,
            match_score=job.match_score,
            score_breakdown=json.dumps(job.score_breakdown.to_dict()),
            why_match=job.why_match,
            missing_requirements=job.missing_requirements,
            risk_flags=json.dumps(job.risk_flags),
            status=job.status.value if isinstance(job.status, JobStatus) else job.status,
            content_hash=job.content_hash,
            application_url_status=job.application_url_status,
            company_priority=job.company_priority,
            employment_type=job.employment_type,
            url_canonical=url_canonical,
            dedup_key=dedup_key,
        )

    @staticmethod
    def _orm_to_job(row: JobORM) -> JobRecord:
        breakdown_data = json.loads(row.score_breakdown or "{}")
        breakdown = ScoreBreakdown(
            technical_stack=breakdown_data.get("technical_stack", 0),
            production_ai=breakdown_data.get("production_ai", 0),
            role_title=breakdown_data.get("role_title", 0),
            medical_cv=breakdown_data.get("medical_cv", 0),
            llm_genai=breakdown_data.get("llm_genai", 0),
            systems_infra=breakdown_data.get("systems_infra", 0),
            experience_level=breakdown_data.get("experience_level", 0),
            compensation=breakdown_data.get("compensation", 0),
        )
        return JobRecord(
            id=row.id,
            company=row.company,
            title=row.title,
            url=row.url,
            application_url=row.application_url,
            source=row.source,
            source_job_id=row.source_job_id,
            location=row.location,
            city=row.city,
            state=row.state,
            country=row.country,
            remote_type=row.remote_type or "unknown",
            salary_min=row.salary_min,
            salary_max=row.salary_max,
            salary_currency=row.salary_currency or "USD",
            salary_period=row.salary_period or "yearly",
            compensation_unknown=bool(row.compensation_unknown),
            date_posted=row.date_posted,
            date_first_seen=row.date_first_seen,
            date_last_seen=row.date_last_seen,
            description=row.description or "",
            requirements=row.requirements or "",
            match_score=row.match_score or 0.0,
            score_breakdown=breakdown,
            why_match=row.why_match or "",
            missing_requirements=row.missing_requirements or "",
            risk_flags=json.loads(row.risk_flags or "[]"),
            status=JobStatus(row.status) if row.status else JobStatus.SEEN,
            content_hash=row.content_hash or "",
            application_url_status=row.application_url_status or "unverified",
            company_priority=row.company_priority or "D",
            employment_type=row.employment_type,
        )

    def _find_duplicate_in_session(
        self,
        session: Session,
        *,
        source_job_id: str | None,
        url_canonical: str,
        dedup_key: str,
        content_hash: str,
    ) -> JobORM | None:
        if source_job_id:
            row = session.scalar(
                select(JobORM).where(JobORM.source_job_id == source_job_id).limit(1)
            )
            if row:
                return row
        for field, value in [
            (JobORM.url_canonical, url_canonical),
            (JobORM.dedup_key, dedup_key),
            (JobORM.content_hash, content_hash),
        ]:
            if value:
                row = session.scalar(select(JobORM).where(field == value).limit(1))
                if row:
                    return row
        return None

    def upsert_job(
        self,
        job: JobRecord,
        *,
        dedup_key: str,
        url_canonical: str,
    ) -> tuple[JobRecord, bool]:
        """Insert or update job. Returns (job, is_new)."""
        now = self._now()
        with self._session() as session:
            existing = self._find_duplicate_in_session(
                session,
                source_job_id=job.source_job_id,
                url_canonical=url_canonical,
                dedup_key=dedup_key,
                content_hash=job.content_hash,
            )

            if existing:
                is_new = False
                existing.date_last_seen = now
                existing.match_score = job.match_score
                existing.score_breakdown = json.dumps(job.score_breakdown.to_dict())
                existing.why_match = job.why_match
                existing.missing_requirements = job.missing_requirements
                existing.risk_flags = json.dumps(job.risk_flags)
                existing.salary_min = job.salary_min
                existing.salary_max = job.salary_max
                existing.compensation_unknown = 1 if job.compensation_unknown else 0
                existing.application_url = job.application_url
                existing.application_url_status = job.application_url_status

                if existing.content_hash != job.content_hash:
                    existing.status = JobStatus.UPDATED.value
                    existing.content_hash = job.content_hash
                    existing.description = job.description
                    existing.title = job.title
                elif existing.status == JobStatus.NEW.value:
                    pass  # keep NEW until reported
                else:
                    existing.status = JobStatus.SEEN.value

                session.merge(existing)
                session.commit()
                session.refresh(existing)
                return self._orm_to_job(existing), is_new

            job.date_first_seen = now
            job.date_last_seen = now
            job.status = JobStatus.NEW
            orm = self._job_to_orm(job, dedup_key=dedup_key, url_canonical=url_canonical)
            session.add(orm)
            session.commit()
            session.refresh(orm)
            result = self._orm_to_job(orm)
            return result, True

    def get_new_qualifying_jobs(
        self,
        min_score: float,
        *,
        max_age_days: int | None = None,
        require_posting_date: bool = True,
    ) -> list[JobRecord]:
        with self._session() as session:
            query = (
                select(JobORM)
                .where(JobORM.status == JobStatus.NEW.value)
                .where(JobORM.match_score >= min_score)
            )
            query = self._apply_posting_date_filter(
                query, max_age_days, require_posting_date
            )
            rows = session.scalars(query.order_by(JobORM.match_score.desc())).all()
            return [self._orm_to_job(r) for r in rows]

    def get_all_qualifying_jobs(
        self,
        min_score: float,
        *,
        max_age_days: int | None = None,
        require_posting_date: bool = True,
    ) -> list[JobRecord]:
        with self._session() as session:
            query = select(JobORM).where(JobORM.match_score >= min_score)
            query = self._apply_posting_date_filter(
                query, max_age_days, require_posting_date
            )
            rows = session.scalars(query.order_by(JobORM.match_score.desc())).all()
            return [self._orm_to_job(r) for r in rows]

    @staticmethod
    def _apply_posting_date_filter(query, max_age_days: int | None, require_posting_date: bool):
        if max_age_days is None or max_age_days <= 0:
            return query
        if require_posting_date:
            query = query.where(JobORM.date_posted.isnot(None))
        cutoff = today_utc() - timedelta(days=max_age_days)
        return query.where(JobORM.date_posted >= cutoff)

    def mark_reported(self, job_ids: list[int]) -> None:
        now = self._now()
        with self._session() as session:
            rows = session.scalars(select(JobORM).where(JobORM.id.in_(job_ids))).all()
            for row in rows:
                row.status = JobStatus.SEEN.value
                row.reported_at = now
            session.commit()

    def record_source_failure(self, company: str, source: str, error: str) -> None:
        with self._session() as session:
            session.add(
                SourceFailureORM(
                    company=company,
                    source=source,
                    error_message=error[:2000],
                    occurred_at=self._now(),
                )
            )
            session.commit()

    def get_stats(self) -> dict[str, Any]:
        with self._session() as session:
            total = session.scalar(select(func.count()).select_from(JobORM)) or 0
            qualifying = (
                session.scalar(
                    select(func.count()).select_from(JobORM).where(JobORM.match_score >= 70)
                )
                or 0
            )
            new_jobs = (
                session.scalar(
                    select(func.count())
                    .select_from(JobORM)
                    .where(JobORM.status == JobStatus.NEW.value)
                )
                or 0
            )

            by_company = dict(
                session.execute(
                    select(JobORM.company, func.count())
                    .group_by(JobORM.company)
                    .order_by(func.count().desc())
                ).all()
            )

            by_score = {
                "90-100": session.scalar(
                    select(func.count()).select_from(JobORM).where(JobORM.match_score >= 90)
                )
                or 0,
                "80-89": session.scalar(
                    select(func.count())
                    .select_from(JobORM)
                    .where(JobORM.match_score >= 80, JobORM.match_score < 90)
                )
                or 0,
                "70-79": session.scalar(
                    select(func.count())
                    .select_from(JobORM)
                    .where(JobORM.match_score >= 70, JobORM.match_score < 80)
                )
                or 0,
            }

            failures = session.scalars(
                select(SourceFailureORM).order_by(SourceFailureORM.occurred_at.desc()).limit(20)
            ).all()

            return {
                "total_jobs": total,
                "qualifying_jobs": qualifying,
                "new_jobs": new_jobs,
                "by_company": by_company,
                "by_score": by_score,
                "recent_failures": [
                    {
                        "company": f.company,
                        "source": f.source,
                        "error": f.error_message,
                        "at": f.occurred_at.isoformat() if f.occurred_at else None,
                    }
                    for f in failures
                ],
            }
