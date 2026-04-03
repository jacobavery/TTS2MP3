"""In-memory async job queue with SSE progress streaming."""
from __future__ import annotations

import asyncio
import os
import shutil
import time
import uuid
from dataclasses import dataclass, field

from .config import JOBS_DIR, JOB_TTL_SECONDS


@dataclass
class Job:
    id: str
    status: str = "pending"  # pending, running, done, error
    progress: int = 0
    error: str | None = None
    output_path: str | None = None
    output_filename: str | None = None
    created_at: float = field(default_factory=time.time)
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue())


class JobManager:
    def __init__(self, max_concurrent: int = 3):
        self.jobs: dict[str, Job] = {}
        self.semaphore = asyncio.Semaphore(max_concurrent)

    def create_job(self, output_filename: str = "output.mp3") -> Job:
        job_id = uuid.uuid4().hex[:12]
        job_dir = os.path.join(JOBS_DIR, job_id)
        os.makedirs(job_dir, exist_ok=True)
        output_path = os.path.join(job_dir, output_filename)
        job = Job(id=job_id, output_path=output_path, output_filename=output_filename)
        self.jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def make_progress_cb(self, job: Job, loop: asyncio.AbstractEventLoop):
        """Return a sync callback that pushes progress to the job's async queue."""
        def cb(pct: int):
            job.progress = pct
            loop.call_soon_threadsafe(job.queue.put_nowait, {"pct": pct})
        return cb

    def cleanup_expired(self):
        """Remove jobs older than TTL."""
        now = time.time()
        expired = [
            jid for jid, j in self.jobs.items()
            if now - j.created_at > JOB_TTL_SECONDS
        ]
        for jid in expired:
            job = self.jobs.pop(jid, None)
            if job and job.output_path:
                job_dir = os.path.dirname(job.output_path)
                if os.path.isdir(job_dir):
                    shutil.rmtree(job_dir, ignore_errors=True)
