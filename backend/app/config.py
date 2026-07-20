"""Environment-driven configuration, read once at import time."""

from __future__ import annotations

import os


def _bool(name: str, default: str) -> bool:
    return os.getenv(name, default) == "1"


MODEL_ID = os.getenv("MODEL_ID", "sumnim/VoxCPM2-Khmer")
LAZY_LOAD = _bool("LAZY_LOAD", "0")
MAX_TEXT_CHARS = int(os.getenv("MAX_TEXT_CHARS", "2000"))
ALLOWED_ORIGINS = [o for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o]

# When set, the server never imports/loads the real VoxCPM model. Every
# "generation" is a short synthetic sine-wave wav instead. Used for frontend
# dev without a GPU, CI, and local tests.
MOCK_TTS = _bool("MOCK_TTS", "0")

# Reference-audio upload (Feature: /api/upload-ref)
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/tmp/voxcpm-refs")
UPLOAD_MAX_BYTES = int(os.getenv("UPLOAD_MAX_MB", "20")) * 1024 * 1024
UPLOAD_MAX_DURATION_S = float(os.getenv("UPLOAD_MAX_DURATION_S", "60"))
UPLOAD_TTL_HOURS = float(os.getenv("UPLOAD_TTL_HOURS", "24"))
# Off by default: raw filesystem paths in reference_wav_path/prompt_wav_path
# let a client read any file the server process can see. Only enable on
# trusted, single-user deployments.
ALLOW_RAW_PATHS = _bool("ALLOW_RAW_PATHS", "0")

# Job queue (Feature: async /api/tts + /api/jobs)
MAX_QUEUE = int(os.getenv("MAX_QUEUE", "10"))
JOB_TTL_MIN = float(os.getenv("JOB_TTL_MIN", "15"))

# Auth + rate limiting
API_KEYS = {k for k in os.getenv("API_KEYS", "").split(",") if k}
RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "10"))
RATE_LIMIT_CHARS_PER_HOUR = int(os.getenv("RATE_LIMIT_CHARS_PER_HOUR", "20000"))
