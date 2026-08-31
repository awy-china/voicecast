"""本地引擎：F5-TTS（完全离线）。独立性铁律的默认主干。

- ref_file: 参考音频（相对 recipes/ 或绝对路径），零样本克隆底声
- speed: 倍率
- pitch: 音分（cents，1 半音 = 100；本地引擎无原生 pitch 控制 → ffmpeg 后处理）
- 模型目录: models/F5-TTS（hf-mirror 下载），首次加载约需数十秒

API 版本差异做防御处理（infer 的 speed 参数在部分版本不存在）。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from ..core.models import VoiceProfile, VoicecastError
from ..core.settings import RECIPES_DIR, REPO_ROOT
from .base import Engine
from .util import verify_audio

MODELS_DIR = REPO_ROOT / "models" / "F5-TTS"

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

    def synthesize(
        self, text: str, profile: VoiceProfile, out_path: Path, emotion: str = ""
    ) -> Path:
        import soundfile as sf

        _patch_torchaudio_load()
        from ..design.seed import REF_TEXT as SEED_REF_TEXT

        ref_path = self._resolve_ref(profile)
        if ref_path is None:
            raise VoicecastError(f"本地引擎需要参考音频 ref_file（配方 {profile.id}）")
        ref_text = str(profile.params.get("ref_text", "") or SEED_REF_TEXT)
        speed = float(profile.params.get("speed", 1.0))
        pitch_cents = float(profile.params.get("pitch", 0))

        model = self._get_model()
        wav, sr, _spec = model.infer(
            ref_file=str(ref_path),
            ref_text=ref_text,
            gen_text=text,
            speed=speed,
            remove_silence=True,
        )
        sf.write(str(out_path), wav, sr)

        # pitch 微调：ffmpeg 变速变调（asetrate + atempo 保持时长）
        if abs(pitch_cents) >= 1:
            shifted = out_path.with_suffix(".shift.wav")
            factor = 2 ** (pitch_cents / 1200)
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(out_path), "-af",
                 f"asetrate=44100*{factor:.5f},aresample=44100,atempo={1 / factor:.5f}",
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
