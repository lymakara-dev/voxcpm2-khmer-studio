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

## Roadmap (good next tasks)
1. Job queue (e.g. simple asyncio queue or Redis) instead of 429-on-busy.
2. Rate limiting + API key auth for public deployments.
3. Playwright smoke test + pytest for the API.
4. History panel: keep the last N generations client-side with replay.
