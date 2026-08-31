"""核心数据模型测试。"""

import pytest
from pydantic import ValidationError

from voicecast.core.models import (
    Cast,
    DesignMethod,
    Role,
    Script,
    ScriptLine,
    VoiceProfile,
)


def test_voiceprofile_roundtrip():
    p = VoiceProfile(id="test_v1", name="测试", params={"pitch": -4, "speed": 0.85})
    p2 = VoiceProfile.model_validate(p.model_dump())
    assert p2.params["pitch"] == -4
    assert p2.design == DesignMethod.RECIPE
    assert p2.engine.prefer_local is True  # 独立性铁律默认本地优先


def test_invalid_profile_id_rejected():
    with pytest.raises(ValidationError):
        VoiceProfile(id="bad id!", name="x")


def test_cast_lookup_and_error():
    c = Cast(cast={"a": Role(id="a", name="阿", voice="v1")})
    assert c.role("a").name == "阿"
    with pytest.raises(Exception):
        c.role("nope")


def test_script_roles_dedup():
    s = Script(
        lines=[
            ScriptLine(role="a", text="x"),
            ScriptLine(role="b", text="y"),
            ScriptLine(role="a", text="z"),
        ]
    )
    assert s.roles == ["a", "b"]


def test_yaml_roundtrip(tmp_path):
    from voicecast.core.io import load_yaml, save_yaml

    p = tmp_path / "t.yaml"
    save_yaml({"cast": {"a": {"role": "阿"}}}, p)
    assert load_yaml(p)["cast"]["a"]["role"] == "阿"


def test_engine_host_default_auto():
    p = VoiceProfile(id="v1")
    assert p.engine.host == "auto"
