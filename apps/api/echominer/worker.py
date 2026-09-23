"""Extraction worker: claims queued jobs and sweeps expired artefacts.

Two ways to run it:
  * its own process -- `python -m echominer.worker` (VM / docker-compose);
  * a thread inside the API process -- EMBEDDED_WORKER=true (single-service
    hosting such as Render's free tier, which has no background workers).

A job submission calls `notify()`, so an embedded worker starts at once instead
of waiting for the next poll. Idle polling can therefore be slow, which keeps a
scale-to-zero database (Neon) asleep when nobody is using the site.
"""
import logging
import signal
import threading
import time

from .config import get_settings
from .db import SessionLocal
from .logging_setup import configure_logging
from .services.jobs import JobService

log = logging.getLogger(__name__)

_wake = threading.Event()


def notify() -> None:
    """Wake an embedded worker immediately (no-op for a separate process)."""
    _wake.set()


def process_one(settings) -> bool:
    """Claim and run one queued job. Returns True if a job was processed."""
    with SessionLocal() as db:
        service = JobService(db, settings)
        try:
            job = service.run_next()
            db.commit()
        except Exception:
            db.rollback()
            log.exception("job processing failed")
            return False
    if job:
        log.info("job processed", extra={"extra_fields": {
            "job_id": str(job.id), "status": job.status, "records": job.record_count}})
    return job is not None


def purge_sweep(settings) -> None:
    with SessionLocal() as db:
        try:
            purged = JobService(db, settings).purge_expired()
            db.commit()
            if purged:
                log.info("artefacts purged", extra={"extra_fields": {"jobs": purged}})
        except Exception:
            db.rollback()
            log.exception("purge sweep failed")


def run(stop: threading.Event, settings=None) -> None:
    settings = settings or get_settings()
    last_purge = time.monotonic()
    log.info("worker started")
    while not stop.is_set():
        worked = process_one(settings)
        if time.monotonic() - last_purge >= settings.purge_interval_seconds:
            purge_sweep(settings)
            last_purge = time.monotonic()
        if not worked:
            _wake.wait(settings.worker_poll_seconds)
            _wake.clear()
    log.info("worker stopped")


def start_embedded(settings=None) -> tuple[threading.Thread, threading.Event]:
    stop = threading.Event()
    thread = threading.Thread(target=run, args=(stop, settings), name="echominer-worker", daemon=True)
    thread.start()
    return thread, stop


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    stop = threading.Event()

    def _stop(*_):
        log.info("worker shutdown requested")
        stop.set()
        _wake.set()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    run(stop, settings)


if __name__ == "__main__":
    main()
