from __future__ import annotations

import time

from app import config


def test_unknown_job_status_404(client):
    resp = client.get("/api/jobs/does-not-exist")
    assert resp.status_code == 404


def test_unknown_job_result_404(client):
    resp = client.get("/api/jobs/does-not-exist/result")
    assert resp.status_code == 404


def test_result_while_processing_is_409(client, monkeypatch):
    import numpy as np

    from app.tts_model import MockModel

    def slow_generate(self, text, **_kwargs):
        time.sleep(0.5)
        return np.zeros(1000, dtype=np.float32)

    monkeypatch.setattr(MockModel, "generate", slow_generate)

    resp = client.post("/api/tts", params={"async": "1"}, json={"text": "hello"})
    job_id = resp.json()["job_id"]

    result = client.get(f"/api/jobs/{job_id}/result")
    assert result.status_code == 409

    status = client.get(f"/api/jobs/{job_id}")
    assert status.json()["status"] in ("queued", "running")

    # The slow generate() call is still sleeping in a background thread and
    # holds the shared model lock until it returns — drain it here so later
    # tests (which share this session-scoped client/worker) don't see a
    # spuriously "locked" model.
    deadline = time.time() + 3.0
    while time.time() < deadline:
        if client.get(f"/api/jobs/{job_id}").json()["status"] not in ("queued", "running"):
            break
        time.sleep(0.05)


def test_queue_full_returns_429(client, monkeypatch):
    monkeypatch.setattr(config, "MAX_QUEUE", 0)
    resp = client.post("/api/tts", params={"async": "1"}, json={"text": "hello"})
    assert resp.status_code == 429
    assert "queue" in resp.json()["detail"].lower()
