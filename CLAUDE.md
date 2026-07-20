# VoxCPM2-Khmer Speech Studio

Web app around the `sumnim/VoxCPM2-Khmer` TTS model (2B, tokenizer-free
diffusion AR, 48kHz output, Apache-2.0). Khmer-specialized fine-tune of
OpenBMB's VoxCPM2.

## Layout
- `backend/` — FastAPI (`app/main.py`), one endpoint that matters: `POST /api/tts`
  (JSON in, `audio/wav` out). Model loads once at startup; an asyncio lock
  serializes GPU work and returns 429 when busy.
- `frontend/` — Vite + React single-page dashboard (`src/App.jsx`), tabs for
  Speak / Voice design / Clone / Model. Dev server proxies `/api` → :8000.
- `docker-compose.yml` — GPU backend + nginx frontend, HF cache volume.

## Commands
- Backend dev: `cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload`
- Frontend dev: `cd frontend && npm install && npm run dev`
- Full stack: `docker compose up --build` (needs NVIDIA container toolkit, ~8 GB VRAM)

## Conventions
- Keep all model parameters in the `TTSRequest` pydantic model; the frontend's
  Python-snippet panel mirrors them 1:1 — update both together.
- Frontend styling lives in the `css` template string in `App.jsx`
  (design tokens in the `T` object). No Tailwind build step.
- API errors must return clean JSON `detail` strings; the UI displays them verbatim.

## Roadmap (good next tasks)
1. Reference-audio upload endpoint (`POST /api/upload-ref`) → returns a server
   path usable as `reference_wav_path`; wire the Clone tab to a file picker.
2. Streaming synthesis via `model.generate_streaming` + chunked audio playback.
3. Job queue (e.g. simple asyncio queue or Redis) instead of 429-on-busy.
4. Rate limiting + API key auth for public deployments.
5. Playwright smoke test + pytest for the API.
6. History panel: keep the last N generations client-side with replay.
