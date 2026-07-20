from __future__ import annotations

from app import config


def test_missing_text_is_422_with_clean_detail(client):
    resp = client.post("/api/tts", json={})
    assert resp.status_code == 422
    body = resp.json()
    assert isinstance(body["detail"], str)
    assert "text" in body["detail"]


def test_empty_text_is_422(client):
    resp = client.post("/api/tts", json={"text": ""})
    assert resp.status_code == 422


def test_text_over_max_chars_is_422(client):
    text = "a" * (config.MAX_TEXT_CHARS + 1)
    resp = client.post("/api/tts", json={"text": text})
    assert resp.status_code == 422


def test_cfg_value_out_of_range_is_422(client):
    resp = client.post("/api/tts", json={"text": "hello", "cfg_value": 10.0})
    assert resp.status_code == 422


def test_inference_timesteps_out_of_range_is_422(client):
    resp = client.post("/api/tts", json={"text": "hello", "inference_timesteps": 1})
    assert resp.status_code == 422


def test_unknown_route_404_is_untouched_by_error_handler(client):
    resp = client.get("/api/does-not-exist")
    assert resp.status_code == 404
