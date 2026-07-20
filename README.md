# VoxCPM2-Khmer · Speech Studio

Production-ready web studio for the [sumnim/VoxCPM2-Khmer](https://huggingface.co/sumnim/VoxCPM2-Khmer)
text-to-speech model — Khmer-specialized fine-tune of VoxCPM2 (2B params,
30 languages, 48 kHz output, Apache-2.0).

## Features
- **Speak** — Khmer TTS with sample presets, `cfg_value` / `inference_timesteps`
  controls, normalize / denoise / retry toggles
- **Voice design** — build a voice from a natural-language description, no reference audio
- **Clone** — basic and "ultimate" (audio + transcript) voice cloning
- **Live Python panel** — every control mirrored as a ready-to-run `voxcpm` snippet
- FastAPI backend with health checks, request validation, and GPU concurrency guard

## Quick start (Docker, recommended)
Requires an NVIDIA GPU (~8 GB VRAM) and the NVIDIA Container Toolkit.

```bash
docker compose up --build
# first start downloads the 2B checkpoint into the hf-cache volume
```
Open http://localhost:8080

## Local development
```bash
# terminal 1 — API on :8000
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
# no GPU? set MOCK_TTS=1 to skip loading the real model and get a synthetic
# sine-wave clip back instead — same API shape, useful for frontend dev/CI.

# terminal 2 — UI on :5173 (proxies /api to :8000)
cd frontend
npm install
npm run dev
```

## API

### `POST /api/tts` → `audio/wav`
```json
{
  "text": "សួស្តី! សូមស្វាគមន៍",
  "cfg_value": 2.0,
  "inference_timesteps": 10,
  "normalize": true,
  "denoise": true,
  "retry_badcase": true,
  "reference_wav_path": null,
  "prompt_wav_path": null,
  "prompt_text": null,
  "reference_ref_id": null,
  "prompt_ref_id": null
}
```
`reference_ref_id` / `prompt_ref_id` are ids returned by `POST /api/upload-ref` and are the
recommended way to pass reference audio. `reference_wav_path` / `prompt_wav_path` (raw
server-side paths) only work when the server has `ALLOW_RAW_PATHS=1` set — disabled by
default because a client-supplied path lets anyone read any file the server process can see.

### `POST /api/upload-ref` → reference-audio upload
Multipart form with a `file` field (WAV, MP3, FLAC, M4A, or OGG; ≤ 20 MB; ≤ 60s). The
server converts it to 16 kHz mono WAV, stores it under `UPLOAD_DIR` with a UUID name, and
deletes it after `UPLOAD_TTL_HOURS` (default 24h).
```json
{ "ref_id": "5f2c...", "duration_s": 4.2, "filename": "speaker.wav" }
```
Use `ref_id` as `reference_ref_id` / `prompt_ref_id` in a subsequent `/api/tts` call.

### `POST /api/tts-stream` → chunked `audio/pcm;rate=48000`
Same request body as `/api/tts`. Instead of a WAV file, the response is chunked raw
**16-bit little-endian PCM, mono**, at the rate given in the `X-Sample-Rate` header —
a WAV container needs the total byte length up front, which isn't available while
streaming. The frontend decodes each chunk into a Web Audio `AudioBuffer` and schedules
it for playback as it arrives, so audio starts before generation finishes; once the
stream ends, the accumulated PCM is wrapped into a WAV blob client-side so downloading
still works. Returns 429 (same `detail` shape as `/api/tts`) if a synthesis is already
in progress.

### `GET /api/health` · `GET /api/model-info`
`model-info` includes `allow_raw_paths` and `mock` so the frontend can adapt its UI
(e.g. only showing the raw server-path field when raw paths are actually accepted).

All error responses are `{"detail": "<human-readable message>"}` — the frontend shows
`detail` verbatim, so backend errors should be written for end users, not developers.

## Responsible use
The model license forbids impersonation, fraud, and disinformation.
Label AI-generated speech clearly and get consent before cloning voices.
