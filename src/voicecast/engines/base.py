"""引擎适配层统一接口：所有引擎只实现 synthesize；路由/调度只依赖本接口。

这就是"引擎无关"的落地点——MiniMax / edge-tts / 本地引擎都是插件。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..core.models import VoiceProfile


class Engine(ABC):
    """引擎抽象。"""

    name: str = "base"
    display_name: str = "Base"

    @abstractmethod
    def available(self) -> bool:
        """本引擎当前是否可用（依赖、模型、key 就绪）。"""

    @abstractmethod
    def synthesize(
        self, text: str, profile: VoiceProfile, out_path: Path, emotion: str = ""
    ) -> Path:
        """生成台词音频到 out_path（wav），返回路径。失败抛 VoicecastError。"""

    @property
    def cost_per_char(self) -> float:
        """元/字符。0 = 免费。"""
        return 0.0

    def explain(self) -> str:
        return self.display_name
