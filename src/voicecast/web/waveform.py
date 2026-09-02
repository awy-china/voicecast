"""波形工具：wav → 降采样波形点（前端 canvas 可视化，零依赖）。"""

from __future__ import annotations

import struct
import wave
from pathlib import Path


def wav_waveform(
    path: Path | str, points: int = 120, db_floor: float = -55.0
) -> list[float]:
    """读取 16-bit PCM wav，返回归一化到 [0,1] 的波形包络点（RMS 平滑）。

    - 用 RMS 而非峰值：视觉更接近人耳响度感知
    - db_floor: 静音压缩到 -55dB 以下视为 0（视觉干净）
    """
    path = Path(path)
    try:
        with wave.open(str(path), "rb") as w:
            n = w.getnframes()
            ch = w.getnchannels()
            sw = w.getsampwidth()
            fr = w.getframerate()
            raw = w.readframes(n)
    except Exception:  # noqa: BLE001  非标准 wav（如 mp3 残留）返回平坦波形
        return [0.0] * points

    if sw != 2:
        return [0.0] * points  # 仅支持 16-bit（引擎输出统一为 16-bit）
    samples = struct.unpack(f"<{len(raw) // 2}h", raw)

    # 多声道取平均
    if ch > 1:
        samples = [sum(samples[i : i + ch]) / ch for i in range(0, len(samples), ch)]

    # 等分到 points 段，每段算 RMS → dB → 归一化
    seg = max(1, len(samples) // points)
    out: list[float] = []
    peak = 0.0
    for i in range(points):
        chunk = samples[i * seg : (i + 1) * seg]
        if not chunk:
            out.append(0.0)
            continue
        rms = (sum(x * x for x in chunk) / len(chunk)) ** 0.5
        peak = max(peak, rms)
        out.append(rms)
    if peak <= 0:
        return [0.0] * points

    # 归一化：RMS/peak 到 dB，然后线性映射 [db_floor, 0] → [0, 1]
    import math

    norm = []
    for r in out:
        db = 20 * math.log10(max(r / peak, 1e-6))
        v = (db - db_floor) / (0 - db_floor)
        norm.append(max(0.0, min(1.0, v)))
    return norm
