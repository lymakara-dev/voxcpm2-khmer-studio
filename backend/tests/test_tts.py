from __future__ import annotations

import io

import soundfile as sf


def test_tts_happy_path_returns_valid_wav(client):
    res = client.post("/api/tts", json={"text": "សួស្តី"})
    assert res.status_code == 200
    assert res.headers["content-type"] == "audio/wav"
    data, sr = sf.read(io.BytesIO(res.content))
    assert sr > 0
    assert len(data) > 0


def test_tts_empty_text_is_rejected(client):
    res = client.post("/api/tts", json={"text": ""})
    assert res.status_code == 422
    assert isinstance(res.json()["detail"], str)
    assert res.json()["detail"]


def test_tts_missing_text_is_rejected(client):
    res = client.post("/api/tts", json={})
    assert res.status_code == 422
    assert res.json()["detail"]


def test_tts_cfg_value_out_of_range_is_rejected(client):
    res = client.post("/api/tts", json={"text": "hello", "cfg_value": 10.0})
    assert res.status_code == 422
    assert res.json()["detail"]


def test_tts_inference_timesteps_out_of_range_is_rejected(client):
    res = client.post("/api/tts", json={"text": "hello", "inference_timesteps": 1})
    assert res.status_code == 422
    assert res.json()["detail"]


def test_raw_paths_rejected_by_default(client):
    res = client.post("/api/tts", json={"text": "hello", "reference_wav_path": "/etc/passwd"})
    assert res.status_code == 400
    assert "upload-ref" in res.json()["detail"]


def test_raw_paths_allowed_when_enabled(client, monkeypatch, tmp_path):
    from app import config

    wav_path = tmp_path / "ref.wav"
    import numpy as np

    sf.write(str(wav_path), (0.1 * np.ones(1000)).astype("float32"), 16000)
    monkeypatch.setattr(config, "ALLOW_RAW_PATHS", True)
    res = client.post("/api/tts", json={"text": "hello", "reference_wav_path": str(wav_path)})
    assert res.status_code == 200


def test_unknown_reference_ref_id_returns_404(client):
    res = client.post("/api/tts", json={"text": "hello", "reference_ref_id": "0" * 32})
    assert res.status_code == 404
    assert res.json()["detail"]


def test_invalid_reference_ref_id_format_returns_400(client):
    res = client.post("/api/tts", json={"text": "hello", "reference_ref_id": "not-a-valid-id"})
    assert res.status_code == 400
    assert res.json()["detail"]
