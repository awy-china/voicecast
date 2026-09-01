"""VoiceCast Web 界面（Gradio）：
Tab1 音色设计器（描述→候选试听→滑杆微调）
Tab2 角色表管理（查看/改音色/保存）
Tab3 批量配音（剧本→分句音频+manifest）
"""

from __future__ import annotations

from pathlib import Path

import gradio as gr

from ..core.io import load_recipe_library, save_yaml
from ..core.models import Cast, Project
from ..design.candidate_gen import generate_candidates
from ..design.sliders import apply_sliders
from ..engines.registry import EngineRegistry
from ..pipeline.parser import parse_file
from ..pipeline.scheduler import load_cast, run_batch

MAX_CANDIDATES = 5

# ---------------- Tab1 设计器 ----------------

_last_design: dict = {}  # 最近一次候选结果（滑杆微调用）


def _refresh_choices(_msg: str):
    """候选下拉框跟随最近一次生成结果刷新（结果存全局，不依赖 UI 返回值）。"""
    cands = _last_design.get("candidates", [])
    return gr.update(choices=[c["profile"].id for c in cands])


def _design_go(description: str, top_k: int, progress=gr.Progress()):
    global _last_design
    if not description.strip():
        return [None] * MAX_CANDIDATES * 2 + ["请输入角色声音描述"]
    progress(0.05, desc="翻译配方…")

    def _cb(frac: float, msg: str) -> None:
        progress(frac, desc=f"🎧 {msg}（本地引擎首次加载模型约需 1 分钟）")

    r = generate_candidates(description, top_k=int(top_k), on_progress=_cb)
    _last_design = r
    progress(1.0, desc="完成")
    outs: list = []
    for i in range(MAX_CANDIDATES):
        if i < len(r["candidates"]):
            c = r["candidates"][i]
            outs.append(c["audio"])
            outs.append(
                f"**{c['profile'].id}** · {c['engine_explain']} · {c['reason']}\n\n"
                f"参数: pitch={c['params'].get('pitch', 0)} speed={c['params'].get('speed', 1.0)}"
            )
        else:
            outs += [None, ""]
    msg = f"翻译来源: {r['source']} — {r['summary']}"
    for e in r.get("errors", []):
        msg += f"\n⚠️ 跳过: {e}"
    return [*outs, msg]


def _slider_go(choice: str, age: float, darkness: float, brightness: float, speed: float):
    cands = _last_design.get("candidates", [])
    if not cands:
        return None, "请先生成候选"
    pick = next((c for c in cands if c["profile"].id == choice), cands[0])
    profile = apply_sliders(
        pick["profile"], age_years=age, darkness=darkness,
        brightness=brightness, speed=speed,
    )
    out_dir = Path(_last_design["out_dir"]) / "tuned"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{profile.id}_tuned.wav"
    try:
        engine = EngineRegistry().route(profile)
        engine.synthesize("微调后的声音，你听听看。", profile, path)
        return str(path), (
            f"基于 {profile.id} 微调 → pitch={profile.params.get('pitch')} "
            f"speed={profile.params.get('speed')}（{engine.name}）"
        )
    except Exception as e:
        return None, f"微调生成失败: {e}"


def design_tab() -> gr.Blocks:
    with gr.Blocks() as tab:
        gr.Markdown("## 🎙️ 音色设计器 —— 描述你想要的声音，出候选试听")
        with gr.Row():
            desc = gr.Textbox(label="角色声音描述", placeholder="如：反派中年男声，低沉阴险", scale=3)
            top_k = gr.Slider(1, MAX_CANDIDATES, value=3, step=1, label="候选数量", scale=1)
        gen_btn = gr.Button("🎧 生成候选", variant="primary")
        status = gr.Markdown("")

        audios: list[gr.Audio] = []
        reasons: list[gr.Markdown] = []
        for i in range(MAX_CANDIDATES):
            with gr.Row():
                audios.append(gr.Audio(label=f"候选 {i + 1}", type="filepath", scale=1))
                reasons.append(gr.Markdown(f"候选 {i + 1} 说明", scale=2))

        gr.Markdown("---\n### 🎛️ 滑杆微调（基于选中候选）")
        with gr.Row():
            choice = gr.Dropdown(label="选择候选", choices=[], scale=2)
            age = gr.Slider(10, 80, value=25, label="年龄")
            darkness = gr.Slider(-1, 1, value=0, step=0.05, label="低沉↔明亮")
            brightness = gr.Slider(-1, 1, value=0, step=0.05, label="亮度")
            speed = gr.Slider(0.5, 1.5, value=1.0, step=0.05, label="语速")
        tune_btn = gr.Button("🔧 微调试听")
        tuned_audio = gr.Audio(label="微调结果", type="filepath")
        tuned_info = gr.Markdown("")

        gen_btn.click(_design_go, [desc, top_k], [*audios, *reasons, status]).then(
            _refresh_choices, [status], [choice],
        )
        tune_btn.click(_slider_go, [choice, age, darkness, brightness, speed],
                       [tuned_audio, tuned_info])
    return tab


# ---------------- Tab2 角色表 ----------------

def _cast_view(path: str):
    try:
        c = load_cast(path)
        rows = [[r.id, r.name, r.voice, r.default_emotion, r.note] for r in c.cast.values()]
        return rows, f"共 {len(rows)} 个角色"
    except Exception as e:
        return [], f"加载失败: {e}"


def _cast_save(path: str, df):
    try:
        c = load_cast(path)
        lib = load_recipe_library()
        changed = []
        for row in df:
            rid, _name, voice, emotion, note = row[:5]
            role = c.cast.get(rid)
            if role is None:
                continue
            if voice != role.voice:
                if voice not in lib:
                    return f"配方不存在: {voice}"
                role.voice = voice
                changed.append(f"{rid} → {voice}")
            if emotion:
                role.default_emotion = emotion
            if note is not None:
                role.note = str(note)
        save_yaml(c.model_dump(exclude_none=True), path)
        return "已保存: " + "; ".join(changed) if changed else "无变化"
    except Exception as e:
        return f"保存失败: {e}"


def cast_tab() -> gr.Blocks:
    with gr.Blocks() as tab:
        gr.Markdown("## 🎭 角色表管理")
        path = gr.Textbox(label="cast.yaml 路径", value="examples/cast_demo.yaml")
        view_btn = gr.Button("📖 加载角色表")
        info = gr.Markdown("")
        df = gr.Dataframe(
            headers=["id", "名字", "音色配方", "默认情绪", "备注"],
            interactive=True, datatype=["str"] * 5,
        )
        save_btn = gr.Button("💾 保存修改")
        save_info = gr.Markdown("")
        view_btn.click(_cast_view, [path], [df, info])
        save_btn.click(_cast_save, [path, df], [save_info])
    return tab


# ---------------- Tab3 批量配音 ----------------

def _batch_run(script_path: str, cast_path: str, out_dir: str, budget: float, dry: bool,
               progress=gr.Progress()):
    from ..compliance.sensitive_words import check_text

    progress(0.05, desc="解析剧本与角色表…")
    try:
        s = parse_file(script_path)
        c = load_cast(cast_path)
        project = Project(name=s.title, script_path=script_path, cast_path=cast_path,
                          output_dir=Path(out_dir), budget_per_episode=budget)
        total = max(len(s.lines), 1)
        done = 0

        def on_line(rec: dict) -> None:
            nonlocal done
            done += 1
            st = rec["status"]
            icon = {"ok": "✅", "error": "❌", "blocked": "🚫", "budget_skipped": "⏭"}.get(st, "•")
            err = f" {rec.get('error', '')}" if rec.get("error") else ""
            progress(done / total, desc=f"[{done}/{total}] {icon} {rec['role']} · {rec.get('engine', '—')}{err}")

        r = run_batch(project, s, c, dry_run=dry, compliance_check=check_text, on_line=on_line)
        progress(1.0, desc="✅ 完成")
        rows = [
            [rec.get("line_no"), rec.get("episode"), rec.get("role"), rec.get("status"),
             rec.get("engine", ""), rec.get("file", ""), rec.get("error", "")]
            for rec in r["records"]
        ]
        summary = (
            f"成功 {r['ok']} / 失败 {r['error']} / 拦截 {r.get('blocked', 0)} / "
            f"预算跳过 {r['budget_skipped']} / 总成本 {r['total_cost']} 元\n"
            f"manifest: {r['manifest']}"
        )
        return rows, summary
    except Exception as e:
        progress(1.0, desc="失败")
        return [], f"运行失败: {e}"


def batch_tab() -> gr.Blocks:
    with gr.Blocks() as tab:
        gr.Markdown("## 🎬 批量配音（剧本 → 分句音频 + manifest）")
        with gr.Row():
            script_path = gr.Textbox(label="剧本文件", value="examples/script_demo.txt", scale=2)
            cast_path = gr.Textbox(label="角色表", value="examples/cast_demo.yaml", scale=2)
            out_dir = gr.Textbox(label="输出目录", value="outputs/web_demo", scale=1)
        with gr.Row():
            budget = gr.Number(label="每集预算(元)，0=不限", value=0)
            dry = gr.Checkbox(label="仅规划(dry-run)", value=False)
        run_btn = gr.Button("🚀 开始配音", variant="primary")
        summary = gr.Markdown("")
        result = gr.Dataframe(
            headers=["句号", "集", "角色", "状态", "引擎", "文件", "错误"],
            interactive=False,
        )
        run_btn.click(_batch_run, [script_path, cast_path, out_dir, budget, dry],
                      [result, summary])
    return tab


# ---------------- 入口 ----------------

def build_app() -> gr.Blocks:
    with gr.Blocks(title="VoiceCast 声演工作室") as demo:
        gr.Markdown("# 🎙️ VoiceCast 声演工作室\n本地优先、零供应商依赖的 AI 配音工作台")
        gr.TabbedInterface(
            [design_tab(), cast_tab(), batch_tab()],
            ["音色设计器", "角色表", "批量配音"],
        )
    # 必须开 queue：gr.Progress 进度条靠 queue 的事件流推送，不开则进度静默丢失
    demo.queue(default_concurrency_limit=1)
    return demo


if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    app = build_app()
    app.launch(server_name="127.0.0.1", server_port=7860, inbrowser=False)
