# VoxCPM2-Khmer Speech Studio

Web app around the `sumnim/VoxCPM2-Khmer` TTS model (2B, tokenizer-free
diffusion AR, 48kHz output, Apache-2.0). Khmer-specialized fine-tune of
OpenBMB's VoxCPM2.

## Layout
- `backend/app/main.py` — FastAPI routes (`/api/tts`, `/api/upload-ref`,
  `/api/health`, `/api/model-info`). `config.py` holds all env vars,
  `tts_model.py` handles real/mock model loading, `uploads.py` handles
  reference-audio validation/storage/cleanup, `errors.py` flattens FastAPI
  validation errors into clean `{"detail": "<string>"}` JSON.
- `frontend/` — Vite + React single-page dashboard (`src/App.jsx`), tabs for
  Speak / Voice design / Clone / Model. Dev server proxies `/api` → :8000.
- `docker-compose.yml` — GPU backend + nginx frontend, HF cache volume.

## Commands
- Backend dev: `cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload`
  (set `MOCK_TTS=1` to skip loading the real model — sine-wave audio instead)
- Frontend dev: `cd frontend && npm install && npm run dev`
- Full stack: `docker compose up --build` (needs NVIDIA container toolkit, ~8 GB VRAM)

## Conventions
- Keep all model parameters in the `TTSRequest` pydantic model; the frontend's
  Python-snippet panel mirrors them 1:1 — update both together.
- Frontend styling lives in the `css` template string in `App.jsx`
  (design tokens in the `T` object). No Tailwind build step.
- API errors must return clean JSON `detail` strings; the UI displays them verbatim.

## Shipped
- Reference-audio upload (`POST /api/upload-ref`): validates/converts to 16kHz
  mono wav, UUID storage under `UPLOAD_DIR` with TTL cleanup, `reference_ref_id`
  / `prompt_ref_id` on `/api/tts`. Raw server paths (`reference_wav_path`)
  gated behind `ALLOW_RAW_PATHS=0` (off by default — client-supplied paths are
  a file-read risk on public deployments). Clone tab has a drag-and-drop
  upload zone; the raw-path field only shows if `/api/model-info` reports
  `allow_raw_paths: true`. `MOCK_TTS=1` skips real model loading and returns a
  synthetic sine-wave clip — used for GPU-less dev and all tests.
- Streaming synthesis (`POST /api/tts-stream`): chunked raw 16-bit PCM, bridging
  the model's blocking `generate_streaming` sync generator to an async response
  via a thread + queue (`tts_model.stream_pcm16`). Frontend "Stream" toggle
  (only enabled for the default `/api/tts` endpoint) plays chunks through Web
  Audio as they arrive and rebuilds a WAV blob client-side at the end so
  download/replay still work; falls back to a clear error and switches Stream
  off if the browser or endpoint doesn't support it.
- Job queue (`app/jobs.py`): `/api/tts` is now a bounded FIFO queue (`MAX_QUEUE`)
  with a single worker instead of lock-or-429; 429 only fires once the queue
  itself is full. `?async=1` returns `{job_id, position}` immediately;
  `GET /api/jobs/{id}` / `GET /api/jobs/{id}/result` poll status and fetch the
  result (results expire after `JOB_TTL_MIN`). The worker shares `_model_lock`
  with `/api/tts-stream` so the two paths never run generation concurrently.
  Frontend polls every 1.5s and shows "In queue — position N" while queued.
- Auth + rate limiting (`app/auth.py`): `API_KEYS` (unset = disabled, the
  dev default) gates every route except `/api/health` and `/api/model-info`
  behind `Authorization: Bearer <key>` / `X-API-Key`. Every caller (by key,
  or by IP when auth is off) is sliding-window rate limited —
  `RATE_LIMIT_PER_MIN` requests/min and `RATE_LIMIT_CHARS_PER_HOUR` on
  `/api/tts*` — both returning 429 + `Retry-After`. In-memory now;
  `SlidingWindowLimiter.check()` is the whole interface a Redis-backed swap
  would need to implement. Frontend has a gear-icon settings panel (API key
  in localStorage, attached to every request) and surfaces 401s as "Invalid
  or missing API key — add one in settings."

## Roadmap (good next tasks)
1. Playwright smoke test + pytest for the API.
2. History panel: keep the last N generations client-side with replay.
3. Redis-backed queue and rate limiter for multi-process/multi-replica
   deployments (both are in-process/single-worker today).
