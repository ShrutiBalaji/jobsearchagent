"""Email delivery for daily job reports."""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from job_agent.config import AppConfig

logger = logging.getLogger("job_agent.emailer")


def send_email(
    config: AppConfig,
    subject: str,
    html_body: str,
    text_body: str,
) -> bool:
    """Send email via SMTP. Returns True on success."""
    if not all([config.smtp_host, config.smtp_username, config.smtp_password, config.email_from]):
        logger.error("SMTP not configured — set SMTP_* and EMAIL_FROM in .env")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config.email_from
    msg["To"] = config.email_to

    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(config.smtp_username, config.smtp_password)
            server.sendmail(config.email_from, [config.email_to], msg.as_string())
        logger.info("Email sent to %s", config.email_to)
        return True
    except Exception as exc:
        logger.error("Failed to send email: %s", exc)
        return False
