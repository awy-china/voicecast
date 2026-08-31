"""合规门禁测试。"""

import os

from voicecast.compliance.clone_gate import CLONE_DECLARATION, clone_gate_check
from voicecast.compliance.provenance import provenance_check
from voicecast.compliance.sensitive_words import check_text
from voicecast.core.models import DesignMethod, VoiceProfile


def test_sensitive_words_builtin():
    assert check_text("这是一句正常的台词") == []
    hits = check_text("教你炸弹制作的方法")
    assert hits == ["炸弹制作"]


def test_sensitive_words_custom_file(tmp_path):
    f = tmp_path / "custom.txt"
    f.write_text("量子速读\n", encoding="utf-8")
    os.environ["VOICECAST_SENSITIVE_FILE"] = str(f)
    from voicecast.compliance import sensitive_words
    sensitive_words._custom = None  # 强制重载
    try:
        assert check_text("量子速读了解一下") == ["量子速读"]
    finally:
        del os.environ["VOICECAST_SENSITIVE_FILE"]
        sensitive_words._custom = None


def test_clone_gate_rejects_unauthorized():
    p = VoiceProfile(
        id="bad_clone", design=DesignMethod.CLONE,
        provenance={"origin": "clone", "authorized": False},
    )
    assert clone_gate_check(p)  # 有违规项


def test_clone_gate_passes_authorized():
    p = VoiceProfile(
        id="good_clone", design=DesignMethod.CLONE,
        provenance={"origin": "clone", "authorized": True,
                    "ref_file": "refs/me.wav", "note": "自有录音"},
    )
    assert clone_gate_check(p) == []


def test_provenance_missing_ref():
    p = VoiceProfile(id="x", design=DesignMethod.CLONE,
                     provenance={"authorized": True})
    issues = provenance_check(p)
    assert any("ref_file" in i for i in issues)


def test_declaration_mentions_prohibition():
    assert "禁止克隆名人" in CLONE_DECLARATION
