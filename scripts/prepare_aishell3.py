"""AISHELL-3 → VoiceCast 参考音频库 处理脚本

流程：解压 tgz → 解析 speaker.info（性别/年龄）→ 按 (性别×年龄) 分桶精选
→ 每说话人取 2-3 段 → 转 24kHz 单声道 wav → 带对应文本入库
→ 生成 manifest（speaker/性别/年龄/来源/许可）→ 授权声明。

数据源：AISHELL-3（Apache 2.0，218 说话人，含性别与年龄组标注，
汉字级成绩单）——满足"各年龄/性别/多种类真人声音"且完全合规。
"""

from __future__ import annotations

import csv
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]          # D:/VoiceCast
CACHE = REPO / ".cache_tmp" / "cv"
TGZ = CACHE / "data_aishell3.tgz"
EXTRACT = CACHE / "extracted"
DATA = EXTRACT / "data_aishell3"
OUT = REPO / "recipes" / "samples" / "ref"

# 每桶（性别×年龄组）最多取多少说话人；每说话人取几段
MAX_SPEAKERS_PER_BUCKET = 14
SEGS_PER_SPEAKER = 3
MIN_LEN, MAX_LEN = 8, 34  # 句长（字符）范围


def extract() -> None:
    if DATA.exists():
        print("已解压，跳过")
        return
    print("解压中（约 25GB）…")
    with tarfile.open(TGZ, "r:gz") as t:
        t.extractall(EXTRACT)
    print("解压完成")


def parse_speakers() -> dict[str, dict]:
    """speaker.info: speaker_id \\t gender \\t age"""
    info_path = DATA / "speaker.info"
    speakers: dict[str, dict] = {}
    for line in info_path.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split("\t")
        if len(parts) >= 2:
            sid = parts[0]
            speakers[sid] = {"gender": parts[1], "age": parts[2] if len(parts) > 2 else "unknown"}
    return speakers


def load_texts(speaker: str) -> dict[str, str]:
    """txt/{speaker}.txt: wav_id \\t 汉字文本 \\t 拼音"""
    txt_path = DATA / "train" / "txt" / f"{speaker}.txt"
    out: dict[str, str] = {}
    if not txt_path.exists():
        return out
    for line in txt_path.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split("\t")
        if len(parts) >= 2:
            out[parts[0]] = parts[1]
    return out


def main() -> None:
    if not TGZ.exists() or TGZ.stat().st_size < 1_000_000_000:
        print(f"tgz 不存在或未下载完整: {TGZ}")
        sys.exit(1)
    extract()

    speakers = parse_speakers()
    print(f"说话人总数: {len(speakers)}")

    # 分桶：gender × age
    buckets: dict[tuple[str, str], list[str]] = {}
    for sid, meta in speakers.items():
        buckets.setdefault((meta["gender"], meta["age"]), []).append(sid)
    print("桶分布:", {f"{g}/{a}": len(v) for (g, a), v in sorted(buckets.items())})

    OUT.mkdir(parents=True, exist_ok=True)
    rows: list[list] = []
    selected_speakers = 0
    segments = 0
    seen = set()

    for (gender, age), sids in sorted(buckets.items()):
        if gender not in ("male", "female"):
            continue
        picked = 0
        for sid in sids:
            if picked >= MAX_SPEAKERS_PER_BUCKET:
                break
            texts = load_texts(sid)
            cand = [(wid, t) for wid, t in texts.items() if MIN_LEN <= len(t) <= MAX_LEN]
            if len(cand) < SEGS_PER_SPEAKER:
                continue
            cand = sorted(cand, key=lambda x: len(x[1]))[:: max(1, len(cand) // 10)][:SEGS_PER_SPEAKER]
            wav_dir = DATA / "train" / "wav" / sid
            got = 0
            for wid, text in cand:
                src = wav_dir / f"{wid}.wav"
                if not src.exists():
                    continue
                out_name = f"aishell3_{sid}_{wid}"
                if out_name in seen:
                    continue
                seen.add(out_name)
                dst_wav = OUT / f"{out_name}.wav"
                subprocess.run(
                    ["ffmpeg", "-y", "-i", str(src), "-ar", "24000", "-ac", "1",
                     "-acodec", "pcm_s16le", str(dst_wav)],
                    check=True, capture_output=True,
                )
                (OUT / f"{out_name}.txt").write_text(text, encoding="utf-8")
                rows.append([sid, gender, age, out_name, len(text), "AISHELL-3", "Apache-2.0"])
                got += 1
                segments += 1
            if got:
                picked += 1
                selected_speakers += 1
            print(f"  [{gender}/{age}] {sid}: +{got} 段")

    # manifest
    with open(OUT / "manifest.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["speaker", "gender", "age", "file", "text_len", "source", "license"])
        w.writerows(rows)

    # 授权声明
    (OUT / "LICENSE-DATA.md").write_text(
        "# 参考音频数据来源与许可\n\n"
        "- 数据集: **AISHELL-3**（多说话人中文普通话语料库, 218 说话人）\n"
        "- 许可: **Apache License 2.0**（可自由使用/修改/分发，需保留署名）\n"
        "- 内容: 中性情绪朗读，含性别与年龄组标注、汉字级成绩单\n"
        "- 用途: 本项目仅用作本地克隆（F5-TTS 零样本）的参考底声，数据由使用者自持\n"
        "- 原文: https://www.openslr.org/93/ ｜ arXiv:2010.11567\n"
        "- 下载镜像: ModelScope OmniData/AISHELL-3\n",
        encoding="utf-8",
    )

    # 参考配方：每个选中说话人 1 条（ref_file 指向其第一段，ref_text 自动读同名 txt）
    write_recipes(rows)

    print(f"\n✅ 完成: {selected_speakers} 个说话人 / {segments} 段参考音频")
    print(f"入库: {OUT}")


AGE_MAP = {
    "teens": "少年", "twenties": "青年", "thirties": "青年",
    "forties": "中年", "fifties": "中年", "sixties": "老年",
    "unknown": "成人",
}
GENDER_MAP = {"male": "男", "female": "女", "other": "中性"}


def write_recipes(rows: list[list]) -> None:
    """为每个说话人生成 1 条参考配方（id=aishell3_<speaker>），
    写入 recipes/ref_voices_aishell3.yaml，规则引擎可按 性别/年龄 匹配。"""
    by_speaker: dict[str, dict] = {}
    for sid, gender, age, out_name, _tl, _src, _lic in rows:
        if sid not in by_speaker:
            by_speaker[sid] = {"gender": gender, "age": age, "first": out_name}

    profiles: list[dict] = []
    for sid, meta in sorted(by_speaker.items()):
        gender_cn = GENDER_MAP.get(meta["gender"], "成人")
        age_cn = AGE_MAP.get(meta["age"], "成人")
        profiles.append({
            "id": f"aishell3_{sid}",
            "name": f"真人参考·{gender_cn}·{age_cn}",
            "engine": {"host": "local"},
            "params": {"ref_file": f"samples/ref/{meta['first']}.wav"},
            "tags": [gender_cn, age_cn, "真人参考"],
            "note": f"AISHELL-3 {sid}（{meta['gender']}/{meta['age']}，Apache-2.0）",
        })

    out = REPO / "recipes" / "ref_voices_aishell3.yaml"
    out.write_text(
        "# 参考音频配方（自动生成自 scripts/prepare_aishell3.py）\n"
        "# 数据源 AISHELL-3（Apache-2.0）：真实人声，含性别/年龄标注。\n"
        "# ref_text 自动读取 samples/ref/<同名>.txt；wav 本体不入 git（见 .gitignore）。\n"
        + yaml_dump({"profiles": profiles}),
        encoding="utf-8",
    )
    print(f"配方已生成: {out}（{len(profiles)} 条）")


def yaml_dump(data: dict) -> str:
    import yaml

    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)


if __name__ == "__main__":
    main()
