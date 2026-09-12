"""Report generation (HTML, JSON, plaintext)."""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

from jinja2 import Template

from job_agent.models import JobRecord, SearchSummary
from job_agent.scoring import sort_jobs
from job_agent.utils.dates import today_utc
from job_agent.utils.salary import ParsedSalary, format_compensation

logger = logging.getLogger("job_agent.reporting")

HTML_TEMPLATE = Template("""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; color: #1a1a1a; }
    h1 { color: #2563eb; border-bottom: 2px solid #2563eb; padding-bottom: 8px; }
    h2 { color: #1e40af; margin-top: 32px; }
    .job { border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; margin: 12px 0; background: #fafafa; }
    .job.new { border-left: 4px solid #16a34a; }
    .score { font-weight: bold; color: #2563eb; }
    .score.exceptional { color: #059669; }
    .score.strong { color: #2563eb; }
    .label { color: #6b7280; font-size: 0.9em; }
    a { color: #2563eb; }
    .stats { background: #f3f4f6; padding: 16px; border-radius: 8px; }
    .flag { color: #dc2626; font-size: 0.85em; }
  </style>
</head>
<body>
  <h1>AI Job Agent — Daily Report</h1>
  <p>{{ report_date }} | {{ new_count }} new qualifying matches</p>

  {% for tier_name, tier_label in tiers %}
  {% if jobs_by_tier[tier_name] %}
  <h2>{{ tier_label }} ({{ jobs_by_tier[tier_name]|length }})</h2>
  {% for job in jobs_by_tier[tier_name] %}
  <div class="job {% if job.is_new %}new{% endif %}">
    <h3>{{ job.company }} — {{ job.title }}</h3>
    <p><span class="score {{ job.tier_class }}">Score: {{ job.match_score }}</span>
       | {{ job.compensation }} | {{ job.location }} ({{ job.remote_type }})
       {% if job.is_new %}<strong> [NEW]</strong>{% endif %}</p>
    <p class="label">Posted: {{ job.date_posted }} | Source: {{ job.source }}</p>
    <p><strong>Why match:</strong> {{ job.why_match }}</p>
    <p><strong>Missing:</strong> {{ job.missing_requirements }}</p>
    {% if job.risk_flags %}<p class="flag">Flags: {{ job.risk_flags|join(', ') }}</p>{% endif %}
    <p><a href="{{ job.application_url }}">Apply directly →</a></p>
  </div>
  {% endfor %}
  {% endif %}
  {% endfor %}

  {% if previous_jobs %}
  <h2>Previously Found Qualifying Jobs ({{ previous_jobs|length }})</h2>
  {% for job in previous_jobs[:20] %}
  <div class="job">
    <h3>{{ job.company }} — {{ job.title }}</h3>
    <p class="score">Score: {{ job.match_score }} | {{ job.compensation }}</p>
    <p><a href="{{ job.application_url }}">Apply →</a></p>
  </div>
  {% endfor %}
  {% endif %}

  <h2>Summary Statistics</h2>
  <div class="stats">
    <ul>
      <li>Companies searched: {{ summary.companies_searched }}</li>
      <li>Companies succeeded: {{ summary.companies_succeeded }}</li>
      <li>Companies failed: {{ summary.companies_failed }}</li>
      <li>Jobs collected: {{ summary.jobs_collected }}</li>
      <li>Jobs after deduplication: {{ summary.jobs_after_dedup }}</li>
      <li>Jobs above salary threshold: {{ summary.jobs_above_salary }}</li>
      <li>Jobs score ≥70: {{ summary.jobs_score_qualifying }}</li>
      <li>New qualifying jobs: {{ summary.new_qualifying_jobs }}</li>
    </ul>
  </div>
</body>
</html>
""")


def _job_display(job: JobRecord, is_new: bool = False) -> dict[str, Any]:
    parsed = ParsedSalary(
        salary_min=job.salary_min,
        salary_max=job.salary_max,
        salary_currency=job.salary_currency,
        salary_period=job.salary_period,
        compensation_unknown=job.compensation_unknown,
    )
    tier = job.tier()
    return {
        "company": job.company,
        "title": job.title,
        "match_score": job.match_score,
        "compensation": format_compensation(parsed),
        "location": job.location or "Unknown",
        "remote_type": job.remote_type.value if hasattr(job.remote_type, "value") else job.remote_type,
        "date_posted": str(job.date_posted) if job.date_posted else "Unknown",
        "why_match": job.why_match,
        "missing_requirements": job.missing_requirements,
        "risk_flags": job.risk_flags,
        "application_url": job.application_url,
        "source": job.source,
        "is_new": is_new,
        "tier_class": tier,
    }


def _serialize_job(job: JobRecord) -> dict[str, Any]:
    return {
        "id": job.id,
        "company": job.company,
        "title": job.title,
        "url": job.url,
        "application_url": job.application_url,
        "match_score": job.match_score,
        "score_breakdown": job.score_breakdown.to_dict(),
        "compensation_unknown": job.compensation_unknown,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "location": job.location,
        "remote_type": job.remote_type.value if hasattr(job.remote_type, "value") else job.remote_type,
        "why_match": job.why_match,
        "missing_requirements": job.missing_requirements,
        "risk_flags": job.risk_flags,
        "status": job.status.value if hasattr(job.status, "value") else job.status,
        "date_posted": str(job.date_posted) if job.date_posted else None,
    }


def generate_report(
    new_jobs: list[JobRecord],
    all_qualifying: list[JobRecord],
    summary: SearchSummary,
    report_date: date | None = None,
) -> tuple[str, str, dict[str, Any]]:
    """Generate HTML, plaintext, and JSON report data."""
    report_date = report_date or today_utc()
    sorted_all = sort_jobs(all_qualifying)
    new_ids = {j.id for j in new_jobs if j.id}

    tiers_map = {"exceptional": [], "strong": [], "good": []}
    previous: list[JobRecord] = []

    for job in sorted_all:
        display = _job_display(job, is_new=job.id in new_ids if job.id else False)
        tier = job.tier()
        if tier in tiers_map:
            tiers_map[tier].append(display)
        if job.id and job.id not in new_ids:
            previous.append(_job_display(job))

    tiers = [
        ("exceptional", "Exceptional Matches (90–100)"),
        ("strong", "Strong Matches (80–89)"),
        ("good", "Good Matches (70–79)"),
    ]

    html = HTML_TEMPLATE.render(
        report_date=report_date.isoformat(),
        new_count=len(new_jobs),
        tiers=tiers,
        jobs_by_tier=tiers_map,
        previous_jobs=previous,
        summary=summary,
    )

    text_lines = [
        f"AI Job Agent — Daily Report — {report_date.isoformat()}",
        f"{len(new_jobs)} new qualifying matches",
        "",
    ]
    for tier_name, tier_label in tiers:
        jobs_in_tier = tiers_map[tier_name]
        if jobs_in_tier:
            text_lines.append(f"=== {tier_label} ===")
            for j in jobs_in_tier:
                new_tag = " [NEW]" if j["is_new"] else ""
                text_lines.extend([
                    f"{j['company']} — {j['title']}{new_tag}",
                    f"  Score: {j['match_score']} | {j['compensation']} | {j['location']}",
                    f"  Why: {j['why_match']}",
                    f"  Apply: {j['application_url']}",
                    "",
                ])

    text_lines.append("=== Summary ===")
    text_lines.append(f"Companies searched: {summary.companies_searched}")
    text_lines.append(f"New qualifying jobs: {summary.new_qualifying_jobs}")

    json_data = {
        "report_date": report_date.isoformat(),
        "new_jobs": [_serialize_job(j) for j in new_jobs],
        "all_qualifying": [_serialize_job(j) for j in sorted_all],
        "summary": {
            "companies_searched": summary.companies_searched,
            "companies_succeeded": summary.companies_succeeded,
            "companies_failed": summary.companies_failed,
            "jobs_collected": summary.jobs_collected,
            "jobs_after_dedup": summary.jobs_after_dedup,
            "jobs_above_salary": summary.jobs_above_salary,
            "jobs_score_qualifying": summary.jobs_score_qualifying,
            "new_qualifying_jobs": summary.new_qualifying_jobs,
        },
    }

    return html, "\n".join(text_lines), json_data


def save_report(
    report_dir: str | Path,
    report_date: date,
    html: str,
    json_data: dict[str, Any],
) -> tuple[Path, Path]:
    """Save report files locally."""
    path = Path(report_dir)
    path.mkdir(parents=True, exist_ok=True)
    date_str = report_date.isoformat()
    html_path = path / f"{date_str}.html"
    json_path = path / f"{date_str}.json"
    html_path.write_text(html, encoding="utf-8")
    json_path.write_text(json.dumps(json_data, indent=2), encoding="utf-8")
    logger.info("Saved reports to %s and %s", html_path, json_path)
    return html_path, json_path
