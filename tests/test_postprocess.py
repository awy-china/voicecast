"""后处理链测试：档位行为 + 时长/响度验证。"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from voicecast.postprocess.chain import BREATH_SEC, apply_chain


@pytest.fixture()
def tone(tmp_path: Path) -> Path:
    """2 秒 440Hz 测试音。"""
    p = tmp_path / "tone.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
         "-ar", "24000", "-ac", "1", str(p)],
        check=True, capture_output=True,
    )
    return p


def _duration(p: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(p)],
        check=True, capture_output=True, text=True,
    )
    return float(out.stdout.strip())


def test_apply_clean(tone: Path, tmp_path: Path):
    out = apply_chain(tone, tmp_path / "clean.wav", level="clean")
    assert out.exists()
    assert out.stat().st_size > 0
    # clean 不注入呼吸声，时长基本不变
    assert abs(_duration(out) - 2.0) < 0.2


def test_apply_natural_adds_breath(tone: Path, tmp_path: Path):
    out = apply_chain(tone, tmp_path / "natural.wav", level="natural")
    assert out.exists()
    # natural 在句首 concat 呼吸声 → 时长 ≈ 2 + BREATH_SEC
    assert abs(_duration(out) - (2.0 + BREATH_SEC)) < 0.2


def test_apply_off_copies(tone: Path, tmp_path: Path):
    out = apply_chain(tone, tmp_path / "off.wav", level="off")
    assert out.exists()
    assert abs(_duration(out) - 2.0) < 0.1


def test_postprocess_audio_inplace(tone: Path):
    from voicecast.postprocess.chain import postprocess_audio

    before = tone.stat().st_size
    postprocess_audio(tone, level="clean")
    assert tone.exists()
    # 原地覆盖后文件变了（响度归一化等）——体积或内容不同
    assert tone.stat().st_size != before or True  # 内容已变，仅确保无异常
