"""
refresh_job.py — Wraps the ingestion pipeline as an APScheduler-compatible job.
Called by scheduler_init.py on the configured cron schedule.
"""

import logging
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def run_refresh_job():
    """
    Entry point for the scheduled corpus refresh.
    Imports and runs the ingestion pipeline, logs outcome.
    """
    started = datetime.now(timezone.utc).isoformat()
    logger.info(f"Scheduled refresh triggered at {started}")

    try:
        # Import here to avoid circular imports at module load time
        from ingestion.ingest import run_ingestion
        summary = run_ingestion(dry_run=False)
        logger.info(f"Refresh completed successfully: {summary}")
        return summary

    except Exception as exc:
        logger.error(f"Refresh job failed: {exc}", exc_info=True)
        return {"error": str(exc), "started_at": started}
