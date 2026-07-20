from __future__ import annotations

import re

from app import config

_REF_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def test_upload_valid_wav(client, sample_wav_bytes):
    resp = client.post(
        "/api/upload-ref",
        files={"file": ("ref.wav", sample_wav_bytes, "audio/wav")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert _REF_ID_RE.match(body["ref_id"])
    assert body["filename"] == "ref.wav"
    assert body["duration_s"] > 0


def test_upload_unsupported_extension(client, sample_wav_bytes):
    resp = client.post(
        "/api/upload-ref",
        files={"file": ("ref.txt", sample_wav_bytes, "text/plain")},
    )
    assert resp.status_code == 400


def test_upload_empty_file(client):
    resp = client.post(
        "/api/upload-ref",
        files={"file": ("ref.wav", b"", "audio/wav")},
    )
    assert resp.status_code == 400


def test_upload_too_large(client, sample_wav_bytes, monkeypatch):
    monkeypatch.setattr(config, "UPLOAD_MAX_BYTES", 1024)
    resp = client.post(
        "/api/upload-ref",
        files={"file": ("ref.wav", sample_wav_bytes, "audio/wav")},
    )
    assert resp.status_code == 413


def test_upload_too_long(client, sample_wav_bytes, monkeypatch):
    monkeypatch.setattr(config, "UPLOAD_MAX_DURATION_S", 0.1)
    resp = client.post(
        "/api/upload-ref",
        files={"file": ("ref.wav", sample_wav_bytes, "audio/wav")},
    )
    assert resp.status_code == 400
    assert "long" in resp.json()["detail"].lower()


def test_upload_then_tts_with_ref_id(client, sample_wav_bytes):
    upload = client.post(
        "/api/upload-ref",
        files={"file": ("ref.wav", sample_wav_bytes, "audio/wav")},
    )
    ref_id = upload.json()["ref_id"]

    resp = client.post(
        "/api/tts",
        json={"text": "hello", "reference_ref_id": ref_id},
    )
    assert resp.status_code == 200


def test_tts_with_malformed_ref_id_is_400(client):
    resp = client.post(
        "/api/tts",
        json={"text": "hello", "reference_ref_id": "not-a-valid-id"},
    )
    assert resp.status_code == 400


def test_tts_with_unknown_ref_id_is_404(client):
    resp = client.post(
        "/api/tts",
        json={"text": "hello", "reference_ref_id": "0" * 32},
    )
    assert resp.status_code == 404
