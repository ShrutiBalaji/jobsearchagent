# AI Job Agent

Automated AI/ML job search agent that searches company career pages and public ATS APIs, scores jobs against your profile, deduplicates results, and appends new matches to a persistent Excel tracker.

**This tool never auto-applies to jobs.** It is strictly for discovery, scoring, and tracking.

## Features

- Multi-source job search (Greenhouse, Lever, Ashby, Workday, SmartRecruiters, Workable, company pages)
- 80+ pre-configured target companies across frontier AI, big tech, healthcare AI, fintech, and startups
- Deterministic 0–100 match scoring with transparent breakdown
- Compensation parsing and $100k+ filtering (when compensation is listed)
- SQLite persistence with deduplication and NEW/SEEN/UPDATED tracking
- **Persistent Excel tracker** at `reports/ai_job_matches.xlsx` (appends new jobs each run)
- Jobs posted within the last 7 days (when a posting date is available)
- Optional LLM-enhanced fit analysis (disabled by default)

## Quick Start

### 1. Install Python

Install Python 3.10 or newer from [python.org](https://www.python.org/downloads/) or via Homebrew:

```bash
brew install python@3.11
```

Verify:

```bash
python3 --version
```

### 2. Clone and enter the project

```bash
cd /path/to/jobsearchagent
```

### 3. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate   # Mac/Linux
# .venv\Scripts\activate    # Windows
```

### 4. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

### 5. Run a dry test (preview only)

```bash
python -m job_agent dry-run
```

This searches companies, scores jobs, and saves HTML/JSON reports to `reports/` — but does **not** update the Excel file.

### 6. Run the daily job search

```bash
python -m job_agent run
```

This searches all companies, scores jobs, and **appends new qualifying jobs** to:

```
reports/ai_job_matches.xlsx
```

### Excel columns

| Column | Description |
|--------|-------------|
| Company name | Employer |
| URL to apply | Direct application link |
| Role name | Job title |
| Salary | Listed compensation, or "Not listed" |
| Match score | 0–100 fit score |
| Location | City / remote info |
| Date posted | When the job was posted (if available) |
| Applied | **Empty for you to fill in** after applying |

**Each daily run appends only new jobs** — duplicates (same application URL) are skipped automatically. Your existing rows and your "Applied" notes are preserved.

No `.env` file or email setup is required.

## CLI Commands

| Command | Description |
|---------|-------------|
| `python -m job_agent run` | Search, score, append new jobs to Excel |
| `python -m job_agent dry-run` | Search and report without updating Excel |
| `python -m job_agent search` | Search and store in database only |
| `python -m job_agent stats` | Print database statistics |
| `python -m job_agent --help` | Show help |

## Configuration

All configuration lives in `config/`:

| File | Purpose |
|------|---------|
| `config/companies.yaml` | Target companies, ATS types, career URLs |
| `config/keywords.yaml` | Role keywords, tech stack, exclusions |
| `config/settings.yaml` | Salary threshold, match score, 7-day freshness filter, discovery toggle |

### Add or remove companies

Edit `config/companies.yaml`:

```yaml
companies:
  - name: New Company
    priority: B          # A=dream, B=high, C=strong, D=other
    category: frontier_ai
    ats: greenhouse      # greenhouse | lever | ashby | workday | smartrecruiters | company_page
    board_token: newco   # for Greenhouse
```

### Change salary threshold

In `config/settings.yaml`:

```yaml
salary_threshold: 100000
```

### Change match score threshold

```yaml
minimum_match_score: 70
```

### Disable company discovery

```yaml
discovery_enabled: false
```

## GitHub Actions Setup

The workflow at `.github/workflows/job_agent.yml` runs daily at approximately 8:00 AM Eastern Time.

> **Note:** GitHub Actions cron schedules use UTC and can be delayed by 15–60+ minutes during high load.

### 1. Push this repo to GitHub

```bash
git init
git add .
git commit -m "Add AI Job Agent"
git remote add origin https://github.com/YOUR_USER/jobsearchagent.git
git push -u origin main
```

### 2. Add repository secrets

Go to **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Example |
|--------|---------|
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USERNAME` | `your.email@gmail.com` |
| `SMTP_PASSWORD` | your app password |
| `EMAIL_FROM` | `your.email@gmail.com` |
| `EMAIL_TO` | `shrutibalaji17@gmail.com` |

### 3. Enable the workflow

The workflow runs automatically on the cron schedule. You can also trigger it manually from the **Actions** tab → **AI Job Agent Daily** → **Run workflow**.

### Database persistence on GitHub Actions

The workflow uses GitHub Actions cache to persist `jobs.db` between runs so job history and deduplication carry forward.

## Local Cron (Mac/Linux)

To run daily on your own machine instead of GitHub Actions:

```bash
crontab -e
```

Add (runs at 8:00 AM local time):

```cron
0 8 * * * cd /path/to/jobsearchagent && .venv/bin/python -m job_agent run >> logs/cron.log 2>&1
```

## Project Structure

```
job_agent/           # Main Python package
  sources/           # ATS adapters (Greenhouse, Lever, Ashby, etc.)
  utils/             # HTTP, salary, URLs, dates, logging
config/              # YAML configuration
tests/               # Unit tests
reports/             # Generated daily reports
logs/                # Application logs
.github/workflows/   # GitHub Actions
```

## Scoring

Jobs are scored 0–100 using weighted categories:

| Category | Weight |
|----------|--------|
| Technical stack match | 25% |
| Production AI engineering | 20% |
| Role/title match | 15% |
| Computer vision / medical AI | 10% |
| LLM / GenAI / multimodal | 10% |
| Systems / infrastructure | 10% |
| Experience level | 5% |
| Compensation | 5% |

Only jobs scoring **≥ 70** are included in reports.

## Troubleshooting

### No jobs found

- Some company APIs may be temporarily unavailable — check `logs/job_agent.log`
- Run `python -m job_agent stats` to see recent source failures
- Big tech career pages use generic scraping and may return fewer results

### Email not sending

- Verify `.env` SMTP settings
- For Gmail, use an App Password (not your regular password)
- Run `python -m job_agent test-email` to isolate the issue

### SMTP authentication error

- Confirm 2FA is enabled and you're using an App Password
- Check that `SMTP_PORT=587` with STARTTLS

### Permission / robots.txt errors

- The agent respects robots.txt and will skip blocked pages
- This is expected for some career sites

### View logs

```bash
tail -f logs/job_agent.log
```

## Optional LLM Scoring

Set in `.env` to enable nuanced fit analysis (does not override hard filters):

```env
LLM_PROVIDER=openai
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
```

## Security

- No auto-apply functionality exists in this codebase
- Credentials are loaded from environment variables only
- `.env` is gitignored
- Passwords are never logged

## Running Tests

```bash
pytest
```

## License

MIT
