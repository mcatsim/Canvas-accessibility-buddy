"""Scan queue manager -- sequential per API key, parallel across keys.

Each API key gets its own asyncio worker coroutine. Jobs for the same
key are processed in FIFO order. Different keys run concurrently.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class QueuedJob:
    job_id: str
    user_id: str
    api_key_id: str
    canvas_url: str
    course_id: int
    course_name: str
    status: str = "queued"  # queued, running, complete, failed, cancelled
    progress_pct: int = 0
    current_phase: str | None = None
    current_item: str | None = None
    items_total: int = 0
    items_checked: int = 0
    issues_found: int = 0
    error: str | None = None
    progress_log: list[dict[str, Any]] = field(default_factory=list)
    db_session_factory: Any = None
    decrypt_fn: Callable | None = None
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ScanQueueManager:
    """Manages scan execution with per-key sequential processing."""

    def __init__(self) -> None:
        self._jobs: dict[str, QueuedJob] = {}
        self._key_queues: dict[str, asyncio.Queue[str]] = {}
        self._workers: dict[str, asyncio.Task] = {}

    async def enqueue(
        self,
        user_id: str,
        api_key_id: str,
        canvas_url: str,
        course_id: int,
        course_name: str,
        db_session_factory: Any,
        decrypt_fn: Callable,
    ) -> str:
        """Add a scan job to the queue. Returns job_id."""
        job_id = uuid.uuid4().hex[:12]
        job = QueuedJob(
            job_id=job_id,
            user_id=user_id,
            api_key_id=api_key_id,
            canvas_url=canvas_url,
            course_id=course_id,
            course_name=course_name,
            db_session_factory=db_session_factory,
            decrypt_fn=decrypt_fn,
        )
        self._jobs[job_id] = job

        # Ensure a queue + worker exists for this key
        if api_key_id not in self._key_queues:
            self._key_queues[api_key_id] = asyncio.Queue()
            self._workers[api_key_id] = asyncio.create_task(
                self._worker_loop(api_key_id)
            )

        await self._key_queues[api_key_id].put(job_id)
        logger.info(
            "Enqueued job %s for key %s (course %d)",
            job_id, api_key_id[:8], course_id,
        )
        return job_id

    async def _worker_loop(self, api_key_id: str) -> None:
        """Process jobs for a single API key sequentially."""
        queue = self._key_queues[api_key_id]
        while True:
            job_id = await queue.get()
            job = self._jobs.get(job_id)
            if not job or job.status == "cancelled":
                queue.task_done()
                continue
            try:
                job.status = "running"
                await self._execute_job(job_id)
            except Exception as exc:
                logger.exception("Job %s failed", job_id)
                if job_id in self._jobs:
                    self._jobs[job_id].status = "failed"
                    self._jobs[job_id].error = str(exc)
            finally:
                queue.task_done()

    async def _execute_job(self, job_id: str, **kwargs: Any) -> None:
        """Run the actual audit. Override in tests."""
        # Real implementation will call audit_runner.run_audit()
        # This is a placeholder -- Task 13 will wire it up
        job = self._jobs[job_id]
        job.status = "complete"

    def get_job_status(self, job_id: str) -> dict[str, Any] | None:
        """Get current status of a job."""
        job = self._jobs.get(job_id)
        if not job:
            return None
        return {
            "job_id": job.job_id,
            "status": job.status,
            "course_id": job.course_id,
            "course_name": job.course_name,
            "progress_pct": job.progress_pct,
            "current_phase": job.current_phase,
            "current_item": job.current_item,
            "items_total": job.items_total,
            "items_checked": job.items_checked,
            "issues_found": job.issues_found,
            "error": job.error,
        }

    def cancel(self, job_id: str) -> bool:
        """Cancel a job. Returns True if cancelled."""
        job = self._jobs.get(job_id)
        if not job:
            return False
        if job.status in ("complete", "failed"):
            return False
        job.status = "cancelled"
        job.cancel_event.set()
        return True

    def get_user_jobs(self, user_id: str) -> list[dict[str, Any]]:
        """Get all jobs for a user."""
        return [
            self.get_job_status(jid)
            for jid, j in self._jobs.items()
            if j.user_id == user_id
        ]

    def get_queue_for_key(self, api_key_id: str) -> list[str]:
        """Get ordered list of queued job IDs for a key."""
        return [
            jid for jid, j in self._jobs.items()
            if j.api_key_id == api_key_id and j.status == "queued"
        ]
