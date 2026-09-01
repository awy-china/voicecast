"""引擎注册与成本路由（§6 规则一骨架；质量门槛/预算在 pipeline/router 强化）。"""

from __future__ import annotations

from ..core.models import VoiceProfile, VoicecastError
from .base import Engine
from .edge_tts_engine import EdgeTTSEngine
from .gpt_sovits_engine import GPTSovitsEngine
from .local_engine import LocalEngine
from .minimax_engine import MiniMaxEngine

# 成本序：本地免费优先；GPT-SoVITS 是"质量档"（服务启动才参与路由）
DEFAULT_ORDER = ["local", "gpt_sovits", "edge_tts", "minimax"]


class EngineRegistry:
    def __init__(self, engines: list[Engine] | None = None) -> None:
        self._engines: dict[str, Engine] = {
            e.name: e
            for e in (engines if engines is not None
                      else [LocalEngine(), GPTSovitsEngine(),
                            EdgeTTSEngine(), MiniMaxEngine()])
        }

    def all(self) -> list[Engine]:
        return list(self._engines.values())

    def get(self, name: str) -> Engine | None:
        return self._engines.get(name)

    def available(self) -> list[Engine]:
        return [e for e in self._engines.values() if e.available()]

    def route(self, profile: VoiceProfile, order: list[str] | None = None) -> Engine:
        """规则一（硬约束）：音色归谁就走谁；auto 则按成本序取第一个可用。"""
        order = order or DEFAULT_ORDER
        host = profile.engine.host
        if host != "auto":
            eng = self._engines.get(host)
            if eng is None:
                raise VoicecastError(f"未知引擎: {host}")
            if not eng.available():
                raise VoicecastError(
                    f"宿主引擎 {host} 不可用（未安装模型/未配置 key/依赖缺失）"
                )
            return eng
        for name in order:
            eng = self._engines.get(name)
            if eng and eng.available():
                return eng
        raise VoicecastError(
            "没有任何引擎可用：本地引擎未装模型、edge-tts 依赖缺失、"
            "MiniMax 未配置 key。请先运行 scripts/setup_local_engine.sh 或安装依赖。"
        )
