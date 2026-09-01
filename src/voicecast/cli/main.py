"""VoiceCast CLI：设计 / 批量配音 / 角色表 / 剧本转换 / 引擎状态。"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from ..compliance import clone_gate_check, provenance_check
from ..core.models import Project, VoicecastError
from ..design.blender import blend_recipe, save_blend
from ..design.candidate_gen import generate_voice
from ..design.seed import generate_seed_library
from ..engines.registry import EngineRegistry
from ..pipeline.parser import parse_file, save_json_script, to_txt
from ..pipeline.scheduler import load_cast, run_batch
from ..pipeline.router import route_engine

app = typer.Typer(
    help="VoiceCast — 以角色为中心的 AI 配音工作台（本地优先、零供应商依赖）",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()


@app.command("engines")
def engines_cmd() -> None:
    """列出所有引擎与可用状态。"""
    reg = EngineRegistry()
    table = Table(title="引擎状态")
    table.add_column("引擎")
    table.add_column("状态")
    table.add_column("说明")
    for e in reg.all():
        ok = e.available()
        table.add_row(e.name, "[green]✅ 可用[/green]" if ok else "[red]⛔ 不可用[/red]", e.explain())
    console.print(table)


@app.command("design")
def design_cmd(
    description: str = typer.Argument(..., help="角色声音描述，如：反派中年男声，低沉阴险"),
    out_dir: Path | None = typer.Option(None, "--out-dir", help="输出目录"),
) -> None:
    """音色设计器：描述 → 直接生成 1 个最匹配的音色（试听）。"""
    from rich.status import Status

    with console.status("🎧 正在生成声音…", spinner="dots") as status:
        status.update("🎧 正在生成声音…（本地引擎首次加载模型约需 1 分钟）")
        r = generate_voice(description, out_dir=out_dir)
    if not r.get("ok"):
        console.print(f"[red]❌ 生成失败:[/red] {r.get('error', '未知错误')}")
        return
    console.print(f"[bold]翻译来源:[/bold] {r['source']} — {r['summary']}")
    console.print(
        f"  [green]✅[/green] [bold]{r['profile'].id}[/bold] "
        f"({r['engine']}) {r['reason']}\n"
        f"        [dim]{r['audio']}[/dim]"
    )


@app.command("blend")
def blend_cmd(
    main: str = typer.Argument(..., help="主参考配方 id（提供韵律骨架），如 aishell3_SSB0016"),
    aux: list[str] = typer.Argument(..., help="辅助参考配方 id（渗入音色特征），可多个"),
    save: bool = typer.Option(False, "--save", help="试听后保存为融合配方"),
    probe: str = typer.Option("这就是我的声音。你看，像不像你心里想的那个角色？", "--probe", help="探测句"),
) -> None:
    """音色混合器：主参考 × 辅助参考 → 融合出独特新音色（GPT-SoVITS 多说话人融合）。"""
    from rich.status import Status

    with console.status(f"🎧 融合中：{main} × {' + '.join(aux)}…（首次推理约 1 分钟）", spinner="dots"):
        r = blend_recipe(main, aux, probe_text=probe)
    if not r.get("ok"):
        console.print(f"[red]❌ 融合失败:[/red] {r.get('error', '未知错误')}")
        return
    console.print(f"[green]✅ 融合音色已生成:[/green] {r['audio']}")
    console.print(f"  配方: [bold]{r['profile'].id}[/bold]（{r['profile'].name}）")
    console.print(f"  标签: {r['profile'].tags}")
    if save:
        path = save_blend(r["profile"])
        console.print(f"[green]✅ 已保存:[/green] {path}（规则引擎/批量配音可用）")


@app.command("run")
def run_cmd(
    script: Path = typer.Argument(..., help="剧本文件（txt 标记式或 JSON）"),
    cast: Path = typer.Argument(..., help="角色表 YAML"),
    out_dir: Path = typer.Option(Path("outputs"), "--out-dir", help="输出目录"),
    budget: float = typer.Option(0.0, "--budget", help="每集预算上限（元），0=不限"),
    dry_run: bool = typer.Option(False, "--dry-run", help="只规划不生成"),
) -> None:
    """批量配音：剧本 → 分句音频 + manifest（成本/溯源）。实时进度面板。"""
    from rich.live import Live
    from rich.panel import Panel

    from ..compliance.sensitive_words import check_text

    s = parse_file(script)
    c = load_cast(cast)
    project = Project(
        name=s.title, script_path=str(script), cast_path=str(cast),
        output_dir=out_dir, budget_per_episode=budget,
    )
    total = len(s.lines)
    if total == 0:
        console.print("[yellow]剧本为空[/yellow]")
        raise typer.Exit(1)

    if dry_run:
        result = run_batch(project, s, c, dry_run=True, compliance_check=check_text)
    else:
        stats = {"ok": 0, "error": 0, "blocked": 0, "budget_skipped": 0}
        icons = {"ok": "✅ 成功", "error": "❌ 失败", "blocked": "🚫 违规拦截",
                 "budget_skipped": "⏭ 超预算"}

        def _panel(cur_line: dict, done: int) -> Panel:
            icon = icons.get(cur_line["status"], cur_line["status"])
            err = f" [red]· {cur_line.get('error', '')}[/red]" if cur_line.get("error") else ""
            body = (
                f"[bold cyan][{done}/{total}][/bold cyan] "
                f"{cur_line['role']} · {cur_line.get('engine', '—')} · {icon}{err}\n"
                f"[dim]成功 {stats['ok']} · 失败 {stats['error']} · "
                f"拦截 {stats['blocked']} · 超预算 {stats['budget_skipped']}[/dim]"
            )
            return Panel(body, title=f"🎬 配音进度：{project.name}", border_style="cyan")

        with Live(console=console, refresh_per_second=6) as live:
            def on_line(rec: dict) -> None:
                stats[rec["status"]] = stats.get(rec["status"], 0) + 1
                live.update(_panel(rec, sum(stats.values())))

            result = run_batch(project, s, c, compliance_check=check_text, on_line=on_line)
        console.print(f"[green]✅ 完成：成功 {result['ok']} / 失败 {result['error']} / "
                      f"拦截 {result.get('blocked', 0)} / 超预算 {result['budget_skipped']} / "
                      f"总成本 {result['total_cost']} 元[/green]")

    table = Table(title=f"配音结果：{project.name}")
    table.add_column("状态")
    table.add_column("数量")
    for key, label in [("ok", "[green]成功[/green]"), ("error", "[red]失败[/red]"),
                       ("blocked", "[yellow]违规拦截[/yellow]"),
                       ("planned", "[cyan]已规划[/cyan]"),
                       ("budget_skipped", "[yellow]超预算跳过[/yellow]")]:
        if result.get(key):
            table.add_row(label, str(result[key]))
    table.add_row("总成本", f"{result['total_cost']:.4f} 元")
    console.print(table)
    if result.get("manifest"):
        console.print(f"[green]manifest: {result['manifest']}[/green]")
    if result.get("error"):
        console.print("[yellow]失败明细见 manifest.csv 的 error 列[/yellow]")


@app.command("cast")
def cast_cmd(cast: Path = typer.Argument(..., help="角色表 YAML")) -> None:
    """查看角色表 + 合规体检。"""
    c = load_cast(cast)
    table = Table(title=f"角色表：{c.title or cast.name}")
    table.add_column("id")
    table.add_column("名字")
    table.add_column("音色配方")
    table.add_column("默认情绪")
    table.add_column("合规")
    for role in c.cast.values():
        issues = provenance_check(role_id_to_profile(role.voice))
        mark = "[green]✅[/green]" if not issues else f"[red]⚠️ {'; '.join(issues)}[/red]"
        table.add_row(role.id, role.name, role.voice, role.default_emotion, mark)
    console.print(table)


def role_id_to_profile(voice_id: str):
    from ..core.io import load_recipe_library
    lib = load_recipe_library()
    return lib[voice_id]


@app.command("script")
def script_cmd(
    path: Path = typer.Argument(..., help="剧本文件"),
    to_json: Path | None = typer.Option(None, "--to-json", help="转换为 JSON 内部标准"),
) -> None:
    """解析/转换剧本（txt ↔ JSON 双向）。"""
    s = parse_file(path)
    if to_json:
        save_json_script(s, to_json)
        console.print(f"[green]{path} → {to_json}（{len(s.lines)} 句）[/green]")
    else:
        console.print(to_txt(s))


@app.command("seed")
def seed_cmd() -> None:
    """重新生成种子音色库（recipes/samples/seed/）。"""
    paths = generate_seed_library()
    console.print(f"[green]种子音色库完成：{len(paths)} 个[/green]")
    for p in paths:
        console.print(f"  [dim]{p}[/dim]")


@app.command("verify")
def verify_cmd(files: list[Path] = typer.Argument(..., help="wav/mp3 文件")) -> None:
    """校验音频文件（时长/静音/削波）。"""
    from ..engines.util import verify_audio

    for f in files:
        try:
            v = verify_audio(f)
            mark = "[green]✅[/green]" if v["ok"] else f"[red]⚠️ {v['reason']}[/red]"
            console.print(
                f"{mark} {f.name}  {v['duration']:.1f}s  "
                f"mean={v['mean_volume']:.0f}dB max={v['max_volume']:.0f}dB"
            )
        except Exception as e:
            console.print(f"[red]✗ {f.name} 无法校验: {e}[/red]")


@app.command("route")
def route_cmd(
    voice: str = typer.Argument(..., help="配方 id（如 male_elderly）"),
) -> None:
    """查看某配方的路由结果（哪个引擎、是否过质量门槛）。"""
    from ..core.io import load_recipe_library
    from ..core.models import Project

    lib = load_recipe_library()
    profile = lib.get(voice)
    if profile is None:
        console.print(f"[red]配方不存在: {voice}[/red]")
        raise typer.Exit(1)
    issues = clone_gate_check(profile)
    try:
        eng = route_engine(profile, Project(name="probe", script_path="", cast_path=""))
        console.print(f"[bold]{profile.id}[/bold] → [green]{eng.name}[/green]（{eng.explain()}）")
    except VoicecastError as e:
        console.print(f"[red]{profile.id} → {e}[/red]")
    if issues:
        console.print(f"[yellow]合规: {'; '.join(issues)}[/yellow]")


if __name__ == "__main__":
    app()
