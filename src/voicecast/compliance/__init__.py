"""合规门禁：音色溯源 + 克隆门禁 + 敏感词过滤。

这是 GitHub 审核的硬要求，也是 MiniMax 没有的信任卖点。
"""

from .clone_gate import CLONE_DECLARATION, clone_gate_check
from .provenance import provenance_check
from .sensitive_words import check_text

__all__ = [
    "CLONE_DECLARATION",
    "clone_gate_check",
    "provenance_check",
    "check_text",
]
