"""音色设计器测试：规则匹配 + 滑杆换算（不依赖网络）。"""

import os

from voicecast.design.recipe_rules import match_candidates
from voicecast.design.sliders import apply_sliders
from voicecast.design.recipe_translator import RecipeTranslator


def test_rules_find_villain():
    top = match_candidates("反派中年男声，低沉阴险", top_k=3)
    ids = [p.id for p, _s, _h in top]
    assert "minimax_villain" in ids or "minimax_male_badao" in ids


def test_rules_find_warm_female():
    top = match_candidates("温柔女声", top_k=3)
    ids = [p.id for p, _s, _h in top]
    assert "female_warm" in ids


def test_rules_find_elderly():
    top = match_candidates("六十岁的沧桑老人", top_k=3)
    ids = [p.id for p, _s, _h in top]
    assert "male_elderly" in ids


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
