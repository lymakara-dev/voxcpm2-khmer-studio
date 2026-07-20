from __future__ import annotations

import io
import time

import soundfile as sf


def _poll_job(client, job_id, timeout_s=5.0):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        resp = client.get(f"/api/jobs/{job_id}")
        body = resp.json()
        if body["status"] not in ("queued", "running"):
            return body
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish within {timeout_s}s")


def test_tts_sync_returns_wav(client):
    resp = client.post("/api/tts", json={"text": "hello world"})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/wav"
    assert "X-Sample-Rate" in resp.headers
    data, sr = sf.read(io.BytesIO(resp.content))
    assert sr == int(resp.headers["X-Sample-Rate"])
    assert len(data) > 0


def test_tts_async_returns_job_then_result(client):
    resp = client.post("/api/tts", params={"async": "1"}, json={"text": "hello world"})
    assert resp.status_code == 200
    body = resp.json()
    assert "job_id" in body
    assert body["position"] >= 0

    status = _poll_job(client, body["job_id"])
    assert status["status"] == "done"
    assert status["position"] == 0

    result = client.get(f"/api/jobs/{body['job_id']}/result")
    assert result.status_code == 200
    assert result.headers["content-type"] == "audio/wav"
    data, _sr = sf.read(io.BytesIO(result.content))
    assert len(data) > 0


def test_raw_path_rejected_by_default(client):
    resp = client.post(
        "/api/tts",
        json={"text": "hello", "reference_wav_path": "/etc/passwd"},
    )
    assert resp.status_code == 400
    assert "raw" in resp.json()["detail"].lower()


def test_raw_path_allowed_when_enabled(client, monkeypatch):
    from app import config

    monkeypatch.setattr(config, "ALLOW_RAW_PATHS", True)
    resp = client.post(
        "/api/tts",
        json={"text": "hello", "reference_wav_path": "/some/path.wav"},
    )
    assert resp.status_code == 200
