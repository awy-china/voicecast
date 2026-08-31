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


class LocalEngine(Engine):
    name = "local"
    display_name = "F5-TTS（本地，完全离线）"
    _model = None

    def available(self) -> bool:
        if not (MODELS_DIR / "model_1250000.pt").exists():
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
            self._model = F5TTS(device="cuda")
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

        ref_path = self._resolve_ref(profile)
        speed = float(profile.params.get("speed", 1.0))
        pitch_cents = float(profile.params.get("pitch", 0))

        model = self._get_model()
        kwargs: dict = {"text": text}
        if ref_path:
            kwargs["ref_file"] = str(ref_path)
        try:
            wav, sr, _spec = model.infer(**kwargs, speed=speed)
        except TypeError:
            # 老版本 API 无 speed 参数
            wav, sr, _spec = model.infer(**kwargs)
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
