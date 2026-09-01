"""音色生成：描述 → 最匹配的一个音色配方 → 生成试听音频。

设计决策（用户指令）：去掉"多候选"交互——描述直接出唯一结果，
不再让用户从 2-5 个候选里挑。规则层 match_candidates 保留 top_k 能力
供内部扩展，但产品入口（CLI/Web）一律单结果。

不可用引擎的配方在规则层已被过滤（根源），此处若仍有异常
（网络/限流等）只记录错误，绝不报错中断。
"""

from __future__ import annotations

import re
from pathlib import Path

from ..core.models import VoicecastError
from ..core.settings import OUTPUTS_DIR
from ..engines.registry import EngineRegistry
from .recipe_translator import RecipeTranslator

PROBE_TEXT = "这就是我的声音。你看，像不像你心里想的那个角色？"


def _slug(desc: str) -> str:
    s = re.sub(r"[^\w\u4e00-\u9fff]+", "_", desc.strip())
    return s[:20] or "voice"


def generate_voice(
    description: str,
    out_dir: Path | None = None,
    probe_text: str = PROBE_TEXT,
) -> dict:
    """描述 → 直接生成 1 个最匹配的音色。

    返回 {ok, profile, audio, engine, engine_explain, reason, params,
          source, summary, error?}
    """
    translator = RecipeTranslator()
    result = translator.translate(description, top_k=1)
    if not result["candidates"]:
        return {
            "ok": False,
            "error": result["summary"],
            "source": result["source"],
            "summary": result["summary"],
        }

    cand = result["candidates"][0]
    profile: VoiceProfile = cand["profile"]
    registry = EngineRegistry()
    out_dir = out_dir or (OUTPUTS_DIR / "design" / _slug(description))
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"01_{profile.id}.wav"

    try:
        engine = registry.route(profile)
        engine.synthesize(probe_text, profile, path)
    except VoicecastError as e:
        return {"ok": False, "profile": profile, "error": str(e),
                "source": result["source"], "summary": result["summary"]}

    return {
        "ok": True,
        "profile": profile,
        "audio": str(path),
        "engine": engine.name,
        "engine_explain": engine.explain(),
        "reason": cand["reason"],
        "params": profile.params,
        "source": result["source"],
        "summary": result["summary"],
    }
