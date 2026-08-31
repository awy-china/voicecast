"""核心数据模型：VoiceProfile / Role / Cast / Script / Project。

这是 VoiceCast 的数据契约（GitHub 仓库的"预留格式"本体）。
所有对象均可 JSON/YAML 序列化，git 可版本管理。
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class VoicecastError(Exception):
    """项目统一异常。"""


class DesignMethod(str, Enum):
    """音色设计方法。"""

    RECIPE = "recipe"      # 参数配方：底声 + pitch/speed/vol 等
    MIX = "mix"            # 多参考音色混合插值
    CLONE = "clone"        # 克隆自参考音频
    PRESET = "preset"      # 引擎内置预设


class Provenance(BaseModel):
    """音色溯源：'这声音哪来的'——合规门禁的数据基础。"""

    origin: Literal["original", "reference", "clone", "synthetic"] = "synthetic"
    authorized: bool = True
    ref_file: Optional[str] = None   # 参考音频路径（相对 recipes/ 或绝对路径）
    note: str = ""                   # 来源/授权说明


class EnginePref(BaseModel):
    """引擎偏好：归属硬约束 + 本地优先（独立性铁律）。"""

    host: str = "auto"               # auto / local / edge_tts / minimax / f5tts ...
    prefer_local: bool = True        # 本地可用时优先


class VoiceProfile(BaseModel):
    """音色配方——声音的最小单位。"""

    id: str
    name: str = ""
    design: DesignMethod = DesignMethod.RECIPE
    params: dict[str, Any] = Field(default_factory=dict)
    engine: EnginePref = Field(default_factory=EnginePref)
    provenance: Provenance = Field(default_factory=Provenance)
    tags: list[str] = Field(default_factory=list)
    description: str = ""            # 人类可读描述，设计器出候选时生成

    @field_validator("id")
    @classmethod
    def _id_ok(cls, v: str) -> str:
        if not v or not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError(f"非法音色 id: {v!r}（仅字母数字、下划线、连字符）")
        return v


class Role(BaseModel):
    """角色：引用一个 VoiceProfile + 角色级微调。"""

    id: str
    name: str
    voice: str                       # VoiceProfile.id
    default_emotion: str = "平静"
    pitch_offset: float = 0.0        # 角色级微调（叠加在配方参数上）
    speed_scale: float = 1.0

    @field_validator("id")
    @classmethod
    def _id_ok(cls, v: str) -> str:
        if not v or not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError(f"非法角色 id: {v!r}")
        return v


class Cast(BaseModel):
    """角色表：一部剧 = 一份文件。"""

    title: str = ""
    cast: dict[str, Role] = Field(default_factory=dict)

    def role(self, role_id: str) -> Role:
        try:
            return self.cast[role_id]
        except KeyError:
            raise VoicecastError(f"角色表中不存在角色: {role_id}") from None


class ScriptLine(BaseModel):
    """一句台词。"""

    role: str                        # Role.id 或【角色】标记中的名字
    text: str
    emotion: str = "平静"
    scene: str = "S00"
    line_no: int = 0
    priority: int = 5                # 1-9，越大越重要


class Script(BaseModel):
    """剧本：行集合。"""

    title: str = "untitled"
    lines: list[ScriptLine] = Field(default_factory=list)

    @property
    def roles(self) -> list[str]:
        seen: list[str] = []
        for ln in self.lines:
            if ln.role not in seen:
                seen.append(ln.role)
        return seen


class Project(BaseModel):
    """剧集工程：剧本 + 角色表 + 输出 + 预算 + 引擎顺序。"""

    name: str
    script_path: Path
    cast_path: Path
    output_dir: Path = Path("outputs")
    budget_per_episode: float = 0.0    # 0 = 不限
    engine_order: list[str] = Field(
        default_factory=lambda: ["local", "edge_tts", "minimax"]
    )
