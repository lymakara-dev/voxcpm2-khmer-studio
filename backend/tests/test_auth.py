from __future__ import annotations

from app import auth as auth_module
from app import config


def test_auth_disabled_by_default_allows_unkeyed_requests(client):
    res = client.post("/api/tts", json={"text": "hello"})
    assert res.status_code == 200


def test_missing_key_rejected_when_api_keys_set(client, monkeypatch):
    monkeypatch.setattr(config, "API_KEYS", {"test123"})
    res = client.post("/api/tts", json={"text": "hello"})
    assert res.status_code == 401
    assert "API key" in res.json()["detail"]


def test_wrong_key_rejected(client, monkeypatch):
    monkeypatch.setattr(config, "API_KEYS", {"test123"})
    res = client.post(
        "/api/tts", json={"text": "hello"}, headers={"Authorization": "Bearer wrong"}
    )
    assert res.status_code == 401


def test_correct_bearer_key_accepted(client, monkeypatch):
    monkeypatch.setattr(config, "API_KEYS", {"test123"})
    res = client.post(
        "/api/tts", json={"text": "hello"}, headers={"Authorization": "Bearer test123"}
    )
    assert res.status_code == 200


def test_correct_x_api_key_header_accepted(client, monkeypatch):
    monkeypatch.setattr(config, "API_KEYS", {"test123"})
    res = client.post("/api/tts", json={"text": "hello"}, headers={"X-API-Key": "test123"})
    assert res.status_code == 200


def test_request_rate_limit_returns_429_with_retry_after(client, monkeypatch):
    monkeypatch.setattr(auth_module.request_limiter, "limit", 2)
    ok1 = client.get("/api/jobs/nonexistent-1")
    ok2 = client.get("/api/jobs/nonexistent-2")
    assert ok1.status_code == 404  # rate budget not yet exceeded
    assert ok2.status_code == 404
    limited = client.get("/api/jobs/nonexistent-3")
    assert limited.status_code == 429
    assert "Retry-After" in limited.headers
    assert limited.json()["detail"]


def test_char_rate_limit_trips_on_long_text(client, monkeypatch):
    monkeypatch.setattr(auth_module.char_limiter, "limit", 10)
    res = client.post("/api/tts", json={"text": "this text is longer than ten characters"})
    assert res.status_code == 429
    assert "Retry-After" in res.headers
    assert "characters/hour" in res.json()["detail"]
