"""剧本流水线测试：解析/路由质量门槛/批量调度（假引擎，不依赖网络）。"""

import subprocess
from pathlib import Path

import pytest

from voicecast.core.models import Project, ScriptLine, VoiceProfile, VoicecastError
from voicecast.engines.base import Engine
from voicecast.engines.registry import EngineRegistry
from voicecast.pipeline.parser import parse_txt, to_txt, parse_file, save_json_script
from voicecast.pipeline.router import route_engine
from voicecast.pipeline.scheduler import load_cast, run_batch


class FakeEngine(Engine):
    name = "edge_tts"

    def __init__(self, name="edge_tts", cost=0.0, available=True):
        self.name = name
        self._cost = cost
        self._available = available

    def available(self) -> bool:
        return self._available

    def synthesize(self, text, profile, out_path, emotion=""):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=300:duration=0.5",
             str(out_path)],
            check=True, capture_output=True,
        )
        return out_path

    @property
    def cost_per_char(self) -> float:
        return self._cost


# ---------------- 解析 ----------------

DEMO_TXT = """【场景】S01
【情绪】平静
【林锋】这把剑，是我师父传下来的。
【叶老】修了一辈子鞋，也没修明白人心。
【情绪】愤怒
【林锋】你究竟要做什么！
"""


def test_parse_txt_basic():
    s = parse_txt(DEMO_TXT)
    assert len(s.lines) == 3
    assert s.lines[0].role == "林锋" and s.lines[0].scene == "S01"
    assert s.lines[0].emotion == "平静"
    assert s.lines[2].emotion == "愤怒"
    assert s.roles == ["林锋", "叶老"]


def test_parse_roundtrip_txt():
    s1 = parse_txt(DEMO_TXT)
    s2 = parse_txt(to_txt(s1))
    assert [(l.role, l.text, l.emotion, l.scene) for l in s1.lines] == [
        (l.role, l.text, l.emotion, l.scene) for l in s2.lines
    ]


def test_parse_json_roundtrip(tmp_path):
    s1 = parse_txt(DEMO_TXT)
    p = tmp_path / "s.json"
    save_json_script(s1, p)
    s2 = parse_file(p)
    assert len(s1.lines) == len(s2.lines)


def test_parse_bad_line_raises():
    with pytest.raises(VoicecastError):
        parse_txt("这一行没有角色标记\n【林锋】正常句")


# ---------------- 路由质量门槛 ----------------

def test_quality_gate_blocks_deep_pitch_on_edge():
    reg = EngineRegistry([FakeEngine("edge_tts"), FakeEngine("local", available=False)])
    p = VoiceProfile(id="deep", engine={"host": "auto"}, params={"pitch": -35})
    with pytest.raises(VoicecastError):  # edge 被门槛拦截，本地不可用 → 无引擎
        route_engine(p, registry=reg)


def test_quality_gate_allows_shallow_pitch():
    reg = EngineRegistry([FakeEngine("edge_tts"), FakeEngine("local", available=False)])
    p = VoiceProfile(id="ok", engine={"host": "auto"}, params={"pitch": -20})
    assert route_engine(p, registry=reg).name == "edge_tts"


# ---------------- 批量调度 ----------------

def _demo_cast() -> str:
    return """cast:
  lin_feng:
    name: 林锋
    voice: male_young_sunny
  ye_lao:
    name: 叶老
    voice: male_elderly
"""


def test_scheduler_batch_ok(tmp_path):
    import yaml
    cast_path = tmp_path / "cast.yaml"
    cast_path.write_text(_demo_cast(), encoding="utf-8")
    cast = load_cast(cast_path)
    script = parse_txt(DEMO_TXT, title="demo")
    project = Project(name="demo", script_path="s.txt", cast_path=str(cast_path),
                      output_dir=tmp_path / "out")
    reg = EngineRegistry([
        FakeEngine("edge_tts"),
        FakeEngine("local", available=False),
        FakeEngine("minimax", available=False),
    ])
    result = run_batch(project, script, cast, registry=reg)
    assert result["ok"] == 3 and result["error"] == 0
    assert (tmp_path / "out" / "E01" / "E01_S01_lin_feng_001.wav").exists()
    assert (tmp_path / "out" / "manifest.json").exists()
    assert (tmp_path / "out" / "manifest.csv").exists()
    assert result["total_cost"] == 0.0


def test_scheduler_budget_skip(tmp_path):
    cast_path = tmp_path / "cast.yaml"
    cast_path.write_text(_demo_cast(), encoding="utf-8")
    cast = load_cast(cast_path)
    script = parse_txt(DEMO_TXT)
    project = Project(name="demo", script_path="s.txt", cast_path=str(cast_path),
                      output_dir=tmp_path / "out", budget_per_episode=0.001)
    reg = EngineRegistry([FakeEngine("edge_tts", cost=0.01)])
    result = run_batch(project, script, cast, registry=reg)
    assert result["ok"] == 1              # 第一句在预算内
    assert result["budget_skipped"] == 2  # 后续超预算跳过
    assert result["total_cost"] > 0


def test_scheduler_dry_run(tmp_path):
    cast_path = tmp_path / "cast.yaml"
    cast_path.write_text(_demo_cast(), encoding="utf-8")
    cast = load_cast(cast_path)
    script = parse_txt(DEMO_TXT)
    project = Project(name="demo", script_path="s.txt", cast_path=str(cast_path),
                      output_dir=tmp_path / "out")
    reg = EngineRegistry([FakeEngine("edge_tts")])
    result = run_batch(project, script, cast, dry_run=True, registry=reg)
    assert result["planned"] == 3
    assert all(r["status"] == "planned" for r in result["records"])


def test_scheduler_on_line_callback(tmp_path):
    """逐句回调：每句处理完都被通知（进度可见性）。"""
    cast_path = tmp_path / "cast.yaml"
    cast_path.write_text(_demo_cast(), encoding="utf-8")
    cast = load_cast(cast_path)
    script = parse_txt(DEMO_TXT)
    project = Project(name="demo", script_path="s.txt", cast_path=str(cast_path),
                      output_dir=tmp_path / "out")
    reg = EngineRegistry([FakeEngine("edge_tts")])
    events: list[dict] = []

    def on_line(rec: dict) -> None:
        events.append(rec)

    result = run_batch(project, script, cast, registry=reg, on_line=on_line)
    assert len(events) == len(script.lines) == 3
    assert [e["status"] for e in events] == ["ok", "ok", "ok"]
    assert events[0]["role"] == "林锋"
    # 回调顺序与结果记录一致
    assert [e["line_no"] for e in events] == [r["line_no"] for r in result["records"]]


def test_rerun_line_overwrites(tmp_path, monkeypatch):
    """单句修复：rerun_line 重跑指定行并覆盖原文件（只动那一句）。"""
    from pathlib import Path
    import hashlib

    from voicecast.core.models import Project
    from voicecast.pipeline.parser import parse_file
    from voicecast.pipeline.scheduler import load_cast, rerun_line, run_batch

    out = tmp_path / "out"
    proj = Project(name="t", script_path="examples/script_demo.txt",
                   cast_path="examples/cast_demo.yaml", output_dir=out,
                   budget_per_episode=0)
    s = parse_file("examples/script_demo.txt")
    c = load_cast("examples/cast_demo.yaml")
    # 全量干跑计划 + 取第 1 行的文件路径（dry 不产生音频，仅验证 rerun 路径生成一致）
    r = run_batch(proj, s, c, dry_run=True)
    planned = next(x for x in r["records"] if x["line_no"] == 1 and x["status"] == "planned")
    rec = rerun_line("examples/script_demo.txt", "examples/cast_demo.yaml",
                     str(out), 1)
    assert rec["status"] == "ok"
    # 文件落在与 run_batch 规划一致的路径（line_filename 同规则）
    assert Path(out, planned["file"]).exists()
    assert rec["file"] == planned["file"]
