"""VoxCPM2-Khmer inference server.

POST /api/tts        -> synthesize speech, returns audio/wav
GET  /api/health     -> liveness + model status
GET  /api/model-info -> static model metadata

The 2B model is loaded once at startup (lazy on first request if
LAZY_LOAD=1) and guarded by a lock: a single GPU can only run one
synthesis at a time, concurrent requests get 429 so the client can
retry instead of queueing unbounded work.
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import time

import soundfile as sf
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logger = logging.getLogger("voxcpm-server")
logging.basicConfig(level=logging.INFO)

MODEL_ID = os.getenv("MODEL_ID", "sumnim/VoxCPM2-Khmer")
LAZY_LOAD = os.getenv("LAZY_LOAD", "0") == "1"
MAX_TEXT_CHARS = int(os.getenv("MAX_TEXT_CHARS", "2000"))
ALLOWED_ORIGINS = [o for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o]

app = FastAPI(title="VoxCPM2-Khmer Speech Studio API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

_model = None
_model_lock = asyncio.Lock()   # one synthesis at a time per GPU
_load_lock = asyncio.Lock()


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_TEXT_CHARS)
    cfg_value: float = Field(2.0, ge=1.0, le=4.0)
    inference_timesteps: int = Field(10, ge=4, le=64)
    normalize: bool = True
    denoise: bool = True
    retry_badcase: bool = True
    reference_wav_path: str | None = None  # server-side path or pre-uploaded id
    prompt_wav_path: str | None = None
    prompt_text: str | None = None


async def get_model():
    global _model
    if _model is not None:
        return _model
    async with _load_lock:
        if _model is None:
            logger.info("Loading %s ...", MODEL_ID)
            t0 = time.time()
            from voxcpm import VoxCPM  # deferred: heavy import

            _model = await asyncio.to_thread(VoxCPM.from_pretrained, MODEL_ID)
            logger.info("Model ready in %.1fs", time.time() - t0)
    return _model


@app.on_event("startup")
async def startup() -> None:
    if not LAZY_LOAD:
        await get_model()


@app.get("/api/health")
async def health():
    return {"status": "ok", "model_loaded": _model is not None, "model_id": MODEL_ID}


@app.get("/api/model-info")
async def model_info():
    return {
        "model_id": MODEL_ID,
        "base": "openbmb/VoxCPM2",
        "params": "2B",
        "sample_rate_out": 48000,
        "languages": 30,
        "license": "apache-2.0",
    }


@app.post("/api/tts")
async def tts(req: TTSRequest):
    model = await get_model()

    if _model_lock.locked():
        raise HTTPException(status_code=429, detail="Synthesis in progress, retry shortly")

    async with _model_lock:
        t0 = time.time()
        try:
            wav = await asyncio.to_thread(
                model.generate,
                text=req.text,
                cfg_value=req.cfg_value,
                inference_timesteps=req.inference_timesteps,
                normalize=req.normalize,
                denoise=req.denoise,
                retry_badcase=req.retry_badcase,
                reference_wav_path=req.reference_wav_path,
                prompt_wav_path=req.prompt_wav_path,
                prompt_text=req.prompt_text,
            )
        except Exception as exc:  # surface a clean error, log the full trace
            logger.exception("Synthesis failed")
            raise HTTPException(status_code=500, detail=f"Synthesis failed: {exc}") from exc

    sample_rate = getattr(getattr(model, "tts_model", None), "sample_rate", 48000)
    buf = io.BytesIO()
    sf.write(buf, wav, sample_rate, format="WAV")
    logger.info("Synthesized %d chars in %.1fs", len(req.text), time.time() - t0)
    return Response(
        content=buf.getvalue(),
        media_type="audio/wav",
        headers={"X-Sample-Rate": str(sample_rate)},
    )
