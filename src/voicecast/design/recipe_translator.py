"""配方翻译器：描述 → 候选配方。

双后端（独立性铁律）：
1. LLM（DEEPSEEK_API_KEY 存在时）：配音导演视角，选候选 + 参数微调建议
2. 规则引擎（永远可用）：关键词匹配配方库
任何 LLM 失败自动降级规则引擎，绝不阻塞主流程。
"""

from __future__ import annotations

import json
import os
from typing import Optional

import httpx

from ..core.io import load_recipe_library
from ..core.models import VoiceProfile
from .recipe_rules import match_candidates

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
PROBE_LLM = """你是配音导演。下面是音色配方库（JSON）。请为需求挑选最匹配的 2-3 个候选，
并给出参数微调建议（pitch 单位以配方为准；speed 为倍率 0.5~1.5）与一句选角理由。

配方库:
{library}

需求: {description}

只输出 JSON，不要任何其他文字：
{{"candidates":[{{"id":"配方id","pitch_delta":0,"speed_delta":0.0,"reason":"选角理由"}}],"summary":"整体判断一句话"}}"""


class RecipeTranslator:
    """描述 → 2-3 个候选配方（含微调建议与理由）。"""

    def __init__(self) -> None:
        self._library = load_recipe_library()

    def _llm_available(self) -> bool:
        return bool(os.environ.get("DEEPSEEK_API_KEY"))

    def _call_llm(self, description: str) -> dict | None:
        library_dump = json.dumps(
            [
                {"id": p.id, "name": p.name, "description": p.description,
                 "params": p.params, "tags": p.tags}
                for p in self._library.values()
            ],
            ensure_ascii=False,
        )
        body = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "user", "content": PROBE_LLM.format(
                    library=library_dump, description=description)}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.4,
        }
        try:
            r = httpx.post(
                DEEPSEEK_URL,
                headers={"Authorization": f"Bearer {os.environ['DEEPSEEK_API_KEY']}"},
                json=body, timeout=90,
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
            return json.loads(content)
        except Exception:
            return None

    def _apply_deltas(self, profile: VoiceProfile, pitch_delta: float, speed_delta: float) -> VoiceProfile:
        p = profile.model_copy(deep=True)
        cur_pitch = float(p.params.get("pitch", 0))
        cur_speed = float(p.params.get("speed", 1.0))
        p.params["pitch"] = cur_pitch + pitch_delta
        p.params["speed"] = max(0.5, min(1.5, cur_speed + speed_delta))
        return p

    def translate(self, description: str, top_k: int = 3) -> dict:
        """返回 {source, candidates: [{profile, reason}], summary}。"""
        if self._llm_available():
            data = self._call_llm(description)
            if data and data.get("candidates"):
                out: list[dict] = []
                for c in data["candidates"]:
                    profile = self._library.get(c.get("id"))
                    if profile is None:
                        continue
                    out.append({
                        "profile": self._apply_deltas(profile,
                                                      float(c.get("pitch_delta", 0)),
                                                      float(c.get("speed_delta", 0))),
                        "reason": c.get("reason", ""),
                    })
                if out:
                    return {"source": "llm", "candidates": out[:top_k],
                            "summary": data.get("summary", "")}

        scored = match_candidates(description, top_k=top_k, library=self._library)
        return {
            "source": "rules",
            "candidates": [{"profile": p, "reason": "命中: " + "、".join(hits)}
                           for p, _s, hits in scored],
            "summary": "规则引擎匹配（未配置 DEEPSEEK_API_KEY 或 LLM 失败，自动降级）",
        }
