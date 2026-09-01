"""音色混合器：多说话人音色融合 → 独特新声音（GPT-SoVITS aux 融合）。

原理：GPT-SoVITS 的 aux_ref_audio_paths 在语义 token 层做多说话人音色融合——
主参考提供韵律与内容骨架，辅助参考渗入音色特征，生成"一个人"的融合音色
（区别于物理混音的双声重叠）。

流程：选主参考 + 1~2 个辅助参考 → 融合试听（合成探测句）→ 满意则保存为
融合配方（ref_voices_blend.yaml），之后规则引擎可按合并标签匹配、批量可用。
"""

from __future__ import annotations

from pathlib import Path

import yaml

from ..core.io import load_recipe_library, save_yaml
from ..core.models import VoiceProfile
from ..core.settings import RECIPES_DIR
from ..engines.registry import EngineRegistry

PROBE_TEXT = "这就是我的声音。你看，像不像你心里想的那个角色？"

BLEND_RECIPE = RECIPES_DIR / "ref_voices_blend.yaml"

FALLBACK_REF = "samples/ref/aishell3_SSB0016_ref.wav"


def _resolve_ref(profile: VoiceProfile) -> str:
    """配方的参考音频路径（相对 recipes/ 解析为可传给引擎的绝对路径）。"""
    ref = profile.params.get("ref_audio_path") or profile.params.get("ref_file")
    if not ref:
        raise ValueError(f"配方无参考音频: {profile.id}")
    p = Path(ref)
    return str(p if p.is_absolute() else RECIPES_DIR / p)


def blend_recipe(
    main_id: str,
    aux_ids: list[str],
    out_dir: Path | None = None,
    probe_text: str = PROBE_TEXT,
) -> dict:
    """主参考 + 辅助参考 → 融合试听音频 + 配方参数。

    返回 {ok, profile(融合配方), audio, engine, error?}。
    """
    lib = load_recipe_library()
    for rid in [main_id, *aux_ids]:
        if rid not in lib:
            return {"ok": False, "error": f"配方不存在: {rid}"}

    main = lib[main_id]
    aux_refs = [_resolve_ref(lib[a]) for a in aux_ids]

    # 融合配方：主参考 + 辅助参考；标签合并（独特性来源）
    tags: list[str] = []
    for rid in [main_id, *aux_ids]:
        for t in lib[rid].tags:
            if t not in tags and t != "真人参考":
                tags.append(t)
    tags.append("融合")

    blend = VoiceProfile(
        id=f"blend_{main_id}_{'_'.join(aux_ids)}",
        name=f"融合·{main.name}×{'+'.join(lib[a].name for a in aux_ids)}",
        engine={"host": "gpt_sovits", "fallback": ["local"]},
        params={
            "ref_audio_path": _resolve_ref(main),
            "aux_ref_audio_paths": aux_refs,
            "speed": float(main.params.get("speed", 1.0)),
            "pitch": float(main.params.get("pitch", 0)),
        },
        tags=tags,
        note="音色混合器生成（GPT-SoVITS 多说话人融合）",
    )

    out_dir = out_dir or (RECIPES_DIR.parent / "outputs" / "blend" / blend.id)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{blend.id}.wav"
    try:
        engine = EngineRegistry().route(blend)
        engine.synthesize(probe_text, blend, path)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "profile": blend, "error": str(e)}

    return {"ok": True, "profile": blend, "audio": str(path), "engine": engine.name}


def _to_rel(p: str) -> str:
    """绝对参考路径转相对 recipes/（配方可移植，换机器不失效）。"""
    try:
        return str(Path(p).resolve().relative_to(RECIPES_DIR.resolve()))
    except ValueError:
        return p


def save_blend(profile: VoiceProfile) -> Path:
    """保存融合配方到 ref_voices_blend.yaml（可被规则引擎匹配、批量使用）。"""
    params = profile.model_dump(mode="json")  # mode=json：枚举→字符串，可 yaml 序列化
    if params.get("params", {}).get("ref_audio_path"):
        params["params"]["ref_audio_path"] = _to_rel(params["params"]["ref_audio_path"])
    if params.get("params", {}).get("aux_ref_audio_paths"):
        params["params"]["aux_ref_audio_paths"] = [
            _to_rel(a) for a in params["params"]["aux_ref_audio_paths"]
        ]
    raw: dict = {}
    if BLEND_RECIPE.exists():
        raw = yaml.safe_load(BLEND_RECIPE.read_text(encoding="utf-8")) or {}
    profiles = raw.get("profiles", [])
    profiles = [p for p in profiles if p.get("id") != params["id"]]
    profiles.append(params)
    save_yaml({"profiles": profiles}, BLEND_RECIPE)
    return BLEND_RECIPE
