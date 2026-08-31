"""克隆门禁：仅允许克隆自有授权声音。

- 界面/CLI 使用前必须展示声明
- 克隆型配方的 provenance.authorized 必须为 True 且带参考音频记录
"""

from __future__ import annotations

from ..core.models import DesignMethod, VoiceProfile
from .provenance import provenance_check

CLONE_DECLARATION = (
    "【克隆门禁声明】\n"
    "本工具仅允许克隆你拥有合法授权的声音：\n"
    "  1. 你自己录制的声音；\n"
    "  2. 你获得明确授权使用的他人声音；\n"
    "  3. 公开的合成音色（如引擎预设/种子音色）。\n"
    "禁止克隆名人、公众人物或任何未授权声音，违者自行承担法律责任。\n"
    "请确认：你即将克隆/使用的参考音频满足上述条件？"
)


def clone_gate_check(profile: VoiceProfile) -> list[str]:
    """克隆/混合型配方过门禁，返回违规项（空 = 通过）。"""
    issues = provenance_check(profile)
    if profile.design in (DesignMethod.CLONE, DesignMethod.MIX):
        if not profile.provenance.authorized:
            issues.append("违反克隆门禁：来源未授权")
    return issues
