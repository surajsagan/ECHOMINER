"""Extraction worker: claims queued jobs and sweeps expired artefacts.

Run with `python -m echominer.worker`. Stateless -- run as many as the VM allows.
"""
import logging
import signal
import time

from .config import get_settings
from .db import SessionLocal
from .logging_setup import configure_logging
from .services.jobs import JobService

log = logging.getLogger(__name__)
_running = True


def _stop(*_):
    global _running
    _running = False
    log.info("worker shutdown requested")


def main(poll_seconds: float = 2.0, purge_every: int = 150) -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    log.info("worker started")

    ticks = 0
    while _running:
        worked = False
        with SessionLocal() as db:
            service = JobService(db, settings)
            try:
                job = service.run_next()
                if job:
                    worked = True
                    log.info("job processed", extra={"extra_fields": {
                        "job_id": str(job.id), "status": job.status,
                        "records": job.record_count}})
                db.commit()
            except Exception:
                db.rollback()
                log.exception("job processing failed")

        ticks += 1
        if ticks % purge_every == 0:
            with SessionLocal() as db:
                try:
                    purged = JobService(db, settings).purge_expired()
                    db.commit()
                    if purged:
                        log.info("artefacts purged", extra={"extra_fields": {"jobs": purged}})
                except Exception:
                    db.rollback()
                    log.exception("purge sweep failed")

        if not worked:
            time.sleep(poll_seconds)


if __name__ == "__main__":
    main()
