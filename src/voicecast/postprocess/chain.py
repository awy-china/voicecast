"""后处理链：去 AI 味的听感处理（ffmpeg 实现，零额外依赖）。

层 ④ 听感层处理，按"自然度档位"生效：
- off      ：不处理（引擎裸输出）
- clean    ：轻处理——EQ 塑形 + 响度归一化（干净但去合成锐利感）
- natural  ：完整链——EQ 塑形 + 压缩限幅 + LUFS 响度归一化（生产级）
             （可选）呼吸声注入 → 见 postprocess_audio(breath=True)

## v0.3 修订（2026-09-16，依据 A/B 实测 + 故障定位）

**移除 aecho=0.7:0.7:35:0.3**
  35ms 短回声 = 梳状滤波。实测倒谱峰精确停在 35.0ms，是"金属感 / 空心感"的主因。
  四个不同形象（老年女/老年男/少女/青年男）的基线里它全部存在，移除后全部消失。

**移除 vibrato=f=5.5:d=0.15 + tremolo=f=4.5:d=0.1**
  恒定周期调制 = 机械抖动感。真人语音不存在恒定 5.5Hz 颤音，这是合成腔的重要来源。

**动态处理放柔**
  acompressor 2.5:1 → 1.8:1（attack 10→20ms、release 150→250ms）；
  alimiter -1dB → -1.5dB；EQ 收敛为 250Hz 补身体感 + 4kHz 轻削锐利感。

**呼吸声移出滤镜链（关键修复）**
  原实现用双输入 concat 把 0.3s 极低电平呼吸段接到句首，**再**让整段过滤镜链。
  该结构在「低电平起始段 + 调制滤波器 + 动态处理」三者同时存在时，
  有约 25–30% 概率把输出锁死成直流（crest≈1dB、频谱重心≈1Hz、全段恒定值），
  且 **ffmpeg 退出码为 0、stderr 正常**，流水线完全无感（详见 BUG-直流锁死-定位报告）。
  现改为：滤镜链只跑语音本体（实测 0/40 故障），呼吸声在链后按输出峰值比例拼接，
  且默认关闭 —— 配方 `params["breath"] = true` 才启用。

**新增产物健康校验 + 自动重试**
  三道判据（crest / 频谱重心 / DC 偏置），不合格自动重试至多 MAX_RETRY 次。

设计依据（配音专家视角）：
- EQ：补 250Hz 身体感、削 4kHz 齿音锐利感、highpass 去隆隆声
- 压缩+限幅：模拟人声动态包络，TP=-1.5dB 防削波
- loudnorm：I=-16 LUFS 生产响度标准（视频平台通用）
- 呼吸声（可选）：句首自然吸气 → "活人感"信号之一
"""

from __future__ import annotations

import subprocess
from pathlib import Path

BREATH_SEC = 0.30        # 句首呼吸声时长
BREATH_LEVEL = 0.030     # 呼吸声电平（相对输出峰值，链后按比例施加）

# 健康判据（依据实测：正常语音 vs 直流锁死产物）
#
# ⚠️ 判据设计要点：**crest 不能当主判据**。
#   纯正弦音天然只有 3.01dB crest（测试夹具就是 440Hz 正弦），
#   若把 crest<6dB 判为坏会把合法的音调信号一并毙掉（实测踩过）。
#   真正区分「直流锁死」的是 **频谱重心** 与 **DC 偏置**：
#     正常语音       crest 14–17dB   centroid 375–1093Hz   |DC|≈0.000
#     直流锁死产物   crest ≈1dB      centroid ≈0–2Hz        |DC|≈0.81
#   故：crest 只做"低于纯正弦"的兜底硬伤判定。
MIN_CREST_DB = 2.0       # 纯正弦≈3.0dB；直流锁死≈1.0dB → 低于 2dB 判硬伤
MIN_CENTROID_HZ = 120.0  # 正常语音 375–1093Hz；直流锁死 ≈0–2Hz
MAX_ABS_DC = 0.05        # 正常 ≈0.000；直流锁死 ≈-0.81
MAX_RETRY = 3

# 完整链（natural）——顺序即信号流
NATURAL_FILTERS = [
    "highpass=f=70",
    "equalizer=f=250:t=q:w=1:g=1.5",
    "equalizer=f=4000:t=q:w=1:g=-1.5",
    "acompressor=threshold=-20dB:ratio=1.8:attack=20:release=250",
    "alimiter=limit=-1.5dB",
    "loudnorm=I=-16:LRA=11:TP=-1.5",
]

# 轻链（clean）——只做归一化与基础听感
CLEAN_FILTERS = [
    "highpass=f=70",
    "loudnorm=I=-16:LRA=11:TP=-1.5",
]


def _breath_source(seconds: float = BREATH_SEC) -> str:
    """合成句首呼吸声（粉噪低通 + 淡入淡出包络，形似吸气）。

    注意：仅供 postprocess_audio(breath=True) 的**链后**拼接使用；
    不要再把它 concat 进滤镜链（会触发直流锁死，见模块 docstring）。
    """
    return (
        f"anoisesrc=d={seconds}:c=pink:a=1.0:seed=42:r=24000,"
        f"lowpass=f=700,afade=t=in:d={seconds * 0.7},"
        f"afade=t=out:st={seconds * 0.6}:d={seconds * 0.4}"
    )


def health_metrics(path: Path | str) -> dict:
    """产物健康指标：crest / 频谱重心 / DC 偏置。"""
    import numpy as np
    import soundfile as sf

    y, sr = sf.read(str(path), dtype="float32")
    if y.ndim > 1:
        y = y.mean(axis=1)
    if len(y) < 256:
        return {"ok": False, "reason": "音频过短", "crest": 0.0, "centroid": 0.0, "dc": 0.0}
    peak = float(np.max(np.abs(y)))
    rms = float(np.sqrt(np.mean(y ** 2)))
    db = lambda x: 20 * np.log10(max(x, 1e-12))  # noqa: E731
    spec = np.abs(np.fft.rfft(y * np.hanning(len(y)))) ** 2
    freqs = np.fft.rfftfreq(len(y), 1 / sr)
    centroid = float((spec * freqs).sum() / max(spec.sum(), 1e-12))
    crest = db(peak) - db(rms)
    dc = float(y.mean())

    if centroid < MIN_CENTROID_HZ:
        return {"ok": False, "reason": f"频谱重心 {centroid:.0f}Hz < {MIN_CENTROID_HZ}Hz（疑似直流锁死）",
                "crest": crest, "centroid": centroid, "dc": dc}
    if abs(dc) > MAX_ABS_DC:
        return {"ok": False, "reason": f"DC 偏置 {dc:+.4f} > {MAX_ABS_DC}",
                "crest": crest, "centroid": centroid, "dc": dc}
    if crest < MIN_CREST_DB:
        return {"ok": False, "reason": f"crest {crest:.1f}dB < {MIN_CREST_DB}dB（低于纯正弦，疑似直流锁死）",
                "crest": crest, "centroid": centroid, "dc": dc}
    return {"ok": True, "reason": "", "crest": crest, "centroid": centroid, "dc": dc}


def apply_chain(
    in_path: Path | str,
    out_path: Path | str,
    level: str = "natural",
    breath: bool = False,
) -> Path:
    """对音频应用后处理链，返回输出路径。

    level: off（跳过）/ clean（轻）/ natural（完整链，默认）。
    breath: 是否在链后拼接句首呼吸声（默认关闭）。
    产物会做健康校验，不合格自动重试至多 MAX_RETRY 次。
    """
    in_path = Path(in_path)
    out_path = Path(out_path)
    if level == "off":
        if in_path != out_path:
            out_path.write_bytes(in_path.read_bytes())
        return out_path

    filters = NATURAL_FILTERS if level == "natural" else CLEAN_FILTERS
    cmd = [
        "ffmpeg", "-y",
        "-i", str(in_path),
        "-af", ",".join(filters),
        "-ar", "24000", "-ac", "1",
        "-acodec", "pcm_s16le", str(out_path),
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)

    last = None
    for attempt in range(1, MAX_RETRY + 1):
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=180)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"后处理链失败: {e.stderr.decode('utf-8', 'ignore')[-300:]}"
            ) from e
        last = health_metrics(out_path)
        if last["ok"]:
            break
    else:
        raise RuntimeError(
            f"后处理链产物健康校验失败（重试 {MAX_RETRY} 次）: {last['reason']}"
        )

    if breath:
        _prepend_breath(out_path)
    return out_path


def _prepend_breath(wav_path: Path, seconds: float = BREATH_SEC) -> None:
    """在链后把呼吸声拼到句首（numpy 实现 —— 确定性，不经过滤镜图）。

    电平按**输出音频的峰值**比例施加，保证与语音的听感比例稳定。
    """
    import numpy as np
    import soundfile as sf

    tmp = wav_path.with_suffix(".breath.wav")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", _breath_source(seconds),
         "-ar", "24000", "-ac", "1", "-acodec", "pcm_s16le", str(tmp)],
        check=True, capture_output=True, timeout=60,
    )
    yb, sr_b = sf.read(str(tmp), dtype="float32")
    y, sr = sf.read(str(wav_path), dtype="float32")
    if y.ndim > 1:
        y = y.mean(axis=1)
    if yb.ndim > 1:
        yb = yb.mean(axis=1)
    if sr_b != sr:  # 兜底：重采样呼吸声
        idx = np.linspace(0, len(yb) - 1, int(len(yb) * sr / sr_b))
        yb = np.interp(idx, np.arange(len(yb)), yb)
    peak = float(np.max(np.abs(y))) or 1.0
    yb = yb * (BREATH_LEVEL * peak / max(float(np.max(np.abs(yb))), 1e-9))
    merged = np.concatenate([yb.astype("float32"), y.astype("float32")])
    sf.write(str(wav_path), merged, sr, subtype="PCM_16")
    tmp.unlink(missing_ok=True)


def postprocess_audio(
    wav_path: Path | str,
    level: str = "natural",
    breath: bool = False,
) -> Path:
    """原地后处理：处理结果覆盖原文件（引擎输出 → 后处理 → 覆盖）。

    breath 默认 False —— 呼吸声注入是可选特性，且必须走链后拼接路径。
    """
    wav_path = Path(wav_path)
    tmp = wav_path.with_suffix(".pp.wav")
    apply_chain(wav_path, tmp, level=level, breath=breath)
    tmp.replace(wav_path)
    return wav_path
