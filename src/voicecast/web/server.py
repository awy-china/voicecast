"""VoiceCast Web 后端（FastAPI）——声学实验室前端的数据与服务层。

API：
  GET  /                      单页前端（web/static/index.html）
  GET  /api/engines           引擎状态
  GET  /api/recipes?q=        配方列表（关键词过滤）
  GET  /api/samples           参考音色（混合器选择器用）
  POST /api/design            设计器：描述 → 直接生成音色（含波形）
  POST /api/blend             混合器：主参考 × 辅助参考 → 融合音色（含波形）
  POST /api/run               SSE 流式批量配音（逐句进度）
  GET  /api/cast?path=        角色表读取
  POST /api/cast              角色表保存
  GET  /api/audio?path=       音频文件（仅 outputs/ 下，防穿越）
"""

from __future__ import annotations

import json
import queue
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from ..core.io import load_recipe_library
from ..core.models import Project
from ..core.settings import OUTPUTS_DIR, REPO_ROOT
from ..design.blender import blend_recipe
from ..design.candidate_gen import generate_voice
from ..engines.registry import EngineRegistry
from ..pipeline.parser import parse_file
from ..pipeline.scheduler import load_cast, run_batch
from .waveform import wav_waveform

app = FastAPI(title="VoiceCast 声演工作室")

STATIC = Path(__file__).resolve().parent / "static"


# ---------------- 工具 ----------------

def _safe_audio(path: str) -> Path:
    p = (REPO_ROOT / path).resolve()
    out_root = OUTPUTS_DIR.resolve()
    if not str(p).startswith(str(out_root)):
        raise HTTPException(status_code=403, detail="路径越界")
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"音频不存在: {path}")
    return p


def _audio_payload(wav_path: Path, label: str, extra: dict | None = None) -> dict:
    rel = str(wav_path.relative_to(REPO_ROOT)).replace("\\", "/")
    return {
        "ok": True,
        "label": label,
        "audio_url": f"/api/audio?path={rel}",
        "waveform": wav_waveform(wav_path),
        **(extra or {}),
    }


# ---------------- API ----------------

@app.get("/api/engines")
def engines_api():
    reg = EngineRegistry()
    return [
        {"name": e.name, "display": e.display_name, "available": e.available(),
         "explain": e.explain()}
        for e in reg.all()
    ]


@app.get("/api/recipes")
def recipes_api(q: str = ""):
    lib = load_recipe_library()
    rows = []
    for p in lib.values():
        if q and q not in f"{p.id} {p.name} {' '.join(p.tags)}":
            continue
        rows.append({
            "id": p.id, "name": p.name, "tags": p.tags,
            "engine": p.engine.host, "ref": p.params.get("ref_file", ""),
        })
    rows.sort(key=lambda r: r["id"])
    return rows


@app.get("/api/samples")
def samples_api():
    """混合器选择器：可作参考的音色配方（真人参考 + 基础 + 已存融合）。"""
    lib = load_recipe_library()
    rows = []
    for p in lib.values():
        if p.params.get("ref_file") or p.params.get("ref_audio_path"):
            rows.append({"id": p.id, "name": p.name, "tags": p.tags,
                         "engine": p.engine.host})
    rows.sort(key=lambda r: r["id"])
    return rows


@app.post("/api/design")
def design_api(body: dict):
    desc = (body.get("description") or "").strip()
    if not desc:
        raise HTTPException(status_code=400, detail="请输入角色声音描述")
    r = generate_voice(desc)
    if not r.get("ok"):
        raise HTTPException(status_code=500, detail=r.get("error", "生成失败"))
    return _audio_payload(
        Path(r["audio"]), desc,
        {"profile": r["profile"].id, "name": r["profile"].name,
         "tags": r["profile"].tags, "engine": r["engine"],
         "reason": r.get("reason", ""), "params": r["profile"].params},
    )


@app.post("/api/blend")
def blend_api(body: dict):
    main = (body.get("main") or "").strip()
    aux = body.get("aux") or []
    if not main or not aux:
        raise HTTPException(status_code=400, detail="需要主参考与至少一个辅助参考")
    r = blend_recipe(main, [str(a) for a in aux])
    if not r.get("ok"):
        raise HTTPException(status_code=500, detail=r.get("error", "融合失败"))
    return _audio_payload(
        Path(r["audio"]), r["profile"].name,
        {"profile": r["profile"].id, "name": r["profile"].name,
         "tags": r["profile"].tags, "engine": r["engine"]},
    )


@app.post("/api/run")
async def run_api(body: dict):
    """SSE 流式批量配音：逐句进度事件 → 完成事件。"""
    script = body.get("script") or "examples/script_demo.txt"
    cast = body.get("cast") or "examples/cast_demo.yaml"
    out_dir = body.get("out_dir") or "outputs/web"
    dry = bool(body.get("dry", False))

    from ..compliance.sensitive_words import check_text

    def event_stream():
        q: queue.Queue = queue.Queue()
        done_box: dict = {}

        def on_line(rec: dict) -> None:
            q.put({"type": "line", **rec})

        def worker() -> None:
            try:
                s = parse_file(script)
                c = load_cast(cast)
                project = Project(name=s.title, script_path=script, cast_path=cast,
                                  output_dir=Path(out_dir), budget_per_episode=0)
                r = run_batch(project, s, c, dry_run=dry,
                              compliance_check=check_text, on_line=on_line)
                done_box["result"] = r
            except Exception as e:  # noqa: BLE001
                done_box["error"] = str(e)
            q.put({"type": "done"})

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        while True:
            item = q.get()
            if item["type"] == "done":
                break
            yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
        if "error" in done_box:
            yield f"data: {json.dumps({'type': 'error', 'error': done_box['error']}, ensure_ascii=False)}\n\n"
        else:
            r = done_box["result"]
            rows = [
                [rec.get("line_no"), rec.get("episode"), rec.get("role"),
                 rec.get("status"), rec.get("engine", ""),
                 rec.get("file", ""), rec.get("error", "")]
                for rec in r["records"]
            ]
            yield f"data: {json.dumps({'type': 'summary', 'ok': r['ok'], 'error': r['error'], 'blocked': r.get('blocked', 0), 'total_cost': r['total_cost'], 'rows': rows, 'manifest': r.get('manifest', '')}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/cast")
def cast_get(path: str = "examples/cast_demo.yaml"):
    try:
        c = load_cast(path)
        rows = [[r.id, r.name, r.voice, r.default_emotion, r.note]
                for r in c.cast.values()]
        return {"rows": rows, "count": len(rows)}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/cast")
def cast_save(body: dict):
    path = body.get("path") or "examples/cast_demo.yaml"
    rows = body.get("rows") or []
    try:
        c = load_cast(path)
        lib = load_recipe_library()
        for row in rows:
            rid, _name, voice, emotion, note = (list(row) + [""] * 5)[:5]
            role = c.cast.get(rid)
            if role is None:
                continue
            if voice and voice != role.voice:
                if voice not in lib:
                    return {"ok": False, "error": f"配方不存在: {voice}"}
                role.voice = voice
            if emotion:
                role.default_emotion = emotion
            if note is not None:
                role.note = note
        from ..core.io import save_yaml

        save_yaml(c.model_dump(mode="json"), path)
        return {"ok": True, "path": path}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/rerun")
def rerun_api(body: dict):
    """单句修复：只重跑指定行，覆盖原文件。"""
    script = body.get("script") or "examples/script_demo.txt"
    cast = body.get("cast") or "examples/cast_demo.yaml"
    out_dir = body.get("out_dir") or "outputs/web"
    line_no = int(body.get("line_no") or 0)
    new_text = (body.get("new_text") or "").strip() or None
    if line_no <= 0:
        raise HTTPException(status_code=400, detail="需要 line_no")
    try:
        from ..pipeline.scheduler import rerun_line

        rec = rerun_line(script, cast, out_dir, line_no, new_text=new_text)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))
    rel = rec.get("file", "")
    full_rel = f"{str(out_dir).strip('/')}/{rel}" if rel else ""  # outputs/web/E01/xxx.wav
    return {
        "ok": rec["status"] == "ok", "rec": {**rec, "file": full_rel},
        "audio_url": f"/api/audio?path={full_rel}" if full_rel else "",
        "waveform": wav_waveform(REPO_ROOT / full_rel) if full_rel else [],
    }


@app.get("/api/audio")
def audio_get(path: str = Query(...)):
    p = _safe_audio(path)
    return FileResponse(p, media_type="audio/wav")


# ---------------- 静态托管 ----------------

app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")
