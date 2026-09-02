"""音色设计器测试：规则匹配 + 滑杆换算（不依赖网络）。"""

import os

from voicecast.design.recipe_rules import _engine_available, match_candidates
from voicecast.design.sliders import apply_sliders
from voicecast.design.recipe_translator import RecipeTranslator


def test_rules_find_villain():
    import os

    top = match_candidates("反派中年男声，低沉阴险", top_k=3)
    ids = [p.id for p, _s, _h in top]
    assert ids  # 有候选
    if not os.environ.get("MINIMAX_API_KEY"):
        # 无 key 时 minimax 配方不应占名额（根源过滤：数量对版）
        assert "minimax_villain" not in ids
    assert "male_mid_business" in ids or "male_mid_calm" in ids


def test_rules_fill_to_top_k():
    """命中不足 top_k 时自动补足到 top_k（数量对版）。"""
    top = match_candidates("温柔女声", top_k=4)
    ids = [p.id for p, _s, _h in top]
    assert len(ids) == 4
    assert "female_warm" in ids


def test_rules_candidates_have_distinct_voices():
    """候选底声互不重复：一次生成的音色明显不同（多样性）。"""
    top = match_candidates("反派中年男声，低沉阴险", top_k=5)
    voices = [
        (p.params.get("base_voice") or p.params.get("ref_file") or p.id)
        for p, _s, _h in top
    ]
    assert len(voices) == len(set(voices)), f"底声重复: {voices}"
    assert len(top) == 5


def test_similar_descriptions_keep_ordering_stable_but_distinct():
    """相似描述：核心候选稳定（相关性强），但候选集合底声不重复。"""
    a = match_candidates("反派中年男声，低沉阴险", top_k=3)
    b = match_candidates("阴险的中年反派男人，低沉", top_k=3)
    ids_a = [p.id for p, _s, _h in a]
    ids_b = [p.id for p, _s, _h in b]
    # 相关性最强的候选应保持一致（同义描述本质相同）
    assert ids_a[0] == ids_b[0]
    # 每个候选集合内部底声不重复
    for ids in (ids_a, ids_b):
        profiles = [p for p, _s, _h in (a if ids is ids_a else b)]
        voices = [p.params.get("base_voice") or p.params.get("ref_file") for p in profiles]
        assert len(voices) == len(set(voices))


def test_rules_find_warm_female():
    top = match_candidates("温柔女声", top_k=3)
    ids = [p.id for p, _s, _h in top]
    assert "female_warm" in ids


def test_rules_find_elderly():
    top = match_candidates("六十岁的沧桑老人", top_k=3)
    # 真人参考加权（去金属感）：无性别描述时真人配方优先
    assert any("真人参考" in p.tags for p, _s, _h in top)
    # 老年特征仍被匹配
    assert any("老年" in p.tags for p, _s, _h in top)
    # 所有候选引擎可用
    for p, _s, _h in top:
        assert _engine_available(p)


def test_rules_gender_filter():
    top = match_candidates("老年女人，慈祥", top_k=3)
    for p, _s, _h in top:
        assert "女" in p.name or "女" in p.tags


def test_translator_falls_back_to_rules_without_key():
    os.environ.pop("DEEPSEEK_API_KEY", None)
    t = RecipeTranslator()
    r = t.translate("温柔女声")
    assert r["source"] == "rules"
    assert len(r["candidates"]) >= 1


def test_sliders_edge_age():
    from voicecast.core.models import VoiceProfile

    p = VoiceProfile(id="male_young_sunny", engine={"host": "edge_tts"},
                     params={"base_voice": "zh-CN-YunxiNeural", "pitch": 0, "speed": 1.0})
    old = apply_sliders(p, age_years=60)
    assert old.params["pitch"] < 0          # 60 岁 → 明显降调（Hz 单位）
    assert old.params["speed"] < 1.0        # 变慢
    young = apply_sliders(p, age_years=20)
    assert young.params["pitch"] > old.params["pitch"]


def test_sliders_darkness():
    from voicecast.core.models import VoiceProfile

    p = VoiceProfile(id="x", engine={"host": "edge_tts"},
                     params={"base_voice": "zh-CN-YunxiNeural", "pitch": 0, "speed": 1.0})
    dark = apply_sliders(p, darkness=1.0)
    bright = apply_sliders(p, brightness=1.0)
    assert dark.params["pitch"] < bright.params["pitch"]
    assert dark.params["speed"] < 1.0
