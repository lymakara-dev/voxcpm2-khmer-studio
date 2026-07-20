"""In-process FIFO job queue for /api/tts, replacing lock-or-429 with fair
ordering and position reporting. A single background worker serializes GPU
access using the same lock /api/tts-stream holds, so streaming and queued
generation never run concurrently."""

from __future__ import annotations

import asyncio
import io
import logging
import time
import uuid
from collections import deque
from dataclasses import dataclass, field

import soundfile as sf
from fastapi import HTTPException

from . import config
from .tts_model import get_model

logger = logging.getLogger("voxcpm-server")


@dataclass
class Job:
    id: str
    kwargs: dict
    status: str = "queued"  # queued | running | done | failed | expired
    position: int = 0       # 1-based while queued, 0 once running/finished
    error: str | None = None
    wav_bytes: bytes | None = None
    sample_rate: int = 48000
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    event: asyncio.Event = field(default_factory=asyncio.Event)


_jobs: dict[str, Job] = {}
_queue: deque[str] = deque()
_wakeup = asyncio.Condition()
_model_lock: asyncio.Lock | None = None


def bind_model_lock(lock: asyncio.Lock) -> None:
    """Called once per app lifespan startup: shares the GPU-serialization
    lock /api/tts-stream uses, and re-creates `_wakeup`.

    asyncio.Condition/Lock latch onto whichever event loop first awaits
    them; a module-level instance created once at import time raises
    "bound to a different event loop" the second time a fresh lifespan
    (hence a fresh loop) uses it — e.g. once per test with TestClient, or
    any process that re-runs the app's lifespan without restarting."""
    global _model_lock, _wakeup
    _model_lock = lock
    _wakeup = asyncio.Condition()


def _renumber() -> None:
    for i, job_id in enumerate(_queue):
        _jobs[job_id].position = i + 1


async def submit(kwargs: dict) -> Job:
    if len(_queue) >= config.MAX_QUEUE:
        raise HTTPException(status_code=429, detail="The synthesis queue is full — try again shortly.")
    job = Job(id=uuid.uuid4().hex, kwargs=kwargs)
    _jobs[job.id] = job
    async with _wakeup:
        _queue.append(job.id)
        _renumber()
        _wakeup.notify_all()
    return job


def get(job_id: str) -> Job:
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found — it may have expired.")
    return job


async def worker_loop() -> None:
    while True:
        async with _wakeup:
            while not _queue:
                await _wakeup.wait()
            job_id = _queue.popleft()
            _renumber()
        await _run(_jobs[job_id])


async def _run(job: Job) -> None:
    job.status = "running"
    job.position = 0
    try:
        model = await get_model()
        assert _model_lock is not None, "jobs.bind_model_lock() must be called at startup"
        async with _model_lock:
            t0 = time.time()
            wav = await asyncio.to_thread(model.generate, **job.kwargs)
        sample_rate = getattr(getattr(model, "tts_model", None), "sample_rate", 48000)
        buf = io.BytesIO()
        sf.write(buf, wav, sample_rate, format="WAV")
        job.wav_bytes = buf.getvalue()
        job.sample_rate = sample_rate
        job.status = "done"
        logger.info("Job %s done in %.1fs", job.id, time.time() - t0)
    except Exception as exc:  # noqa: BLE001 - recorded on the job, not raised here
        logger.exception("Job %s failed", job.id)
        job.status = "failed"
        job.error = f"Synthesis failed: {exc}"
    finally:
        job.finished_at = time.time()
        job.event.set()
        asyncio.create_task(_expire(job.id))


async def _expire(job_id: str) -> None:
    await asyncio.sleep(config.JOB_TTL_MIN * 60)
    job = _jobs.get(job_id)
    if job is not None:
        job.wav_bytes = None
        job.status = "expired"
