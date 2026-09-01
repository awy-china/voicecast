"""后处理链：去 AI 味的四层听感处理（ffmpeg 实现，零额外依赖）。

层 ④ 听感层处理，按"自然度档位"生效：
- off      ：不处理（引擎裸输出）
- clean    ：轻处理——EQ 塑形 + 响度归一化（干净但去合成锐利感）
- natural  ：完整链——呼吸声注入 + 微颤动(jitter/vibrato) + EQ 塑形
             + 压缩限幅 + 微量混响 + LUFS 响度归一化（生产级"人味"）

配方通过 VoiceProfile.params["postprocess"] 控制档位（默认 natural）。

设计依据（配音专家视角）：
- 呼吸声：句首自然吸气 → "活人感"最强信号之一
- vibrato/tremolo 小深度：打破合成声的"等时规整"，模拟人声微颤动
- EQ：削 4-9kHz 齿音锐利感、补 300Hz 身体感、highpass 去隆隆声
- 压缩+限幅：模拟人声动态包络，TP=-1.5dB 防削波
- 微量混响：短房间感，避免"消声室"假干净
- loudnorm：I=-16 LUFS 生产响度标准（视频平台通用）
"""

from __future__ import annotations

import subprocess
from pathlib import Path

BREATH_SEC = 0.30   # 句首呼吸声时长
BREATH_LEVEL = 0.025  # 呼吸声增益（相对原音频）

# 完整链（natural）——顺序即信号流
NATURAL_FILTERS = [
    "highpass=f=80",
    "vibrato=f=5.5:d=0.15",
    "tremolo=f=4.5:d=0.1",
    "equalizer=f=300:t=q:w=1:g=2",
    "equalizer=f=5000:t=q:w=1:g=-2",
    "equalizer=f=9000:t=q:w=1:g=-1",
    "acompressor=threshold=-18dB:ratio=2.5:attack=10:release=150:makeup=1",
    "alimiter=limit=-1dB",
    "aecho=0.7:0.7:35:0.3",
    "loudnorm=I=-16:LRA=11:TP=-1.5",
]

# 轻链（clean）——只做听感基础
CLEAN_FILTERS = [
    "highpass=f=80",
    "equalizer=f=5000:t=q:w=1:g=-2",
    "alimiter=limit=-1dB",
    "loudnorm=I=-16:LRA=11:TP=-1.5",
]


def _breath_source(seconds: float = BREATH_SEC) -> str:
    """合成句首呼吸声（粉噪低通 + 淡入淡出包络，形似吸气）。"""
    return (
        f"anoisesrc=d={seconds}:c=pink:a={BREATH_LEVEL}:seed=42,"
        f"lowpass=f=700,afade=t=in:d={seconds * 0.7},"
        f"afade=t=out:st={seconds * 0.6}:d={seconds * 0.4}"
    )


def apply_chain(
    in_path: Path | str,
    out_path: Path | str,
    level: str = "natural",
) -> Path:
    """对音频应用后处理链，返回输出路径。

    level: off（跳过）/ clean（轻）/ natural（完整链，默认）。
    """
    in_path = Path(in_path)
    out_path = Path(out_path)
    if level == "off":
        if in_path != out_path:
            out_path.write_bytes(in_path.read_bytes())
        return out_path

    filters = NATURAL_FILTERS if level == "natural" else CLEAN_FILTERS

    if level == "natural":
        # 呼吸声 concat 到句首：ffmpeg 双输入（原音频 + lavfi 合成呼吸声）
        cmd = [
            "ffmpeg", "-y",
            "-i", str(in_path),
            "-f", "lavfi", "-i", _breath_source(),
            "-filter_complex",
            f"[1:a][0:a]concat=n=2:v=0:a=1[main];[main]{','.join(filters)}[out]",
            "-map", "[out]",
            "-ar", "24000", "-ac", "1",
            "-acodec", "pcm_s16le", str(out_path),
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-i", str(in_path),
            "-af", ",".join(filters),
            "-ar", "24000", "-ac", "1",
            "-acodec", "pcm_s16le", str(out_path),
        ]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=180)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"后处理链失败: {e.stderr.decode('utf-8', 'ignore')[-300:]}"
        ) from e
    return out_path


def postprocess_audio(
    wav_path: Path | str,
    level: str = "natural",
) -> Path:
    """原地后处理：处理结果覆盖原文件（引擎输出 → 后处理 → 覆盖）。"""
    wav_path = Path(wav_path)
    tmp = wav_path.with_suffix(".pp.wav")
    apply_chain(wav_path, tmp, level=level)
    tmp.replace(wav_path)
    return wav_path
