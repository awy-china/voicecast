"""规则翻译器：描述 → 配方候选（关键词匹配 + 评分）。

零依赖、永远可用——这是"独立运作"的底线保障。
LLM 翻译器只是它的增强（recipe_translator.py）。
"""

from __future__ import annotations

import re

from ..core.io import load_recipe_library
from ..core.models import VoiceProfile

# 同义词表：需求词 → 配方库检索词
SYNONYMS: dict[str, list[str]] = {
    "反派": ["反派", "阴险", "狠", "毒", "算计", "坏人", "奸"],
    "老年": ["老年", "老人", "爷爷", "大爷", "沧桑", "苍老", "老"],
    "中年": ["中年", "大叔", "沉稳", "商人", "上位", "成熟"],
    "青年": ["青年", "年轻", "少年", "男主", "小伙"],
    "温柔": ["温柔", "温婉", "柔和", "暖", "知性"],
    "活泼": ["活泼", "俏皮", "灵动", "欢快"],
    "阳光": ["阳光", "清澈", "明亮", "清爽"],
    "迷茫": ["迷茫", "沉郁", "压抑", "疲惫", "丧"],
    "慈祥": ["慈祥", "和蔼", "亲切", "大妈", "奶奶"],
    "爽利": ["爽利", "利落", "干脆", "泼辣"],
    "少女": ["少女", "萝莉", "清纯", "甜美"],
    "御姐": ["御姐", "气场", "成熟女", "飒"],
    "甜美": ["甜美", "甜", "可爱"],
    "霸道": ["霸道", "总裁", "强势", "霸气"],
    "精英": ["精英", "干练", "职场", "白领"],
    "清澈": ["清澈", "干净", "清亮"],
    "低沉": ["低沉", "沙哑", "浑厚", "压"],
    "方言": ["方言", "口音", "东北", "陕西", "河南", "四川"],
    "硬朗": ["硬朗", "刚强", "中气"],
    "男": ["男", "男人", "男性"],
    "女": ["女", "女人", "女性"],
    "快": ["快", "语速快", "急促", "利落"],
    "慢": ["慢", "语速慢", "迟缓", "拖"],
}

GENDER_WORDS = {"男": ["男", "叔", "爷", "哥", "少年", "总裁"], "女": ["女", "婶", "姐", "妹", "少女", "御姐"]}


def _engine_available(profile: VoiceProfile) -> bool:
    """候选只保留当前可用引擎的配方——保证"设置几个就出几个"（根源过滤）。"""
    from ..engines.registry import EngineRegistry

    host = profile.engine.host
    if host == "auto":
        return True  # auto 走成本路由，总会落到某个可用引擎
    eng = EngineRegistry().get(host)
    return bool(eng and eng.available())


def _searchable(profile: VoiceProfile) -> str:
    return " ".join(
        [profile.id, profile.name, profile.description, *profile.tags]
    ).lower()


def match_candidates(
    description: str, top_k: int = 3, library: dict[str, VoiceProfile] | None = None
) -> list[tuple[VoiceProfile, int, list[str]]]:
    """返回 [(profile, 得分, 命中词)]，按得分降序。"""
    library = library or load_recipe_library()
    desc = description.lower()

    # 性别硬过滤（描述明确提到性别时）
    gender_hint: str | None = None
    for g, words in GENDER_WORDS.items():
        if any(w in desc for w in words):
            gender_hint = g
            break

    scored: list[tuple[VoiceProfile, int, list[str]]] = []
    for profile in library.values():
        hay = _searchable(profile)
        hits: list[str] = []
        score = 0
        for canon, words in SYNONYMS.items():
            if any(w in desc for w in words):
                # 配方侧命中才算数
                matched = [w for w in words if w in hay]
                if matched:
                    score += 2
                    hits.append(canon)
        if gender_hint and gender_hint not in profile.tags and gender_hint not in profile.name:
            continue
        if not _engine_available(profile):
            continue  # 引擎不可用（如 minimax 无 key）的配方不进候选，避免占名额
        if score > 0:
            scored.append((profile, score, hits))

    scored.sort(key=lambda x: -x[1])

    # 补足：命中不足 top_k 时，从同性别/未命中的配方里补齐，
    # 只补当前可用引擎的配方——保证"设置几个就出几个"
    if len(scored) < top_k:
        seen = {p.id for p, _s, _h in scored}
        for profile in library.values():
            if len(scored) >= top_k:
                break
            if profile.id in seen:
                continue
            if gender_hint and gender_hint not in profile.tags and gender_hint not in profile.name:
                continue
            if not _engine_available(profile):
                continue
            scored.append((profile, 1, ["补充候选（相关性较低）"]))
            seen.add(profile.id)

    return scored[:top_k]
