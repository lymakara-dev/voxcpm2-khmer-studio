from __future__ import annotations


def test_tts_stream_returns_chunked_pcm(client):
    with client.stream("POST", "/api/tts-stream", json={"text": "hello there"}) as res:
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("audio/pcm")
        assert "X-Sample-Rate" in res.headers
        total = 0
        for chunk in res.iter_bytes():
            total += len(chunk)
        assert total > 0
        assert total % 2 == 0  # 16-bit samples
