"""成本路由（设计文档 §6）：归属硬约束 → 质量门槛 → 成本估算。

质量门槛（实测）：edge-tts pitch < -30Hz 会失真机械 → 自动升级更贵的引擎。
"""

from __future__ import annotations

from ..core.models import Project, VoiceProfile, VoicecastError
from ..engines.registry import DEFAULT_ORDER, Engine, EngineRegistry

EDGE_PITCH_FLOOR = -30  # edge-tts 降调失真阈值（实测）


def route_engine(
    profile: VoiceProfile,
    project: Project | None = None,
    registry: EngineRegistry | None = None,
) -> Engine:
    """规则一 + 质量门槛。返回选定引擎。"""
    registry = registry or EngineRegistry()
    order = list((project.engine_order if project else None) or DEFAULT_ORDER)

    # 归属硬约束
    host = profile.engine.host
    if host != "auto":
        eng = registry.get(host)
        if eng is None:
            raise VoicecastError(f"未知引擎: {host}")
        if not eng.available():
            raise VoicecastError(f"宿主引擎 {host} 不可用")
        return eng

    # 动态选择 + 质量门槛
    for name in order:
        eng = registry.get(name)
        if not eng or not eng.available():
            continue
        if name == "edge_tts" and _edge_quality_ok(profile) is False:
            continue  # 降调过深 → 自动升级
        return eng
    raise VoicecastError("没有任何引擎可用")


def _edge_quality_ok(profile: VoiceProfile) -> bool:
    pitch = float(profile.params.get("pitch", 0))
    return pitch >= EDGE_PITCH_FLOOR


def estimate_cost(text: str, engine: Engine) -> float:
    return engine.cost_per_char * len(text)
