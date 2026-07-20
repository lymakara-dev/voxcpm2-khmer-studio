from __future__ import annotations

from app import config


def test_no_auth_required_by_default(client):
    resp = client.post("/api/tts", json={"text": "hello"})
    assert resp.status_code == 200


def test_missing_key_is_401_when_auth_enabled(client, monkeypatch):
    monkeypatch.setattr(config, "API_KEYS", {"secret"})
    resp = client.post("/api/tts", json={"text": "hello"})
    assert resp.status_code == 401


def test_wrong_key_is_401(client, monkeypatch):
    monkeypatch.setattr(config, "API_KEYS", {"secret"})
    resp = client.post(
        "/api/tts",
        json={"text": "hello"},
        headers={"Authorization": "Bearer wrong"},
    )
    assert resp.status_code == 401


def test_correct_bearer_key_succeeds(client, monkeypatch):
    monkeypatch.setattr(config, "API_KEYS", {"secret"})
    resp = client.post(
        "/api/tts",
        json={"text": "hello"},
        headers={"Authorization": "Bearer secret"},
    )
    assert resp.status_code == 200


def test_correct_x_api_key_header_succeeds(client, monkeypatch):
    monkeypatch.setattr(config, "API_KEYS", {"secret"})
    resp = client.post(
        "/api/tts",
        json={"text": "hello"},
        headers={"X-API-Key": "secret"},
    )
    assert resp.status_code == 200
