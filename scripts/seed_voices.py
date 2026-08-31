#!/usr/bin/env python
"""种子音色库生成（薄封装，逻辑在 voicecast.design.seed）。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from voicecast.design.seed import generate_seed_library  # noqa: E402

if __name__ == "__main__":
    paths = generate_seed_library()
    print(f"种子音色库完成：{len(paths)} 个\n" + "\n".join(str(p) for p in paths))
