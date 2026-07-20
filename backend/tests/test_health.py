from __future__ import annotations


def test_health_shape(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["mock"] is True
    assert body["model_loaded"] is True  # LAZY_LOAD=0 default -> loaded at startup
    assert "model_id" in body


def test_model_info_shape(client):
    res = client.get("/api/model-info")
    assert res.status_code == 200
    body = res.json()
    for key in ("model_id", "base", "params", "sample_rate_out", "languages", "license"):
        assert key in body
    assert body["mock"] is True
    assert body["allow_raw_paths"] is False
    assert body["auth_required"] is False


def test_health_and_model_info_never_require_auth(client, monkeypatch):
    from app import config

    monkeypatch.setattr(config, "API_KEYS", {"secret"})
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/model-info").status_code == 200
