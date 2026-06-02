"""
scheduler_init.py — APScheduler setup for 6-hourly corpus refresh.
Cron fires at: 00:00, 06:00, 12:00, 18:00 IST daily.
Designed to start once per Streamlit app session via st.session_state guard.
"""

import logging
import threading
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from scheduler.refresh_job import run_refresh_job

logger = logging.getLogger(__name__)

# ── Singleton scheduler (module-level) ────────────────────────────────────────
# We use a threading lock to prevent double-initialization in Streamlit's
# multi-thread environment (Streamlit re-runs the script on every interaction).
_scheduler: BackgroundScheduler | None = None
_lock = threading.Lock()


def get_scheduler_status() -> dict:
    """
    Return current scheduler status for display in the UI sidebar.

    Returns dict with:
        running:    bool
        next_run:   ISO string of next scheduled run (or None)
        last_run:   Not tracked here; read from logs/refresh.log for accuracy.
    """
    global _scheduler
    if _scheduler is None or not _scheduler.running:
        return {"running": False, "next_run": None}

    jobs = _scheduler.get_jobs()
    next_run = None
    if jobs:
        next_run_time = jobs[0].next_run_time
        if next_run_time:
            next_run = next_run_time.isoformat()

    return {"running": True, "next_run": next_run}


def start_scheduler() -> BackgroundScheduler:
    """
    Start the APScheduler BackgroundScheduler if not already running.
    Safe to call multiple times — idempotent due to threading lock.

    Cron: 0 0,6,12,18 * * *  →  fires at 00:00, 06:00, 12:00, 18:00 daily.

    Returns:
        The running BackgroundScheduler instance.
    """
    global _scheduler

    with _lock:
        if _scheduler is not None and _scheduler.running:
            logger.debug("Scheduler already running — skipping re-init.")
            return _scheduler

        logger.info("Initialising APScheduler (6-hourly corpus refresh) ...")

        _scheduler = BackgroundScheduler(
            job_defaults={"misfire_grace_time": 3600},  # 1-hour grace if app was down
            timezone="Asia/Kolkata",
        )

        _scheduler.add_job(
            func=run_refresh_job,
            trigger=CronTrigger(hour="0,6,12,18", minute=0, timezone="Asia/Kolkata"),
            id="corpus_refresh",
            name="MF FAQ Corpus Refresh (6h)",
            replace_existing=True,
        )

        _scheduler.start()
        logger.info(
            f"Scheduler started. Next run: "
            f"{_scheduler.get_jobs()[0].next_run_time}"
        )

    return _scheduler


def stop_scheduler():
    """Gracefully stop the scheduler (called on app shutdown if needed)."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
