"""VoxCPM2-Khmer inference server.

POST /api/tts               -> synthesize speech, returns audio/wav (or a
                                job_id immediately with ?async=1)
POST /api/tts-stream        -> synthesize speech, chunked raw 16-bit PCM
GET  /api/jobs/{id}         -> job status + queue position
GET  /api/jobs/{id}/result  -> the finished job's audio/wav
POST /api/upload-ref        -> upload reference audio, returns a ref_id
GET  /api/health            -> liveness + model status
GET  /api/model-info        -> static model metadata

/api/tts is backed by a bounded FIFO queue (MAX_QUEUE) with a single
worker, so GPU access is serialized fairly instead of rejecting concurrent
requests outright; 429 only happens once the queue itself is full.
/api/tts-stream shares the same underlying lock so it never overlaps with
queued work.

Set MOCK_TTS=1 to skip loading the real model entirely and return a
synthetic sine-wave clip instead — used for frontend dev without a GPU,
CI, and the test suite.

If API_KEYS is set, all routes above except /api/health and /api/model-info
require an API key (Authorization: Bearer <key> or X-API-Key); unset
(the default) disables auth entirely. Every caller — keyed by API key when
auth is on, by IP otherwise — is also sliding-window rate limited
(RATE_LIMIT_PER_MIN requests/min, RATE_LIMIT_CHARS_PER_HOUR characters/hour).
"""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator

from . import auth, config, errors, jobs, uploads
from .tts_model import get_model, is_loaded, safe_normalize_flag, stream_pcm16

logger = logging.getLogger("voxcpm-server")
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _model_lock
    # Created fresh per lifespan startup, not once at import time: asyncio
    # primitives latch onto whichever loop first awaits them, and reusing
    # one across independent lifespans (e.g. one per test with TestClient)
    # raises "bound to a different event loop".
    _model_lock = asyncio.Lock()
    if not config.LAZY_LOAD:
        await get_model()
    jobs.bind_model_lock(_model_lock)
    worker_task = asyncio.create_task(jobs.worker_loop())
    cleanup_task = asyncio.create_task(uploads.cleanup_loop())
    try:
        yield
    finally:
        worker_task.cancel()
        cleanup_task.cancel()


app = FastAPI(title="VoxCPM2-Khmer Speech Studio API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)
errors.install(app)

_model_lock: asyncio.Lock  # one synthesis at a time per GPU; (re)created in lifespan()


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
        "auth_required": bool(config.API_KEYS),
    }


@app.post("/api/upload-ref")
async def upload_ref(file: UploadFile, identity: str = Depends(auth.require_identity)):
    auth.enforce_request_rate(identity)
    return await uploads.save_upload(file)


def _generate_kwargs(req: TTSRequest) -> dict:
    return dict(
        text=req.text,
        cfg_value=req.cfg_value,
        inference_timesteps=req.inference_timesteps,
        normalize=safe_normalize_flag(req.text, req.normalize),
        denoise=req.denoise,
        retry_badcase=req.retry_badcase,
        reference_wav_path=req.reference_wav_path,
        prompt_wav_path=req.prompt_wav_path,
        prompt_text=req.prompt_text,
    )


def _sample_rate(model) -> int:
    return getattr(getattr(model, "tts_model", None), "sample_rate", 48000)


def _job_result_response(job: jobs.Job) -> Response:
    if job.status == "failed":
        raise HTTPException(status_code=500, detail=job.error)
    if job.status == "expired" or job.wav_bytes is None:
        raise HTTPException(status_code=410, detail="Result has expired. Submit a new request.")
    return Response(
        content=job.wav_bytes,
        media_type="audio/wav",
        headers={"X-Sample-Rate": str(job.sample_rate)},
    )


@app.post("/api/tts")
async def tts(
    req: TTSRequest,
    async_mode: bool = Query(False, alias="async"),
    identity: str = Depends(auth.require_identity),
):
    auth.enforce_request_rate(identity)
    auth.enforce_char_rate(identity, len(req.text))
    job = await jobs.submit(_generate_kwargs(req))
    if async_mode:
        return {"job_id": job.id, "position": job.position}
    await job.event.wait()
    return _job_result_response(job)


@app.get("/api/jobs/{job_id}")
async def job_status(job_id: str, identity: str = Depends(auth.require_identity)):
    auth.enforce_request_rate(identity)
    job = jobs.get(job_id)
    body = {"status": job.status, "position": job.position}
    if job.status == "failed":
        body["error"] = job.error
    return body


@app.get("/api/jobs/{job_id}/result")
async def job_result(job_id: str, identity: str = Depends(auth.require_identity)):
    auth.enforce_request_rate(identity)
    job = jobs.get(job_id)
    if job.status in ("queued", "running"):
        raise HTTPException(status_code=409, detail="Job is still processing — check /api/jobs/{id} for status.")
    return _job_result_response(job)


@app.post("/api/tts-stream")
async def tts_stream(req: TTSRequest, identity: str = Depends(auth.require_identity)):
    """Chunked raw 16-bit little-endian PCM, mono, at the rate in
    X-Sample-Rate. Not a WAV container — a WAV header needs the total
    length up front, which streaming can't provide."""
    auth.enforce_request_rate(identity)
    auth.enforce_char_rate(identity, len(req.text))
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
