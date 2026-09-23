"""Job and export surface (M5/M6)."""
import asyncio
import json
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..adapters.export import build_workbook
from ..citation import all_formats, render
from ..config import Settings, get_settings
from ..db import SessionLocal, get_db
from ..services.jobs import IncomingFile, JobNotFound, JobService, UploadRejected
from .deps import client_ip, current_user

router = APIRouter(prefix="/api/v1", tags=["jobs"])


def get_jobs(db: Annotated[Session, Depends(get_db)],
             settings: Annotated[Settings, Depends(get_settings)]) -> JobService:
    return JobService(db, settings)


def _job_state(job, service: JobService) -> dict:
    return {
        "id": str(job.id),
        "status": job.status,
        "file_count": job.file_count,
        "record_count": job.record_count,
        "engine_version": job.engine_version,
        "files": service.file_summaries(job),
        "purged": job.purged_at is not None,
    }


@router.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
async def submit_job(request: Request, files: list[UploadFile] = File(...),
                     user=Depends(current_user),
                     service: JobService = Depends(get_jobs),
                     settings: Settings = Depends(get_settings)):
    if len(files) > settings.max_files_per_job:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE,
                            f"a maximum of {settings.max_files_per_job} files can be uploaded at once")
    incoming = [IncomingFile(filename=f.filename or "upload.pdf", content=await f.read()) for f in files]
    try:
        job = service.submit(user_id=user.id, files=incoming, ip=client_ip(request))
    except UploadRejected as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return {"id": str(job.id), "status": job.status, "file_count": job.file_count}


@router.get("/jobs/{job_id}")
def job_status(job_id: str, user=Depends(current_user), service: JobService = Depends(get_jobs)):
    try:
        job = service.get_owned(job_id, user.id)
    except JobNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")
    return _job_state(job, service)


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str, user=Depends(current_user),
                     settings: Settings = Depends(get_settings)):
    """Server-sent progress. Each tick opens its own short-lived session so a
    long-lived stream never holds a pooled connection open."""
    user_id = user.id

    async def stream():
        terminal = {"completed", "partial", "failed", "purged"}
        for _ in range(600):  # ~10 minutes at 1s
            with SessionLocal() as db:
                service = JobService(db, settings)
                try:
                    job = service.get_owned(job_id, user_id)
                except JobNotFound:
                    yield f"event: error\ndata: {json.dumps({'error': 'not found'})}\n\n"
                    return
                payload = _job_state(job, service)
            yield f"data: {json.dumps(payload)}\n\n"
            if payload["status"] in terminal:
                return
            await asyncio.sleep(1)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/jobs/{job_id}/preview")
def job_preview(job_id: str, limit: int = 50, offset: int = 0,
                user=Depends(current_user), service: JobService = Depends(get_jobs)):
    try:
        job = service.get_owned(job_id, user.id)
    except JobNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")
    rows, columns = service.rows_for(job)
    limit = max(1, min(limit, 200))
    return {"columns": columns, "total": len(rows), "rows": rows[offset:offset + limit]}


@router.get("/jobs/{job_id}/export.xlsx")
def export_job(job_id: str, user=Depends(current_user), service: JobService = Depends(get_jobs)):
    try:
        job = service.get_owned(job_id, user.id)
    except JobNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")
    if job.purged_at:
        raise HTTPException(status.HTTP_410_GONE, "this job's data has been removed")
    if job.status not in ("completed", "partial"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"job is {job.status}")

    rows, columns = service.rows_for(job)
    content = build_workbook(rows=rows, columns=columns, job_id=str(job.id),
                             engine_version=job.engine_version,
                             dictionary_version=job.dictionary_version,
                             file_summaries=service.file_summaries(job))
    # Artefacts are removed as soon as the download succeeds.
    service.record_download(job, user_id=user.id, size=len(content))
    filename = f"echominer_{str(job.id)[:8]}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.delete("/jobs/{job_id}")
def delete_job(job_id: str, user=Depends(current_user), service: JobService = Depends(get_jobs)):
    try:
        job = service.get_owned(job_id, user.id)
    except JobNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")
    service.purge(job, reason="user_requested")
    return {"status": "purged"}


@router.get("/citation")
def citation(format: str | None = None):
    if format is None:
        return all_formats()
    try:
        return {"format": format, "text": render(format)}
    except KeyError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "format must be one of: apa, vancouver, ieee, bibtex, ris")
