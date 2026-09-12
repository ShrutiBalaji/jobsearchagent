"""Command-line interface for AI Job Agent."""

from __future__ import annotations

import argparse
import sys

from job_agent.config import load_config
from job_agent.database import Database
from job_agent.excel_export import rebuild_jobs_in_excel
from job_agent.normalization import filter_qualifying_jobs
from job_agent.scheduler import JobAgentPipeline
from job_agent.scoring import sort_jobs
from job_agent.utils.logging import setup_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="job_agent",
        description="AI Job Agent — automated AI/ML job search and Excel tracking",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("run", help="Search, score, and append new jobs to Excel")
    sub.add_parser("dry-run", help="Search and report without updating Excel")
    sub.add_parser("search", help="Search and store jobs in the database only")
    sub.add_parser("stats", help="Print database statistics")
    sub.add_parser(
        "export-excel",
        help="Rebuild Excel from all qualifying jobs in the database (no new search)",
    )

    return parser


def cmd_export_excel(config) -> int:
    db = Database(config.database_path)
    jobs = sort_jobs(
        filter_qualifying_jobs(
            db.get_all_qualifying_jobs(
                config.minimum_match_score,
                max_age_days=config.max_job_age_days,
                require_posting_date=config.require_posting_date,
            ),
            config,
        )
    )
    if not jobs:
        print("No qualifying jobs found in the database to export.")
        print(
            f"Try running a full search first: python -m job_agent run "
            f"(filters: score ≥{config.minimum_match_score}, "
            f"posted within {config.max_job_age_days} days)"
        )
        return 1

    written, path = rebuild_jobs_in_excel(config.excel_path, jobs)
    print(f"\nExcel tracker: {path}")
    print(f"Qualifying jobs in database: {len(jobs)}")
    print(f"Rows written this export: {written}")
    return 0


def cmd_stats(config) -> int:
    db = Database(config.database_path)
    stats = db.get_stats()
    print("\n=== AI Job Agent Statistics ===")
    print(f"Total jobs seen: {stats['total_jobs']}")
    print(f"Qualifying jobs (score ≥70): {stats['qualifying_jobs']}")
    print(f"New jobs: {stats['new_jobs']}")
    print("\nJobs by score tier:")
    for tier, count in stats["by_score"].items():
        print(f"  {tier}: {count}")
    print("\nTop companies:")
    for company, count in list(stats["by_company"].items())[:15]:
        print(f"  {company}: {count}")
    if stats["recent_failures"]:
        print("\nRecent failures:")
        for f in stats["recent_failures"][:5]:
            print(f"  {f['company']} ({f['source']}): {f['error'][:60]}")
    return 0


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        sys.exit(0)

    config = load_config()
    setup_logging(config.log_dir, config.log_level)

    if args.command == "run":
        pipeline = JobAgentPipeline(config)
        pipeline.run(mode="run")
    elif args.command == "dry-run":
        pipeline = JobAgentPipeline(config)
        pipeline.run(mode="dry-run")
    elif args.command == "search":
        pipeline = JobAgentPipeline(config)
        pipeline.run(mode="search")
    elif args.command == "stats":
        sys.exit(cmd_stats(config))
    elif args.command == "export-excel":
        sys.exit(cmd_export_excel(config))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
