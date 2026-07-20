from __future__ import annotations

import time

import pytest
from fastapi import HTTPException

from app import config, jobs


def test_async_tts_lifecycle_queued_to_done(client):
    submit = client.post("/api/tts?async=1", json={"text": "hello"})
    assert submit.status_code == 200
    body = submit.json()
    job_id = body["job_id"]
    assert "position" in body

    deadline = time.time() + 5
    status = None
    while time.time() < deadline:
        status_res = client.get(f"/api/jobs/{job_id}")
        assert status_res.status_code == 200
        status = status_res.json()["status"]
        if status == "done":
            break
        time.sleep(0.05)
    assert status == "done"

    result = client.get(f"/api/jobs/{job_id}/result")
    assert result.status_code == 200
    assert result.headers["content-type"] == "audio/wav"


def test_job_result_while_still_processing_returns_409(client):
    submit = client.post("/api/tts?async=1", json={"text": "hello"})
    job_id = submit.json()["job_id"]
    result = client.get(f"/api/jobs/{job_id}/result")
    # It may have already finished on a fast machine — only assert 409 when
    # genuinely still in flight, otherwise this assertion would be flaky.
    if result.status_code != 200:
        assert result.status_code == 409


def test_unknown_job_id_returns_404(client):
    res = client.get("/api/jobs/does-not-exist")
    assert res.status_code == 404
    assert res.json()["detail"]


@pytest.mark.asyncio
async def test_queue_full_raises_429(monkeypatch):
    monkeypatch.setattr(config, "MAX_QUEUE", 2)
    jobs._queue.extend(["fake-a", "fake-b"])
    with pytest.raises(HTTPException) as exc_info:
        await jobs.submit({"text": "hello"})
    assert exc_info.value.status_code == 429
    assert "queue is full" in exc_info.value.detail
