from __future__ import annotations

import io


def test_upload_valid_wav(client, sample_wav_bytes):
    res = client.post(
        "/api/upload-ref",
        files={"file": ("speaker.wav", sample_wav_bytes, "audio/wav")},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["filename"] == "speaker.wav"
    assert body["duration_s"] == 1.0
    assert len(body["ref_id"]) == 32


def test_upload_then_use_as_reference_ref_id(client, sample_wav_bytes):
    upload = client.post(
        "/api/upload-ref",
        files={"file": ("speaker.wav", sample_wav_bytes, "audio/wav")},
    )
    ref_id = upload.json()["ref_id"]
    res = client.post("/api/tts", json={"text": "hello", "reference_ref_id": ref_id})
    assert res.status_code == 200


def test_upload_rejects_unsupported_extension(client):
    res = client.post(
        "/api/upload-ref",
        files={"file": ("clip.xyz", b"not audio", "application/octet-stream")},
    )
    assert res.status_code == 400
    assert "Unsupported file type" in res.json()["detail"]


def test_upload_rejects_empty_file(client):
    res = client.post(
        "/api/upload-ref",
        files={"file": ("speaker.wav", b"", "audio/wav")},
    )
    assert res.status_code == 400
    assert res.json()["detail"]


def test_upload_rejects_unreadable_audio(client):
    res = client.post(
        "/api/upload-ref",
        files={"file": ("speaker.wav", b"not really a wav file", "audio/wav")},
    )
    assert res.status_code == 400
    assert "Couldn't read" in res.json()["detail"]


def test_upload_rejects_oversized_file(client, monkeypatch, sample_wav_bytes):
    from app import config

    monkeypatch.setattr(config, "UPLOAD_MAX_BYTES", 10)
    res = client.post(
        "/api/upload-ref",
        files={"file": ("speaker.wav", sample_wav_bytes, "audio/wav")},
    )
    assert res.status_code == 413
    assert "MB limit" in res.json()["detail"]


def test_upload_rejects_overlong_clip(client, monkeypatch, sample_wav_bytes):
    from app import config

    monkeypatch.setattr(config, "UPLOAD_MAX_DURATION_S", 0.1)
    res = client.post(
        "/api/upload-ref",
        files={"file": ("speaker.wav", sample_wav_bytes, "audio/wav")},
    )
    assert res.status_code == 400
    assert "limit is" in res.json()["detail"]
