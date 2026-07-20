from __future__ import annotations

import os
import tempfile

# Must happen before `app.*` is ever imported — config.py reads these at
# import time and MOCK_TTS gates whether the real (heavy, GPU-only) voxcpm
# package gets imported at all.
os.environ.setdefault("MOCK_TTS", "1")
os.environ.setdefault("UPLOAD_DIR", tempfile.mkdtemp(prefix="voxcpm-test-refs-"))

import time

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

import app.main as main_module
from app import auth as auth_module
from app import config
from app import jobs as jobs_module


@pytest.fixture(scope="session")
def client():
    """Session-scoped: the app's lifespan starts the worker loop bound to
    module-level asyncio primitives (jobs._wakeup, main._model_lock).
    Tearing lifespan down and back up per test would recreate the event
    loop while those singletons persist, which hangs the next test's
    synthesis. `_reset_state` below clears the mutable state between
    tests instead."""
    with TestClient(main_module.app) as c:
        yield c


@pytest.fixture(autouse=True)
def _reset_state():
    """Module-level singletons (job table/queue, rate-limit buckets, the
    model lock) persist across the whole test session — wait out any job
    still running from the previous test (so e.g. /api/tts-stream's
    lock-contention check doesn't flake) and clear the rest before every
    test so one test's traffic can't trip another's rate limit or leave
    stale jobs."""
    deadline = time.time() + 3.0
    while (jobs_module._queue or (main_module._model_lock and main_module._model_lock.locked())) and time.time() < deadline:
        time.sleep(0.01)
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
