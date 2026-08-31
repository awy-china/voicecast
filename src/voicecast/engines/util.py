"""音频校验工具：每句生成后实测（时长/静音/削波），杜绝"纸面能用"。"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


def ffprobe_info(path: Path) -> dict:
    """返回 {duration, mean_volume, max_volume}。

    ffprobe 拿时长；volumedetect 是 ffmpeg 滤镜（ffprobe 的 -af 不认），
    用 ffmpeg 跑一遍解析 stderr。
    """
    r1 = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", str(path)],
        capture_output=True, text=True, timeout=60,
    )
    if r1.returncode != 0:
        raise RuntimeError(f"ffprobe 失败: {r1.stderr.strip()}")
    duration = float(
        (json.loads(r1.stdout or "{}").get("format") or {}).get("duration", 0) or 0
    )

    r2 = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(path), "-af", "volumedetect",
         "-f", "null", "-"],
        capture_output=True, text=True, timeout=120,
    )
    mean_v, max_v = -91.0, -91.0
    if r2.returncode == 0:
        m = re.search(r"mean_volume:\s*(-?[\d.]+) dB", r2.stderr)
        x = re.search(r"max_volume:\s*(-?[\d.]+) dB", r2.stderr)
        if m:
            mean_v = float(m.group(1))
        if x:
            max_v = float(x.group(1))
    return {"duration": duration, "mean_volume": mean_v, "max_volume": max_v}


def verify_audio(path: Path, min_duration: float = 0.4) -> dict:
    """校验规则：够长、非静音、无明显削波。返回 {ok, reason, **info}。"""
    info = ffprobe_info(path)
    issues: list[str] = []
    if info["duration"] < min_duration:
        issues.append(f"时长过短 {info['duration']:.2f}s")
    if info["max_volume"] < -60:
        issues.append(f"疑似静音 max={info['max_volume']:.1f}dB")
    if info["max_volume"] > -0.05:
        issues.append(f"疑似削波 max={info['max_volume']:.1f}dB")
    return {"ok": not issues, "reason": "; ".join(issues), **info}
