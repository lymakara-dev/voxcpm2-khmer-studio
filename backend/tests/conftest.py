from __future__ import annotations

import os
import tempfile

# Must happen before `app.*` is ever imported — config.py reads these at
# import time and MOCK_TTS gates whether the real (heavy, GPU-only) voxcpm
# package gets imported at all.
os.environ.setdefault("MOCK_TTS", "1")
os.environ.setdefault("UPLOAD_DIR", tempfile.mkdtemp(prefix="voxcpm-test-refs-"))

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

import app.main as main_module
from app import auth as auth_module
from app import config
from app import jobs as jobs_module


@pytest.fixture
def client():
    with TestClient(main_module.app) as c:
        yield c


@pytest.fixture(autouse=True)
def _reset_state():
    """Module-level singletons (job table/queue, rate-limit buckets) persist
    across the whole test session — clear them before every test so one
    test's traffic can't trip another's rate limit or leave stale jobs."""
    jobs_module._jobs.clear()
    jobs_module._queue.clear()
    auth_module.request_limiter._hits.clear()
    auth_module.char_limiter._hits.clear()
    yield


@pytest.fixture
def sample_wav_bytes():
    sr = 44100
    t = np.linspace(0, 1.0, sr, endpoint=False)
    data = (0.1 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    import io

    buf = io.BytesIO()
    sf.write(buf, data, sr, format="WAV")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def _unlimited_rate_limits(monkeypatch):
    """Most tests aren't about rate limiting — give them effectively
    infinite budget so unrelated assertions don't flake under load. Tests
    that exercise the limiter itself override `.limit` back down."""
    monkeypatch.setattr(auth_module.request_limiter, "limit", 10_000)
    monkeypatch.setattr(auth_module.char_limiter, "limit", 10_000_000)
