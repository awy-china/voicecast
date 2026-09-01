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
from ..design.sliders import apply_sliders
from ..engines.registry import EngineRegistry
from ..pipeline.parser import parse_file
from ..pipeline.scheduler import load_cast, run_batch

# ---------------- Tab1 设计器 ----------------

_last_design: dict = {}  # 最近一次生成结果（滑杆微调用）


def _design_go(description: str):
    """描述 → 直接生成 1 个最匹配的音色（用户指令：去掉多候选）。"""
    global _last_design
    from ..design.candidate_gen import generate_voice

    if not description.strip():
        return None, "请输入角色声音描述"
    r = generate_voice(description)
    if not r.get("ok"):
        return None, f"❌ 生成失败: {r.get('error', '未知错误')}"
    _last_design = r
    msg = (
        f"✅ 生成成功（翻译来源: {r['source']}）\n\n"
        f"**{r['profile'].id}** · {r['engine_explain']} · {r['reason']}\n\n"
        f"参数: pitch={r['params'].get('pitch', 0)} speed={r['params'].get('speed', 1.0)}"
    )
    return r["audio"], msg


def _slider_go(age: float, darkness: float, brightness: float, speed: float):
    profile = _last_design.get("profile")
    if profile is None:
        return None, "请先生成声音"
    new_profile = apply_sliders(
        profile, age_years=age, darkness=darkness,
        brightness=brightness, speed=speed,
    )
    out_dir = Path(_last_design["audio"]).parent / "tuned"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{profile.id}_tuned.wav"
    try:
        engine = EngineRegistry().route(new_profile)
        engine.synthesize("微调后的声音，你听听看。", new_profile, path)
        return str(path), (
            f"基于 {profile.id} 微调 → pitch={new_profile.params.get('pitch')} "
            f"speed={new_profile.params.get('speed')}（{engine.name}）"
        )
    except Exception as e:  # noqa: BLE001
        return None, f"微调生成失败: {e}"


def design_tab() -> gr.Blocks:
    with gr.Blocks() as tab:
        gr.Markdown("## 🎙️ 音色设计器 —— 描述你想要的声音，直接生成试听")
        desc = gr.Textbox(label="角色声音描述", placeholder="如：反派中年男声，低沉阴险", lines=2)
        gen_btn = gr.Button("🎧 生成声音", variant="primary")
        with gr.Row():
            audio = gr.Audio(label="生成结果", type="filepath", scale=1)
            info = gr.Markdown("", scale=2)

        gr.Markdown("---\n### 🎛️ 滑杆微调（基于生成结果）")
        with gr.Row():
            age = gr.Slider(10, 80, value=25, label="年龄")
            darkness = gr.Slider(-1, 1, value=0, step=0.05, label="低沉↔明亮")
            brightness = gr.Slider(-1, 1, value=0, step=0.05, label="亮度")
            speed = gr.Slider(0.5, 1.5, value=1.0, step=0.05, label="语速")
        tune_btn = gr.Button("🔧 微调试听")
        tuned_audio = gr.Audio(label="微调结果", type="filepath")
        tuned_info = gr.Markdown("")

        gen_btn.click(_design_go, [desc], [audio, info])
        tune_btn.click(_slider_go, [age, darkness, brightness, speed],
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

def _batch_run_stream(script_path: str, cast_path: str, out_dir: str, budget: float,
                      dry: bool, progress=gr.Progress()):
    """流式批量配音：每句完成即 yield 日志，前端实时滚动（不依赖进度条）。"""
    import threading
    import time

    from ..compliance.sensitive_words import check_text

    yield "", "⏳ 解析剧本与角色表…", []
    s = parse_file(script_path)
    c = load_cast(cast_path)
    project = Project(name=s.title, script_path=script_path, cast_path=cast_path,
                      output_dir=Path(out_dir), budget_per_episode=budget)
    total = max(len(s.lines), 1)
    log: list[str] = []
    box: dict = {}

    def worker() -> None:
        def on_line(rec: dict) -> None:
            st = rec["status"]
            icon = {"ok": "✅", "error": "❌", "blocked": "🚫", "budget_skipped": "⏭"}.get(st, "•")
            err = f" {rec.get('error', '')}" if rec.get("error") else ""
            log.append(
                f"[{len(log) + 1:>3}/{total}] {icon} {rec['role']} · "
                f"{rec.get('engine', '—')}{err}"
            )

        try:
            box["result"] = run_batch(project, s, c, dry_run=dry,
                                      compliance_check=check_text, on_line=on_line)
        except Exception as e:  # noqa: BLE001
            box["error"] = str(e)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    while t.is_alive():
        yield "\n".join(log[-20:]), "⏳ 配音运行中…", []
        time.sleep(0.25)
    t.join()

    if "error" in box:
        yield "\n".join(log[-20:]), f"❌ 运行失败: {box['error']}", []
        return
    r = box["result"]
    summary = (
        f"✅ 成功 {r['ok']} / 失败 {r['error']} / 拦截 {r.get('blocked', 0)} / "
        f"预算跳过 {r['budget_skipped']} / 总成本 {r['total_cost']} 元\n"
        f"📄 manifest: {r['manifest']}"
    )
    rows = [
        [rec.get("line_no"), rec.get("episode"), rec.get("role"), rec.get("status"),
         rec.get("engine", ""), rec.get("file", ""), rec.get("error", "")]
        for rec in r["records"]
    ]
    yield "\n".join(log[-30:]), summary, rows


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
        log_box = gr.Textbox(label="📊 实时状态（每句完成后滚动更新）", lines=18,
                             interactive=False, placeholder="点击开始配音后，这里会逐句显示进度…")
        summary = gr.Markdown("")
        result = gr.Dataframe(
            headers=["句号", "集", "角色", "状态", "引擎", "文件", "错误"],
            interactive=False,
        )
        run_btn.click(_batch_run_stream,
                      [script_path, cast_path, out_dir, budget, dry],
                      [log_box, summary, result])
    return tab


# ---------------- 入口 ----------------

def build_app() -> gr.Blocks:
    """TabbedInterface 本身就是 Blocks，绝不能再包一层 gr.Blocks——
    嵌套会导致 UI 双份渲染（用户点的按钮是未绑事件的副本，点击无效）。"""
    demo = gr.TabbedInterface(
        [design_tab(), cast_tab(), batch_tab()],
        ["音色设计器", "角色表", "批量配音"],
        title="VoiceCast 声演工作室",
    )
    # 必须开 queue：流式输出（generator yield）与 gr.Progress 都靠 queue 推送
    demo.queue(default_concurrency_limit=1)
    return demo


if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    app = build_app()
    app.launch(server_name="127.0.0.1", server_port=7860, inbrowser=False)
