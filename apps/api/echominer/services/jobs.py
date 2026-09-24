"""Extraction job lifecycle (M5).

Queue: PostgreSQL row-claiming with FOR UPDATE SKIP LOCKED rather than a broker.
On a single free VM this removes an entire moving part -- jobs survive a restart
because they live in the database that is already backed up, and there is no
second system to monitor. Rate limiting is done by nginx.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

import pymupdf

from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from ..adapters.blob import LocalSpool
from ..adapters.extraction import (DocumentTooLarge, UnparseableDocument,
                                   ValidatedPipelineEngine)
from ..config import Settings
from ..models import AuditEvent, Download, ExtractionJob, ExtractionRecord, JobFile
from ..security import expires_in, now

log = logging.getLogger(__name__)

PDF_MAGIC = b"%PDF-"
# Structures a report PDF has no reason to contain. Rejected before the parser
# is handed the file. (Virus scanning was removed by ruling; this is the part
# that actually matters for a PDF parser and costs nothing.)
DANGEROUS_MARKERS = (b"/JavaScript", b"/JS", b"/Launch", b"/EmbeddedFile", b"/OpenAction")


class UploadRejected(Exception):
    pass


class JobNotFound(Exception):
    pass


@dataclass
class IncomingFile:
    filename: str
    content: bytes


class JobService:
    def __init__(self, db: Session, settings: Settings, spool: LocalSpool | None = None,
                 engine: ValidatedPipelineEngine | None = None):
        self.db = db
        self.settings = settings
        self.spool = spool or LocalSpool(settings.spool_dir)
        self.engine = engine or ValidatedPipelineEngine(max_pages=settings.max_pages_per_file)

    # -- validation ------------------------------------------------------
    def _validate(self, files: Sequence[IncomingFile]) -> None:
        if not files:
            raise UploadRejected("no files were uploaded")
        if len(files) > self.settings.max_files_per_job:
            raise UploadRejected(
                f"a maximum of {self.settings.max_files_per_job} files can be uploaded at once")
        total = sum(len(f.content) for f in files)
        if total > self.settings.max_job_bytes:
            raise UploadRejected(
                f"total upload exceeds {self.settings.max_job_bytes // (1024 * 1024)} MB")
        for f in files:
            if not f.filename.lower().endswith(".pdf"):
                raise UploadRejected(f"{f.filename}: only PDF files are accepted")
            if not f.content.startswith(PDF_MAGIC):
                raise UploadRejected(f"{f.filename}: not a valid PDF")
            head = f.content[:2_000_000]
            for marker in DANGEROUS_MARKERS:
                if marker in head:
                    raise UploadRejected(
                        f"{f.filename}: contains active content ({marker.decode()}) and was rejected")

        # Page counts are read from the PDF structure only (no text extraction),
        # so this check is cheap even for very large archives.
        pages: list[tuple[str, int]] = []
        for f in files:
            try:
                with pymupdf.open(stream=f.content, filetype="pdf") as doc:
                    pages.append((f.filename, doc.page_count))
            except Exception:
                raise UploadRejected(f"{f.filename}: the PDF could not be opened")
        per_file = self.settings.max_pages_per_file
        for name, n in pages:
            if per_file and n > per_file:
                raise UploadRejected(
                    f"{name} has {n:,} pages; the limit is {per_file:,} pages per file. "
                    "Split it into smaller PDFs and upload them separately.")
        per_job = self.settings.max_pages_per_job
        total_pages = sum(n for _, n in pages)
        if per_job and total_pages > per_job:
            raise UploadRejected(
                f"these files have {total_pages:,} pages in total; this server accepts up to "
                f"{per_job:,} pages per submission. Upload fewer files at a time "
                "(for example one quarterly archive per submission).")

    # -- submission ------------------------------------------------------
    def submit(self, *, user_id, files: Sequence[IncomingFile], ip: str | None = None) -> ExtractionJob:
        self._validate(files)
        job = ExtractionJob(
            user_id=user_id, status="queued", file_count=len(files),
            total_bytes=sum(len(f.content) for f in files),
            engine_version=self.engine.version,
            dictionary_version=self.engine.dictionary_version,
            purge_after=expires_in(self.settings.artefact_ttl_seconds))
        self.db.add(job)
        self.db.flush()

        for f in files:
            record = JobFile(
                job_id=job.id, original_filename=f.filename[:400],
                sha256=hashlib.sha256(f.content).digest(),
                size_bytes=len(f.content), status="queued")
            self.db.add(record)
            self.db.flush()
            self.spool.put(job.id, record.id, f.content)

        self.db.add(AuditEvent(actor_type="user", actor_id=user_id, action="job.submitted",
                               target_type="job", target_id=str(job.id), ip=ip,
                               metadata_json={"files": len(files)}))
        self.db.flush()
        return job

    # -- processing ------------------------------------------------------
    def claim_next(self) -> ExtractionJob | None:
        """Atomically take one queued job. SKIP LOCKED lets several workers run
        without coordinating; SQLite (tests) falls back to a plain select."""
        stmt = select(ExtractionJob).where(ExtractionJob.status == "queued").order_by(
            ExtractionJob.created_at).limit(1)
        try:
            job = self.db.scalars(stmt.with_for_update(skip_locked=True)).first()
        except (OperationalError, NotImplementedError):
            job = self.db.scalars(stmt).first()
        if job is None:
            return None
        job.status = "running"
        job.started_at = now()
        self.db.flush()
        return job

    def process(self, job: ExtractionJob) -> ExtractionJob:
        files = self.db.scalars(select(JobFile).where(JobFile.job_id == job.id)
                                .order_by(JobFile.original_filename)).all()
        total_records = 0
        failures = 0

        for jf in files:
            path = self.spool.path(job.id, jf.id)
            try:
                result = self.engine.extract(path, filename=jf.original_filename)
            except (UnparseableDocument, DocumentTooLarge) as exc:
                jf.status = "failed"
                jf.error_code = type(exc).__name__
                jf.warnings = str(exc)[:2000]
                failures += 1
                continue
            except Exception as exc:  # pragma: no cover - defensive
                log.exception("extraction crashed")
                jf.status = "failed"
                jf.error_code = "EngineError"
                jf.warnings = str(exc)[:2000]
                failures += 1
                continue

            jf.status = "extracted"
            jf.page_count = result.page_count
            jf.record_count = result.record_count
            jf.blank_row_count = result.blank_row_count
            jf.header_count = result.header_count
            jf.warnings = "; ".join(result.warnings)[:2000] or None

            for seq, row in enumerate(result.rows, start=1):
                self.db.add(ExtractionRecord(
                    job_id=job.id, file_id=jf.id, seq=seq,
                    payload={"__columns__": result.columns, **row},
                    dictionary_version=self.engine.dictionary_version,
                    completeness=_completeness(row)))
            total_records += result.record_count

        job.record_count = total_records
        job.finished_at = now()
        if failures == len(files):
            job.status = "failed"
            job.error_code = "all_files_failed"
        elif failures:
            job.status = "partial"
        else:
            job.status = "completed"
        job.purge_after = expires_in(self.settings.artefact_ttl_seconds)
        self.db.flush()
        return job

    def run_next(self) -> ExtractionJob | None:
        job = self.claim_next()
        return self.process(job) if job else None

    # -- reading ---------------------------------------------------------
    def get_owned(self, job_id, user_id) -> ExtractionJob:
        job = self.db.get(ExtractionJob, job_id)
        # 404 rather than 403: a job belonging to another user must not be
        # confirmed to exist.
        if job is None or job.user_id != user_id:
            raise JobNotFound(str(job_id))
        return job

    def rows_for(self, job: ExtractionJob) -> tuple[list[dict], list[str]]:
        # Ordered by filename then record sequence. Ordering by file_id would
        # follow random UUIDs, so the same upload could produce differently
        # ordered rows on two runs -- which breaks reproducibility of an export.
        records = self.db.scalars(
            select(ExtractionRecord)
            .join(JobFile, JobFile.id == ExtractionRecord.file_id)
            .where(ExtractionRecord.job_id == job.id)
            .order_by(JobFile.original_filename, ExtractionRecord.seq)).all()
        columns: list[str] = []
        rows: list[dict] = []
        for rec in records:
            payload = dict(rec.payload)
            cols = payload.pop("__columns__", [])
            if cols and not columns:
                columns = list(cols)
            rows.append(payload)
        return rows, columns

    def file_summaries(self, job: ExtractionJob) -> list[dict]:
        files = self.db.scalars(select(JobFile).where(JobFile.job_id == job.id)
                                .order_by(JobFile.original_filename)).all()
        return [{"filename": f.original_filename, "pages": f.page_count,
                 "header_count": f.header_count, "record_count": f.record_count,
                 "blank_row_count": f.blank_row_count, "status": f.status,
                 "warnings": f.warnings} for f in files]

    # -- download & purge ------------------------------------------------
    def record_download(self, job: ExtractionJob, *, user_id, size: int, fmt: str = "xlsx") -> None:
        self.db.add(Download(job_id=job.id, user_id=user_id, format=fmt, bytes=size))
        self.db.add(AuditEvent(actor_type="user", actor_id=user_id, action="job.downloaded",
                               target_type="job", target_id=str(job.id)))
        self.purge(job, reason="downloaded")

    def purge(self, job: ExtractionJob, *, reason: str) -> int:
        """Remove staged PDFs and extracted rows. Job metadata and audit trail
        survive, so usage statistics remain intact and nothing that could
        reconstruct a report does."""
        if job.purged_at:
            return 0
        removed = self.spool.purge(job.id)
        deleted = 0
        for rec in self.db.scalars(
                select(ExtractionRecord).where(ExtractionRecord.job_id == job.id)).all():
            self.db.delete(rec)
            deleted += 1
        job.purged_at = now()
        job.status = "purged" if job.status in ("completed", "partial") else job.status
        self.db.add(AuditEvent(actor_type="system", action="job.purged", target_type="job",
                               target_id=str(job.id),
                               metadata_json={"reason": reason, "files": removed, "rows": deleted}))
        self.db.flush()
        return deleted

    def purge_expired(self, cutoff: datetime | None = None) -> int:
        """Sweeper for abandoned jobs -- the user who closes the tab without
        downloading. Runs every few minutes; purge lag is an alerting metric."""
        cutoff = cutoff or now()
        stale = self.db.scalars(
            select(ExtractionJob).where(ExtractionJob.purged_at.is_(None),
                                        ExtractionJob.purge_after.is_not(None),
                                        ExtractionJob.purge_after <= cutoff)).all()
        for job in stale:
            self.purge(job, reason="ttl_expired")
        return len(stale)


def _completeness(row: dict) -> float:
    if not row:
        return 0.0
    filled = sum(1 for v in row.values() if str(v).strip() != "")
    return round(100.0 * filled / len(row), 1)
