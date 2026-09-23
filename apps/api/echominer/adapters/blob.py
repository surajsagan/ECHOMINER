"""Staging store. Files live in tmpfs for the life of a job and are unlinked on
purge, so an uploaded report never reaches the block volume."""
from __future__ import annotations
import shutil
from pathlib import Path


class LocalSpool:
    def __init__(self, root: str | Path = "/var/echominer/spool"):
        self.root = Path(root)

    def job_dir(self, job_id) -> Path:
        return self.root / str(job_id)

    def put(self, job_id, file_id, data: bytes) -> Path:
        d = self.job_dir(job_id)
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"{file_id}.pdf"
        path.write_bytes(data)
        path.chmod(0o600)
        return path

    def path(self, job_id, file_id) -> Path:
        return self.job_dir(job_id) / f"{file_id}.pdf"

    def purge(self, job_id) -> int:
        d = self.job_dir(job_id)
        if not d.exists():
            return 0
        count = len(list(d.glob("*.pdf")))
        shutil.rmtree(d, ignore_errors=True)
        return count
