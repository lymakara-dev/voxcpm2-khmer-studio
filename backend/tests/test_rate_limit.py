from __future__ import annotations

from app import auth as auth_module


def test_request_rate_limit_returns_429_with_retry_after(client, monkeypatch):
    monkeypatch.setattr(auth_module.request_limiter, "limit", 2)

    for _ in range(2):
        resp = client.post("/api/tts", params={"async": "1"}, json={"text": "hi"})
        assert resp.status_code == 200

    resp = client.post("/api/tts", params={"async": "1"}, json={"text": "hi"})
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
    assert "rate limit" in resp.json()["detail"].lower()


def test_char_rate_limit_returns_429(client, monkeypatch):
    monkeypatch.setattr(auth_module.char_limiter, "limit", 10)

    resp = client.post("/api/tts", params={"async": "1"}, json={"text": "a" * 8})
    assert resp.status_code == 200

    resp = client.post("/api/tts", params={"async": "1"}, json={"text": "a" * 8})
    assert resp.status_code == 429
    assert "character" in resp.json()["detail"].lower()
