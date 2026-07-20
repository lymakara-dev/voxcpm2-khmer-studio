from __future__ import annotations


def test_stream_returns_pcm16_chunks(client):
    resp = client.post("/api/tts-stream", json={"text": "hello world"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("audio/pcm;rate=")
    assert "X-Sample-Rate" in resp.headers
    assert len(resp.content) > 0
    assert len(resp.content) % 2 == 0  # 16-bit samples


def test_stream_validates_request_body(client):
    resp = client.post("/api/tts-stream", json={"text": ""})
    assert resp.status_code == 422


def test_stream_returns_429_when_model_locked(client, monkeypatch):
    import app.main as main_module

    class _AlwaysLocked:
        def locked(self):
            return True

    monkeypatch.setattr(main_module, "_model_lock", _AlwaysLocked())
    resp = client.post("/api/tts-stream", json={"text": "hello"})
    assert resp.status_code == 429
