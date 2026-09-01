"""候选生成：描述 → 2-3 个可试听的候选音频（同一句探测台词，公平对比）。

每个候选：{profile, audio_path, reason, engine_name}。
不可用的引擎候选自动跳过（无 key 的 MiniMax、未装模型的本地引擎），绝不报错中断。
"""

from __future__ import annotations

import re
from pathlib import Path

from ..core.models import VoiceProfile, VoicecastError
from ..core.settings import OUTPUTS_DIR
from ..engines.registry import EngineRegistry
from .recipe_translator import RecipeTranslator

PROBE_TEXT = "这就是我的声音。你看，像不像你心里想的那个角色？"


def _slug(desc: str) -> str:
    s = re.sub(r"[^\w\u4e00-\u9fff]+", "_", desc.strip())
    return s[:20] or "voice"


def generate_candidates(
    description: str,
    out_dir: Path | None = None,
    probe_text: str = PROBE_TEXT,
    top_k: int = 3,
    on_progress=None,
) -> dict:
    """返回 {description, source, summary, candidates: [...]}。
    on_progress: Callable[[float, str], None] | None —— 进度回调 (0~1, 消息)。"""
    translator = RecipeTranslator()
    result = translator.translate(description, top_k=top_k)
    registry = EngineRegistry()
    out_dir = out_dir or (OUTPUTS_DIR / "design" / _slug(description))
    out_dir.mkdir(parents=True, exist_ok=True)

    candidates = []
    errors = []
    n = len(result["candidates"])
    for i, cand in enumerate(result["candidates"], start=1):
        profile: VoiceProfile = cand["profile"]
        if on_progress:
            on_progress((i - 0.5) / max(n, 1), f"正在生成候选 {i}/{n}：{profile.id}…")
        try:
            engine = registry.route(profile)
        except VoicecastError as e:
            errors.append(f"{profile.id}: {e}")
            continue
        path = out_dir / f"{i:02d}_{profile.id}.wav"
        try:
            engine.synthesize(probe_text, profile, path)
            candidates.append({
                "index": i,
                "profile": profile,
                "audio": str(path),
                "engine": engine.name,
                "engine_explain": engine.explain(),
                "reason": cand["reason"],
                "params": profile.params,
            })
        except VoicecastError as e:
            errors.append(f"{profile.id}: {e}")

    result["candidates"] = candidates
    result["errors"] = errors
    result["out_dir"] = str(out_dir)
    return result
