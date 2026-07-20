"""Reference-audio upload: validation, conversion to 16kHz mono wav,
UUID-keyed storage under UPLOAD_DIR, and TTL-based cleanup."""

from __future__ import annotations

import asyncio
import io
import logging
import math
import os
import re
import time
import uuid

import numpy as np
import soundfile as sf
from fastapi import HTTPException, UploadFile

from . import config

logger = logging.getLogger("voxcpm-server")

ALLOWED_EXTENSIONS = {".wav", ".mp3", ".flac", ".m4a", ".ogg"}
TARGET_SAMPLE_RATE = 16000
_REF_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def _friendly_read_error() -> HTTPException:
    return HTTPException(
        status_code=400,
        detail=(
            "Couldn't read that audio file. Supported formats are WAV, FLAC, "
            "OGG, and MP3 (M4A support depends on the server's audio "
            "libraries) — try re-exporting as WAV if this keeps failing."
        ),
    )


def _resample(data: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    if orig_sr == target_sr:
        return data
    from scipy.signal import resample_poly

    g = math.gcd(orig_sr, target_sr)
    return resample_poly(data, target_sr // g, orig_sr // g)


async def save_upload(file: UploadFile) -> dict:
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext or 'unknown'}'. Upload a WAV, MP3, FLAC, M4A, or OGG file.",
        )

    raw = await file.read(config.UPLOAD_MAX_BYTES + 1)
    if len(raw) > config.UPLOAD_MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File is larger than the {config.UPLOAD_MAX_BYTES // (1024 * 1024)} MB limit.",
        )
    if not raw:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    def _process() -> tuple[np.ndarray, float]:
        try:
            data, sr = sf.read(io.BytesIO(raw), always_2d=False)
        except Exception as exc:  # noqa: BLE001 - surfaced as a clean 400 below
            raise _friendly_read_error() from exc

        if data.ndim > 1:
            data = data.mean(axis=1)
        duration_s = len(data) / sr
        if duration_s > config.UPLOAD_MAX_DURATION_S:
            raise HTTPException(
                status_code=400,
                detail=f"Clip is {duration_s:.1f}s long — the limit is {config.UPLOAD_MAX_DURATION_S:.0f}s.",
            )
        data = _resample(data.astype(np.float32), sr, TARGET_SAMPLE_RATE)
        return data, len(data) / TARGET_SAMPLE_RATE

    data, duration_s = await asyncio.to_thread(_process)

    os.makedirs(config.UPLOAD_DIR, exist_ok=True)
    ref_id = uuid.uuid4().hex
    dest = os.path.join(config.UPLOAD_DIR, f"{ref_id}.wav")
    await asyncio.to_thread(sf.write, dest, data, TARGET_SAMPLE_RATE, "PCM_16")

    logger.info("Stored reference upload %s (%.1fs, %s)", ref_id, duration_s, file.filename)
    return {"ref_id": ref_id, "duration_s": round(duration_s, 2), "filename": file.filename}


def resolve_ref_id(ref_id: str) -> str:
    """Map a client-supplied ref_id to a path strictly inside UPLOAD_DIR."""
    if not _REF_ID_RE.match(ref_id):
        raise HTTPException(status_code=400, detail="Invalid reference id.")
    path = os.path.join(config.UPLOAD_DIR, f"{ref_id}.wav")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Reference audio not found — it may have expired. Upload it again.")
    return path


async def cleanup_loop() -> None:
    """Background task: delete uploads older than UPLOAD_TTL_HOURS."""
    interval_s = max(60.0, min(3600.0, config.UPLOAD_TTL_HOURS * 3600 / 4))
    ttl_s = config.UPLOAD_TTL_HOURS * 3600
    while True:
        try:
            await asyncio.to_thread(_sweep, ttl_s)
        except Exception:  # noqa: BLE001 - never let cleanup crash the server
            logger.exception("Upload cleanup sweep failed")
        await asyncio.sleep(interval_s)


def _sweep(ttl_s: float) -> None:
    if not os.path.isdir(config.UPLOAD_DIR):
        return
    now = time.time()
    for name in os.listdir(config.UPLOAD_DIR):
        path = os.path.join(config.UPLOAD_DIR, name)
        try:
            if now - os.path.getmtime(path) > ttl_s:
                os.remove(path)
                logger.info("Cleaned up expired upload %s", name)
        except OSError:
            pass
