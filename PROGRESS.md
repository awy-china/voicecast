# PROGRESS — VoiceCast（声演工作室）

> 进度账本。状态：🟡 进行中 / ✅ 完成 / ⛔ 阻塞

## 总览

| 里程碑 | 状态 | 备注 |
|---|---|---|
| M0 骨架+环境 | ✅ | torch 2.11+cu128 装好 CUDA 点亮；F5-TTS 本地引擎**完全离线合成成功** |
| M1 core+配方库+种子音色 | ✅ | 23 条通用配方 + 8 种子音色 |
| M2 引擎适配层 | ✅ | local ✅ / edge_tts ✅ / minimax 可选插件 |
| M3 音色设计器 | ✅ | 规则+LLM 双后端，候选试听实测 |
| M4 剧本流水线 | ✅ | 解析/路由/调度/归档全通 |
| M5 合规门禁 | ✅ | 溯源/克隆门禁/敏感词 |
| M6 CLI | ✅ | voicecast.bat 全命令可用 |
| M7 Gradio Web | ✅ | 127.0.0.1:7860（web.bat） |
| M8 GitHub 收尾 | 🟡 | README/LICENSE/CI/发布清单就绪，**不 push 等用户批准** |

## 关键事实（2026-09-01 更新）
- 测试：36 passed
- **本地引擎实测**：`outputs/f5_first_test.wav` 完全离线合成（4.84s/句，首次加载 21s）；vocos 已缓存 `models/hf_cache`，之后零联网
- 引擎状态：local ✅（F5-TTS 离线）| edge_tts ✅（免费）| minimax ⛔（无 key 自动跳过）
- 全流程成本：0 元
- 环境：RTX 5060 Laptop 8GB；D 盘余 ~180G（models 6.3G + 缓存）

## 执行日志
- 2026-08-31 开工；设计定稿 → M1~M8 全里程碑推进
- 2026-09-01 本地引擎攻坚完成：torchcodec DLL 坑 → 卸载 + soundfile 兜底 patch；vocos 走 hf-mirror 落项目内
