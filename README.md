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

# terminal 2 — UI on :5173 (proxies /api to :8000)
cd frontend
npm install
npm run dev
```

## API
`POST /api/tts` → `audio/wav`
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
  "prompt_text": null
}
```
`GET /api/health` · `GET /api/model-info`

## Responsible use
The model license forbids impersonation, fraud, and disinformation.
Label AI-generated speech clearly and get consent before cloning voices.
