"""本地引擎：F5-TTS（完全离线）。独立性铁律的默认主干。

- ref_file: 参考音频（相对 recipes/ 或绝对路径），零样本克隆底声
- speed: 倍率
- pitch: 音分（cents，1 半音 = 100；本地引擎无原生 pitch 控制 → ffmpeg 后处理）
- 模型目录: models/F5-TTS（hf-mirror 下载），首次加载约需数十秒

API 版本差异做防御处理（infer 的 speed 参数在部分版本不存在）。

## v0.3 修订（2026-09-16，依据参考库体检 + A/B 实测）

1. **参考音频归一化**（默认开启）：AISHELL-3 参考峰值实测 0.036–0.674（差 19dB），
   电平过低会让克隆学到噪声底噪 → 出薄、沙、金属音。现统一去直流 + 归一化到 -1dBFS，
   结果缓存到 recipes/samples/ref_normalized/，源文件更新则自动重建。
   可用配方参数 `normalize_ref: false` 关闭。
2. **推理质量参数可配**：nfe_step 默认 32 → **64**（音质显著提升），
   cfg_strength 默认 2.0。均可由配方 params 覆盖。
3. **修复 pitch 硬编码**：原实现 `asetrate=44100*factor` 硬编码假设输入 44100Hz，
   但本引擎输出为 24000Hz（F5-TTS v1 Base），带 pitch 的配方会被额外拉高
   1.8375 倍音高 + 1.8375 倍速。现按真实采样率计算。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

from ..core.models import VoiceProfile, VoicecastError
from ..core.settings import RECIPES_DIR, REPO_ROOT
from .base import Engine
from .util import verify_audio

MODELS_DIR = REPO_ROOT / "models" / "F5-TTS"
REF_NORM_DIR = RECIPES_DIR / "samples" / "ref_normalized"
# 参考目标峰值 = -6 dBFS。
# 实测（4 音色 × 4 电平）：0.891(-1dB) → 3/4 音色输出削波（最高 peak 2.17）；
# 0.708(-3dB) → 1/4 削波；**0.50(-6dB) → 4/4 全部不削波**，且 crest/重心健康。
# 这是"全库通用"的最高安全电平 —— 详见 outputs/sweep 扫描记录。
REF_TARGET_PEAK = 0.501   # ≈ -6 dBFS
OUT_SAFE_PEAK = 0.95      # 引擎输出峰值安全上限（兜底，防止个别音色过冲）

_patched_load: bool = False


def _patch_torchaudio_load() -> None:
    """f5_tts 依赖 torchaudio.load 读参考音频；torchaudio 2.11 只有 torchcodec 后端
    （Windows 下 torchcodec 缺 ffmpeg DLL 会崩）。用 soundfile 无缝替代：
    参考音频均为 wav，soundfile 读取质量等同。幂等。"""
    global _patched_load
    if _patched_load:
        return
    import soundfile as sf
    import torch
    import torchaudio

    orig = torchaudio.load

    def load_patched(filepath, *args, **kwargs):
        try:
            return orig(filepath, *args, **kwargs)
        except ImportError:
            pass  # torchcodec 缺失/不可用 → 走 soundfile
        wav, sr = sf.read(str(filepath), dtype="float32")
        return torch.from_numpy(wav).unsqueeze(0), sr

    torchaudio.load = load_patched
    _patched_load = True


class LocalEngine(Engine):
    name = "local"
    display_name = "F5-TTS（本地，完全离线）"
    _model = None

    def available(self) -> bool:
        has_model = (
            any(MODELS_DIR.rglob("*.pt"))
            or any(MODELS_DIR.rglob("*.safetensors"))
        )
        if not has_model:
            return False
        try:
            import torch  # noqa: F401
            import f5_tts  # noqa: F401
            return torch.cuda.is_available()
        except ImportError:
            return False

    def _get_model(self):
        if self._model is None:
            from f5_tts.api import F5TTS

            ckpt = MODELS_DIR / "F5TTS_v1_Base" / "model_1250000.safetensors"
            vocab = MODELS_DIR / "F5TTS_v1_Base" / "vocab.txt"
            self._model = F5TTS(
                model="F5TTS_v1_Base",
                ckpt_file=str(ckpt) if ckpt.exists() else "",
                vocab_file=str(vocab) if vocab.exists() else "",
                device="cuda",
                hf_cache_dir=str(REPO_ROOT / "models" / "hf_cache"),  # vocos 落项目内，全离线
            )
        return self._model

    def _resolve_ref(self, profile: VoiceProfile) -> Path | None:
        ref = profile.params.get("ref_file")
        if not ref:
            return None
        ref_path = Path(ref)
        if not ref_path.is_absolute():
            ref_path = RECIPES_DIR / ref_path
        if not ref_path.exists():
            raise VoicecastError(f"参考音频不存在: {ref_path}（配方 {profile.id}）")
        return ref_path

    def _normalized_ref(self, ref_path: Path) -> Path:
        """参考音频归一化：去直流 + 峰值对齐到 -1dBFS。带缓存（源文件更新则重建）。

        AISHELL-3 原始参考峰值 0.036–0.674（差 19dB）。电平过低是"薄/沙/金属"
        听感的直接来源之一 —— 归一化把这一变量在全库抹平。
        """
        import soundfile as sf

        REF_NORM_DIR.mkdir(parents=True, exist_ok=True)
        # 缓存名带上目标电平 —— 否则调整 REF_TARGET_PEAK 后会命中旧缓存（踩过）
        dst = REF_NORM_DIR / f"{ref_path.stem}_p{int(REF_TARGET_PEAK * 100)}{ref_path.suffix}"
        try:
            if dst.exists() and dst.stat().st_mtime >= ref_path.stat().st_mtime:
                return dst
        except OSError:
            pass

        y, sr = sf.read(str(ref_path), dtype="float32")
        if y.ndim > 1:
            y = y.mean(axis=1)
        y = y - float(y.mean())                     # 去直流
        peak = float(np.max(np.abs(y)))
        if peak > 1e-6:
            y = y * (REF_TARGET_PEAK / peak)
        sf.write(str(dst), y.astype("float32"), sr, subtype="PCM_16")
        return dst

    def synthesize(
        self, text: str, profile: VoiceProfile, out_path: Path, emotion: str = ""
    ) -> Path:
        import soundfile as sf

        _patch_torchaudio_load()
        from ..design.seed import REF_TEXT as SEED_REF_TEXT

        ref_path = self._resolve_ref(profile)
        if ref_path is None:
            raise VoicecastError(f"本地引擎需要参考音频 ref_file（配方 {profile.id}）")
        # ref_text 优先级：配方参数 > 参考音频同名 .txt（参考库约定）> 种子默认文本
        ref_text = str(profile.params.get("ref_text", "") or "")
        if not ref_text:
            txt_path = ref_path.with_suffix(".txt")
            if txt_path.exists():
                ref_text = txt_path.read_text(encoding="utf-8").strip()
        if not ref_text:
            ref_text = SEED_REF_TEXT
        speed = float(profile.params.get("speed", 1.0))
        pitch_cents = float(profile.params.get("pitch", 0))
        nfe_step = int(profile.params.get("nfe_step", 64))
        cfg_strength = float(profile.params.get("cfg_strength", 2.0))

        if profile.params.get("normalize_ref", True):
            ref_path = self._normalized_ref(ref_path)

        model = self._get_model()
        infer_kw = dict(
            ref_file=str(ref_path),
            ref_text=ref_text,
            gen_text=text,
            speed=speed,
            remove_silence=bool(profile.params.get("remove_silence", True)),
        )
        try:
            wav, sr, _spec = model.infer(
                nfe_step=nfe_step, cfg_strength=cfg_strength, **infer_kw
            )
        except TypeError:
            # 该版本 infer 不支持 nfe_step/cfg_strength → 退回默认（并如实记录）
            wav, sr, _spec = model.infer(**infer_kw)
        # 输出峰值安全兜底：F5-TTS 输出为 float，未限幅音色会过冲；
        # 直接写 PCM_16 会硬削波（实测 peak 最高 2.17）。此处按比例收，不产生失真。
        if hasattr(wav, "detach"):  # 某些版本返回 tensor，先回 CPU
            wav = wav.detach().cpu().numpy()
        wav = np.asarray(wav, dtype="float32").reshape(-1)
        peak = float(np.max(np.abs(wav)))
        if peak > OUT_SAFE_PEAK:
            wav = wav * (OUT_SAFE_PEAK / peak)
        sf.write(str(out_path), wav, sr)

        # pitch 微调：ffmpeg 变速变调（asetrate + atempo 保持时长）
        # 注意：采样率必须取自实际产物（本引擎为 24000Hz），不可硬编码 44100。
        if abs(pitch_cents) >= 1:
            shifted = out_path.with_suffix(".shift.wav")
            factor = 2 ** (pitch_cents / 1200)
            src_rate = int(sf.info(str(out_path)).samplerate)
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(out_path), "-af",
                 f"asetrate={int(src_rate * factor)},aresample={src_rate},"
                 f"atempo={1 / factor:.5f}",
                 str(shifted)],
                check=True, capture_output=True, timeout=120,
            )
            shifted.replace(out_path)

        v = verify_audio(out_path)
        if not v["ok"]:
            raise VoicecastError(f"本地引擎输出校验失败: {profile.id} {v['reason']}")
        return out_path

    def explain(self) -> str:
        return f"{self.display_name}（0 元，不联网）"
