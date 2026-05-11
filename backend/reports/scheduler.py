"""
Report Scheduler — two triggers:
  1. Daily 8 AM IST (02:30 UTC): generates a "last 7 days" summary report
  2. Spike detection every 6 hours: if post volume > threshold, generate alert report

Also handles email + webhook notification after report is generated.
"""
import asyncio
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from loguru import logger

from backend.config import settings
from backend.sync.mysql_connector import MySQLConnector
from backend.reports.store import init_db, list_reports, mark_notified, get_report

IST = timezone(timedelta(hours=5, minutes=30))
DAILY_REPORT_HOUR_IST = 8   # 8 AM IST


class ReportScheduler:
    def __init__(self, generator):
        self.generator = generator
        self.mysql = MySQLConnector()

    # ─── Main loop ────────────────────────────────────────────────────────────

    async def run_forever(self):
        init_db()
        logger.info("Report scheduler started")
        while True:
            try:
                await self._daily_check()
                await self._spike_check()
                await self._notify_pending()
            except Exception as e:
                logger.error(f"Scheduler cycle error: {e}")
            await asyncio.sleep(3600)   # check every hour

    # ─── Daily report ─────────────────────────────────────────────────────────

    async def _daily_check(self):
        now_ist = datetime.now(IST)
        if now_ist.hour != DAILY_REPORT_HOUR_IST:
            return

        # Avoid duplicate: check if we already generated a report today
        today = now_ist.strftime("%Y-%m-%d")
        existing = [r for r in list_reports(5) if r["from_date"] and r["from_date"] >= today]
        if existing:
            return

        to_date = now_ist.strftime("%Y-%m-%d")
        from_date = (now_ist - timedelta(days=7)).strftime("%Y-%m-%d")
        title = f"साप्ताहिक सोशल मीडिया इंटेलिजेंस रिपोर्ट — {to_date}"

        logger.info(f"Generating daily report: {title}")
        report_id = await self.generator.generate(
            title=title, from_date=from_date, to_date=to_date, trigger="daily"
        )
        logger.info(f"Daily report generated: {report_id}")

    # ─── Spike detection ──────────────────────────────────────────────────────

    async def _spike_check(self):
        threshold = settings.SPIKE_THRESHOLD
        is_spike, count = self.mysql.check_spike(hours=6, threshold=threshold)
        if not is_spike:
            return

        # Avoid duplicate spike reports within 12 hours
        twelve_hours_ago = (datetime.utcnow() - timedelta(hours=12)).isoformat()
        recent = [r for r in list_reports(10)
                  if r.get("trigger") == "spike" and r.get("created_at", "") >= twelve_hours_ago]
        if recent:
            return

        now = datetime.utcnow()
        to_date = now.strftime("%Y-%m-%d %H:%M:%S")
        from_date = (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        title = f"⚠️ Spike Alert — {count} posts in last 6 hours ({now.strftime('%d %b %Y')})"

        logger.warning(f"Spike detected: {count} posts in 6h. Generating alert report.")
        report_id = await self.generator.generate(
            title=title, from_date=from_date, to_date=to_date, trigger="spike"
        )
        logger.info(f"Spike report generated: {report_id}")

    # ─── Notification ─────────────────────────────────────────────────────────

    async def _notify_pending(self):
        """Send email for completed reports that haven't been notified yet."""
        if not settings.REPORT_EMAIL_RECIPIENTS:
            return
        for report in list_reports(10):
            if report["status"] == "completed" and not report.get("notified_at"):
                full = get_report(report["report_id"])
                if full and full.get("html"):
                    self._send_email(full)
                    mark_notified(report["report_id"])

    def _send_email(self, report: dict):
        recipients = settings.REPORT_EMAIL_RECIPIENTS
        if not recipients or not settings.SMTP_USER:
            logger.info(f"Email not configured — skipping notification for {report['report_id']}")
            return

        subject = f"[PHQ Intelligence] {report['title']}"
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_USER
        msg["To"] = ", ".join(recipients)
        msg.attach(MIMEText(report["html"], "html", "utf-8"))

        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_USER, recipients, msg.as_string())
            logger.info(f"Email sent for report {report['report_id']} to {recipients}")
        except Exception as e:
            logger.error(f"Email send failed: {e}")
