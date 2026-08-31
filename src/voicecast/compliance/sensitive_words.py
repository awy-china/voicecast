"""敏感词过滤：生成前检查，可插拔。

内置轻量词库（明显违法内容）；可通过环境变量 VOICECAST_SENSITIVE_FILE
指向自定义词库文件（每行一个词）扩展。留空列表 = 不拦截。
"""

from __future__ import annotations

import os
from pathlib import Path

BUILTIN_WORDS: list[str] = [
    "枪支买卖",
    "制毒",
    "炸弹制作",
    "暗杀教程",
    "儿童色情",
    "恐怖袭击",
    "买卖器官",
]

_custom: list[str] | None = None


def _custom_words() -> list[str]:
    global _custom
    if _custom is None:
        f = os.environ.get("VOICECAST_SENSITIVE_FILE")
        if f and Path(f).exists():
            _custom = [
                w.strip() for w in Path(f).read_text(encoding="utf-8").splitlines()
                if w.strip() and not w.startswith("#")
            ]
        else:
            _custom = []
    return _custom


def check_text(text: str) -> list[str]:
    """返回命中的违规词（空 = 通过）。"""
    hits: list[str] = []
    for w in [*BUILTIN_WORDS, *_custom_words()]:
        if w in text:
            hits.append(w)
    return hits
