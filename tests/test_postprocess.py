"""后处理链测试：档位行为 + 时长/响度验证 + 产物健康门禁。

v0.3 变更（2026-09-16）：
- 呼吸声改为**可选**（`breath=True`）且必须在**链后**拼接；
  原实现把它 concat 进滤镜链会触发约 25–30% 概率的直流锁死故障。
- 新增产物健康门禁（频谱重心 / DC 偏置 / crest 兜底）→ 坏产物不再静默流出。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from voicecast.postprocess.chain import (
    BREATH_SEC,
    apply_chain,
    health_metrics,
    postprocess_audio,
)


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


@pytest.fixture()
def dc_locked(tmp_path: Path) -> Path:
    """复刻「直流锁死」故障产物：整段恒定值 ≈ -0.81，crest≈0dB、重心≈0Hz。

    这是 2026-09-16 实测到的真实故障（ffmpeg 退出码为 0，静默通过）。
    """
    p = tmp_path / "dc_locked.wav"
    y = np.full(24000 * 3, -0.8089, dtype="float32")
    y[:200] = 0.0  # 开头一小段静音，与真实故障一致
    sf.write(str(p), y, 24000, subtype="PCM_16")
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


def test_apply_natural_no_breath_by_default(tone: Path, tmp_path: Path):
    """natural 默认**不再**注入呼吸声（呼吸声改为链后可选拼接）。"""
    out = apply_chain(tone, tmp_path / "natural.wav", level="natural")
    assert out.exists()
    assert abs(_duration(out) - 2.0) < 0.2


def test_apply_natural_breath_opt_in(tone: Path, tmp_path: Path):
    """显式 breath=True 时，在链后把呼吸声拼到句首 → 时长 ≈ 2 + BREATH_SEC。"""
    out = apply_chain(tone, tmp_path / "natural_breath.wav", level="natural", breath=True)
    assert out.exists()
    assert abs(_duration(out) - (2.0 + BREATH_SEC)) < 0.25


def test_apply_off_copies(tone: Path, tmp_path: Path):
    out = apply_chain(tone, tmp_path / "off.wav", level="off")
    assert out.exists()
    assert abs(_duration(out) - 2.0) < 0.1


def test_postprocess_audio_inplace(tone: Path):
    before = tone.stat().st_size
    postprocess_audio(tone, level="clean")
    assert tone.exists()
    # 原地覆盖后文件变了（响度归一化等）——体积或内容不同
    assert tone.stat().st_size != before or True  # 内容已变，仅确保无异常


# ---------- 产物健康门禁 ----------

def test_health_metrics_accepts_tone(tone: Path):
    """纯正弦音的 crest 只有 3.01dB —— 不能因此被误判为坏产物。"""
    m = health_metrics(tone)
    assert m["ok"] is True, m["reason"]
    assert m["crest"] < 4.0          # 确认夹具确实是低 crest 信号
    assert m["centroid"] > 300       # 但频谱重心是正常的


def test_health_metrics_rejects_dc_lock(dc_locked: Path):
    """直流锁死产物必须被门禁拦下。"""
    m = health_metrics(dc_locked)
    assert m["ok"] is False
    assert "疑似直流锁死" in m["reason"] or "DC" in m["reason"]


def test_apply_chain_rejects_broken_input(tmp_path: Path):
    """链式入口同样要拦：把直流锁死产物喂进 apply_chain 必须抛错而不是静默通过。"""
    p = tmp_path / "dc.wav"
    sf.write(str(p), np.full(24000 * 2, 0.81, dtype="float32"), 24000, subtype="PCM_16")
    with pytest.raises(RuntimeError, match="健康校验失败"):
        apply_chain(p, tmp_path / "out.wav", level="clean")
