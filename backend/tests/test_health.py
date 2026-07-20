from __future__ import annotations


def test_health_ok(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["mock"] is True
    assert "model_id" in body
    assert isinstance(body["model_loaded"], bool)


def test_model_info(client):
    resp = client.get("/api/model-info")
    assert resp.status_code == 200
    body = resp.json()
    assert body["base"] == "openbmb/VoxCPM2"
    assert body["params"] == "2B"
    assert body["sample_rate_out"] == 48000
    assert body["mock"] is True
    assert body["auth_required"] is False


def test_health_and_model_info_need_no_auth_even_when_enabled(client, monkeypatch):
    from app import config

    monkeypatch.setattr(config, "API_KEYS", {"secret"})
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/model-info").status_code == 200
