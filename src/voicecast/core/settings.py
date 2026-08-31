"""路径与配置：仓库根、配方库、输出目录，全部可环境变量覆盖。"""

from __future__ import annotations

import os
from pathlib import Path

# 仓库根：src/voicecast/core/settings.py -> parents: [core, voicecast, src, REPO]
REPO_ROOT = Path(__file__).resolve().parents[3]

RECIPES_DIR = Path(os.environ.get("VOICECAST_RECIPES_DIR", REPO_ROOT / "recipes"))
SEED_DIR = RECIPES_DIR / "samples" / "seed"
OUTPUTS_DIR = Path(os.environ.get("VOICECAST_OUTPUTS_DIR", REPO_ROOT / "outputs"))
