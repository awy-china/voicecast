"""配方库加载测试。"""

from voicecast.core.io import load_recipe_library


def test_recipe_library_loads():
    lib = load_recipe_library()
    assert len(lib) >= 15
    assert "male_elderly" in lib
    # 老年配方必须是降调（实测经验：-25Hz 以下）
    assert lib["male_elderly"].params.get("pitch", 0) <= -25


def test_recipe_has_provenance():
    lib = load_recipe_library()
    for p in lib.values():
        assert p.provenance.authorized is True, f"{p.id} 缺少授权声明（合规门禁）"
