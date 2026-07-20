"""Model loading, real or mocked."""

from __future__ import annotations

import asyncio
import logging
import time

import numpy as np

from . import config

logger = logging.getLogger("voxcpm-server")

MOCK_SAMPLE_RATE = 48000


class _MockTTSInner:
    sample_rate = MOCK_SAMPLE_RATE


class MockModel:
    """Stands in for `voxcpm.VoxCPM` when MOCK_TTS=1. Generates a short,
    deterministic sine-wave clip so the rest of the stack (encoding,
    streaming, queueing) can be exercised without a GPU or the real
    checkpoint."""

    tts_model = _MockTTSInner()

    def generate(self, text: str, **_kwargs) -> np.ndarray:
        duration_s = min(3.0, 0.5 + 0.02 * len(text))
        return _sine_wav(duration_s)

    def generate_streaming(self, text: str, **_kwargs):
        duration_s = min(3.0, 0.5 + 0.02 * len(text))
        chunk_s = 0.5
        t = 0.0
        while t < duration_s:
            this_chunk = min(chunk_s, duration_s - t)
            yield _sine_wav(this_chunk, phase_offset=t)
            t += this_chunk


def _sine_wav(duration_s: float, freq: float = 220.0, phase_offset: float = 0.0) -> np.ndarray:
    n = max(1, int(duration_s * MOCK_SAMPLE_RATE))
    t = np.arange(n) / MOCK_SAMPLE_RATE + phase_offset
    envelope = np.minimum(1.0, np.minimum(t - phase_offset, duration_s - (t - phase_offset)) * 20 + 0.05)
    return (0.2 * np.sin(2 * np.pi * freq * t) * envelope).astype(np.float32)


_model = None
_load_lock = asyncio.Lock()


async def get_model():
    global _model
    if _model is not None:
        return _model
    async with _load_lock:
        if _model is None:
            if config.MOCK_TTS:
                logger.info("MOCK_TTS=1 — using synthetic sine-wave model")
                _model = MockModel()
                return _model
            logger.info("Loading %s ...", config.MODEL_ID)
            t0 = time.time()
            from voxcpm import VoxCPM  # deferred: heavy import

            _model = await asyncio.to_thread(VoxCPM.from_pretrained, config.MODEL_ID)
            logger.info("Model ready in %.1fs", time.time() - t0)
    return _model


def is_loaded() -> bool:
    return _model is not None
