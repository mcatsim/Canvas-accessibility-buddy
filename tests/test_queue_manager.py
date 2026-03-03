# tests/test_queue_manager.py
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from a11yscope.web.queue_manager import ScanQueueManager


@pytest.fixture
def manager():
    return ScanQueueManager()


@pytest.mark.asyncio
async def test_enqueue_creates_job(manager):
    """Enqueuing returns a job ID and the job is tracked."""
    job_id = await manager.enqueue(
        user_id="u1", api_key_id="k1", canvas_url="https://c.edu",
        course_id=101, course_name="CS101",
        db_session_factory=AsyncMock(),
        decrypt_fn=lambda kid: "plaintext-token",
    )
    assert isinstance(job_id, str)
    status = manager.get_job_status(job_id)
    assert status is not None
    assert status["status"] in ("queued", "running")


@pytest.mark.asyncio
async def test_sequential_per_key(manager):
    """Jobs with the same key run sequentially."""
    started = []
    original_run = manager._execute_job

    async def slow_run(job_id, **kwargs):
        started.append(job_id)
        await asyncio.sleep(0.1)

    manager._execute_job = slow_run

    id1 = await manager.enqueue(
        user_id="u1", api_key_id="k1", canvas_url="https://c.edu",
        course_id=1, course_name="C1",
        db_session_factory=AsyncMock(), decrypt_fn=lambda kid: "tok",
    )
    id2 = await manager.enqueue(
        user_id="u1", api_key_id="k1", canvas_url="https://c.edu",
        course_id=2, course_name="C2",
        db_session_factory=AsyncMock(), decrypt_fn=lambda kid: "tok",
    )
    # Give workers time to process
    await asyncio.sleep(0.05)
    # First job should start before second
    assert started[0] == id1


@pytest.mark.asyncio
async def test_cancel_queued_job(manager):
    """Cancelling a queued job removes it."""
    async def block_forever(job_id, **kwargs):
        await asyncio.sleep(10)

    manager._execute_job = block_forever
    id1 = await manager.enqueue(
        user_id="u1", api_key_id="k1", canvas_url="https://c.edu",
        course_id=1, course_name="C1",
        db_session_factory=AsyncMock(), decrypt_fn=lambda kid: "tok",
    )
    cancelled = manager.cancel(id1)
    assert cancelled is True
