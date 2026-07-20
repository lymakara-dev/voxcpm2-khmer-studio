"""VoxCPM2-Khmer inference server.

POST /api/tts          -> synthesize speech, returns audio/wav
POST /api/tts-stream   -> synthesize speech, chunked raw 16-bit PCM
POST /api/upload-ref   -> upload reference audio, returns a ref_id
GET  /api/health       -> liveness + model status
GET  /api/model-info   -> static model metadata

The 2B model is loaded once at startup (lazy on first request if
LAZY_LOAD=1) and guarded by a lock: a single GPU can only run one
synthesis at a time, concurrent requests get 429 so the client can
retry instead of queueing unbounded work.

Set MOCK_TTS=1 to skip loading the real model entirely and return a
synthetic sine-wave clip instead — used for frontend dev without a GPU,
CI, and the test suite.
"""

from __future__ import annotations

import asyncio
import io
import logging
import time
from contextlib import asynccontextmanager

import soundfile as sf
from fastapi import FastAPI, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator

from . import config, errors, uploads
from .tts_model import get_model, is_loaded, stream_pcm16

logger = logging.getLogger("voxcpm-server")
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if not config.LAZY_LOAD:
        await get_model()
    cleanup_task = asyncio.create_task(uploads.cleanup_loop())
    try:
        yield
    finally:
        cleanup_task.cancel()


app = FastAPI(title="VoxCPM2-Khmer Speech Studio API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)
errors.install(app)

_model_lock = asyncio.Lock()   # one synthesis at a time per GPU


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=config.MAX_TEXT_CHARS)
    cfg_value: float = Field(2.0, ge=1.0, le=4.0)
    inference_timesteps: int = Field(10, ge=4, le=64)
    normalize: bool = True
    denoise: bool = True
    retry_badcase: bool = True
    reference_wav_path: str | None = None  # raw server path — gated by ALLOW_RAW_PATHS
    prompt_wav_path: str | None = None
    prompt_text: str | None = None
    reference_ref_id: str | None = None  # id returned by POST /api/upload-ref
    prompt_ref_id: str | None = None

    @model_validator(mode="after")
    def _resolve_refs(self):
        if not config.ALLOW_RAW_PATHS and (self.reference_wav_path or self.prompt_wav_path):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Raw server file paths are disabled on this deployment. "
                    "Upload the reference clip via /api/upload-ref and pass reference_ref_id instead."
                ),
            )
        if self.reference_ref_id:
            self.reference_wav_path = uploads.resolve_ref_id(self.reference_ref_id)
        if self.prompt_ref_id:
            self.prompt_wav_path = uploads.resolve_ref_id(self.prompt_ref_id)
        return self


@app.get("/api/health")
async def health():
    return {"status": "ok", "model_loaded": is_loaded(), "model_id": config.MODEL_ID, "mock": config.MOCK_TTS}


@app.get("/api/model-info")
async def model_info():
    return {
        "model_id": config.MODEL_ID,
        "base": "openbmb/VoxCPM2",
        "params": "2B",
        "sample_rate_out": 48000,
        "languages": 30,
        "license": "apache-2.0",
        "allow_raw_paths": config.ALLOW_RAW_PATHS,
        "mock": config.MOCK_TTS,
    }


@app.post("/api/upload-ref")
async def upload_ref(file: UploadFile):
    return await uploads.save_upload(file)


def _generate_kwargs(req: TTSRequest) -> dict:
    return dict(
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


def _sample_rate(model) -> int:
    return getattr(getattr(model, "tts_model", None), "sample_rate", 48000)


@app.post("/api/tts")
async def tts(req: TTSRequest):
    model = await get_model()

    if _model_lock.locked():
        raise HTTPException(status_code=429, detail="Synthesis in progress, retry shortly")

    async with _model_lock:
        t0 = time.time()
        try:
            wav = await asyncio.to_thread(model.generate, **_generate_kwargs(req))
        except Exception as exc:  # surface a clean error, log the full trace
            logger.exception("Synthesis failed")
            raise HTTPException(status_code=500, detail=f"Synthesis failed: {exc}") from exc

    sample_rate = _sample_rate(model)
    buf = io.BytesIO()
    sf.write(buf, wav, sample_rate, format="WAV")
    logger.info("Synthesized %d chars in %.1fs", len(req.text), time.time() - t0)
    return Response(
        content=buf.getvalue(),
        media_type="audio/wav",
        headers={"X-Sample-Rate": str(sample_rate)},
    )


@app.post("/api/tts-stream")
async def tts_stream(req: TTSRequest):
    """Chunked raw 16-bit little-endian PCM, mono, at the rate in
    X-Sample-Rate. Not a WAV container — a WAV header needs the total
    length up front, which streaming can't provide."""
    model = await get_model()

    if _model_lock.locked():
        raise HTTPException(status_code=429, detail="Synthesis in progress, retry shortly")

    sample_rate = _sample_rate(model)

    async def body():
        t0 = time.time()
        async with _model_lock:
            async for chunk in stream_pcm16(model, **_generate_kwargs(req)):
                yield chunk
        logger.info("Streamed %d chars in %.1fs", len(req.text), time.time() - t0)

    return StreamingResponse(
        body(),
        media_type=f"audio/pcm;rate={sample_rate}",
        headers={"X-Sample-Rate": str(sample_rate)},
    )
