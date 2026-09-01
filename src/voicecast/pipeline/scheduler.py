"""批量调度：逐句 → 路由 → 生成 → 校验 → 记账 → 重试 → 归档。

- 重试：每句最多 RETRIES 次退避重试
- 预算：按集累计成本，超过 project.budget_per_episode 则后续台词标 budget_skipped
- 输出：output_dir/E##/<E##_S##_角色_###.wav> + manifest.json/csv（含溯源/成本）
"""

from __future__ import annotations

import time
from pathlib import Path

from ..core.io import load_recipe_library, load_yaml
from ..core.models import Cast, Project, Role, Script, VoiceProfile, VoicecastError
from ..engines.registry import Engine, EngineRegistry
from .archiver import line_filename, write_manifest
from .router import estimate_cost, route_engine

RETRIES = 2
RETRY_DELAY = 2.0


def load_cast(path: Path | str) -> Cast:
    return Cast.model_validate(load_yaml(path))


def resolve_role_profile(cast: Cast, role_name: str) -> tuple[Role, VoiceProfile]:
    """角色名/id → (Role, 应用角色级微调后的 VoiceProfile)。"""
    role: Role | None = None
    for r in cast.cast.values():
        if r.name == role_name or r.id == role_name:
            role = r
            break
    if role is None:
        raise VoicecastError(f"角色表里没有「{role_name}」")
    lib = load_recipe_library()
    profile = lib.get(role.voice)
    if profile is None:
        raise VoicecastError(f"角色 {role_name} 引用的配方不存在: {role.voice}")
    if role.pitch_offset or role.speed_scale != 1.0:
        profile = profile.model_copy(deep=True)
        profile.params["pitch"] = float(profile.params.get("pitch", 0)) + role.pitch_offset
        profile.params["speed"] = float(profile.params.get("speed", 1.0)) * role.speed_scale
    return role, profile


def run_batch(
    project: Project,
    script: Script,
    cast: Cast,
    dry_run: bool = False,
    registry: EngineRegistry | None = None,
    compliance_check=None,
    on_line=None,
) -> dict:
    """compliance_check: Callable[[str], list[str]] | None —— 返回违规词列表则拦截。
    on_line: Callable[[dict], None] | None —— 每句处理完回调该句记录（进度可见性）。"""
    registry = registry or EngineRegistry()
    out_root = project.output_dir
    out_root.mkdir(parents=True, exist_ok=True)

    records: list[dict] = []
    ep_cost: dict[int, float] = {}
    ok_count = error_count = planned_count = budget_skipped = blocked_count = 0

    def _emit(rec: dict) -> None:
        records.append(rec)
        if on_line:
            on_line(rec)

    for ln in script.lines:
        if compliance_check:
            hits = compliance_check(ln.text)
            if hits:
                blocked_count += 1
                _emit({
                    "line_no": ln.line_no, "episode": ln.episode, "scene": ln.scene,
                    "role": ln.role, "text": ln.text, "emotion": ln.emotion,
                    "status": "blocked", "error": f"违规词: {'、'.join(hits)}",
                })
                continue
        budget = project.budget_per_episode
        over_budget = budget > 0 and ep_cost.get(ln.episode, 0) >= budget
        if over_budget:
            budget_skipped += 1
            _emit({
                "line_no": ln.line_no, "episode": ln.episode, "scene": ln.scene,
                "role": ln.role, "text": ln.text, "emotion": ln.emotion,
                "status": "budget_skipped", "error": f"第{ln.episode}集预算已超(上限{budget}元)",
            })
            continue

        try:
            role, profile = resolve_role_profile(cast, ln.role)
            engine = route_engine(profile, project, registry)
        except VoicecastError as e:
            error_count += 1
            _emit({
                "line_no": ln.line_no, "episode": ln.episode, "scene": ln.scene,
                "role": ln.role, "text": ln.text, "emotion": ln.emotion,
                "status": "error", "error": str(e),
            })
            continue

        filename = line_filename(ln.episode, ln.scene, role.id, ln.line_no)
        rel_path = f"E{ln.episode:02d}/{filename}"
        out_path = out_root / rel_path

        if dry_run:
            planned_count += 1
            _emit({
                "line_no": ln.line_no, "episode": ln.episode, "scene": ln.scene,
                "role": ln.role, "text": ln.text, "emotion": ln.emotion,
                "status": "planned", "engine": engine.name, "file": rel_path,
                "cost_est": round(estimate_cost(ln.text, engine), 4),
            })
            continue

        last_err = ""
        for attempt in range(RETRIES + 1):
            try:
                engine.synthesize(ln.text, profile, out_path, emotion=ln.emotion)
                break
            except Exception as e:  # noqa: BLE001  引擎异常统一转记录，不中断整批
                last_err = str(e)
                if attempt < RETRIES:
                    time.sleep(RETRY_DELAY * (attempt + 1))

        if last_err:
            error_count += 1
            _emit({
                "line_no": ln.line_no, "episode": ln.episode, "scene": ln.scene,
                "role": ln.role, "text": ln.text, "emotion": ln.emotion,
                "status": "error", "engine": engine.name, "error": last_err,
            })
        else:
            ok_count += 1
            cost = estimate_cost(ln.text, engine)
            ep_cost[ln.episode] = ep_cost.get(ln.episode, 0) + cost
            _emit({
                "line_no": ln.line_no, "episode": ln.episode, "scene": ln.scene,
                "role": ln.role, "text": ln.text, "emotion": ln.emotion,
                "status": "ok", "engine": engine.name, "file": rel_path,
                "cost": round(cost, 4), "voice_profile": profile.id,
            })

    manifest = write_manifest(records, out_root) if not dry_run else None
    total_cost = round(sum(r.get("cost", 0) or 0 for r in records), 4)
    return {
        "records": records,
        "manifest": str(manifest) if manifest else None,
        "total_cost": total_cost,
        "ok": ok_count, "error": error_count,
        "planned": planned_count, "budget_skipped": budget_skipped,
        "blocked": blocked_count,
        "output_dir": str(out_root),
    }
