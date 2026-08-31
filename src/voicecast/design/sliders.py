"""滑杆微调：年龄/低沉/语速/明亮 → 配方参数。

参数单位按引擎约定换算：
- edge_tts: pitch 用 Hz（实测约 0.6Hz/岁）
- minimax: pitch 用 -5~+2 档位（约 0.08/岁）
- local: pitch 用音分 cents（约 12/岁）
"""

from __future__ import annotations

from ..core.models import VoiceProfile


def _pitch_scale(host: str) -> float:
    if host == "minimax":
        return 0.08
    if host == "local":
        return 12.0
    return 0.6  # edge_tts Hz/岁


def apply_sliders(
    profile: VoiceProfile,
    age_years: float | None = None,
    darkness: float = 0.0,      # -1(明亮轻快) ~ +1(低沉压迫)
    brightness: float = 0.0,    # -1 ~ +1
    speed: float | None = None,  # 0.5 ~ 1.5
) -> VoiceProfile:
    """在配方基础上叠加滑杆，返回新配方（不修改原对象）。"""
    p = profile.model_copy(deep=True)
    host = p.engine.host
    scale = _pitch_scale(host)

    pitch = float(p.params.get("pitch", 0))
    if age_years is not None:
        # 基准 25 岁；年龄越大越低沉
        pitch += (25 - age_years) * scale
    pitch -= darkness * scale * 8    # 越低沉越降调
    pitch += brightness * scale * 6
    p.params["pitch"] = round(pitch, 1)

    spd = float(p.params.get("speed", 1.0))
    if age_years is not None:
        spd -= max(0.0, age_years - 25) * 0.004   # 年龄越大越慢（60 岁 ≈ -14%）
    spd -= darkness * 0.04          # 越低沉越慢
    spd += brightness * 0.03
    if speed is not None:
        spd = speed
    p.params["speed"] = round(max(0.5, min(1.5, spd)), 3)
    return p
