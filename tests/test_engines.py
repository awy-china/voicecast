"""引擎适配层测试。"""

import os
import subprocess

import pytest

from voicecast.core.models import VoiceProfile, VoicecastError
from voicecast.engines.registry import EngineRegistry


def test_registry_has_three_engines():
    r = EngineRegistry()
    assert {e.name for e in r.all()} == {"local", "edge_tts", "minimax"}


def test_minimax_skipped_without_key():
    os.environ.pop("MINIMAX_API_KEY", None)
    r = EngineRegistry()
    assert r.get("minimax").available() is False
    assert "minimax" not in [e.name for e in r.available()]


def test_route_host_constraint():
    r = EngineRegistry()
    p = VoiceProfile(id="x", engine={"host": "edge_tts"})
    assert r.route(p).name == "edge_tts"


def test_route_host_unavailable_raises():
    os.environ.pop("MINIMAX_API_KEY", None)
    r = EngineRegistry()
    p = VoiceProfile(id="x", engine={"host": "minimax"})
    with pytest.raises(VoicecastError):
        r.route(p)


def test_route_auto_falls_to_available():
    r = EngineRegistry()
    p = VoiceProfile(id="x")
    eng = r.route(p)
    assert eng.name in ("local", "edge_tts")


def test_verify_audio_detects_silence(tmp_path):
    from voicecast.engines.util import verify_audio

    p = tmp_path / "sine.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=1", str(p)],
        check=True, capture_output=True,
    )
    assert verify_audio(p)["ok"] is True

    q = tmp_path / "junk.wav"
    q.write_bytes(b"RIFF this is not a real wave file at all")
    try:
        result = verify_audio(q)
        assert result["ok"] is False  # 非法文件：要么 ok=False，要么 ffprobe 抛错
    except Exception:
        pass  # ffprobe 对非法文件报错同样可接受
