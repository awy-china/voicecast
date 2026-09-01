# PROGRESS — VoiceCast（声演工作室）

> 进度账本。状态：🟡 进行中 / ✅ 完成 / ⛔ 阻塞

## 总览

| 里程碑 | 状态 | 备注 |
|---|---|---|
| M0 骨架+环境 | ✅ | torch 2.11+cu128 CUDA 点亮；F5-TTS 完全离线合成成功 |
| M1 core+配方库+种子音色 | ✅ | 23 条通用配方 + 8 种子音色 |
| M2 引擎适配层 | ✅ | local / gpt_sovits / edge_tts / minimax 四引擎 |
| M3 音色设计器 | ✅ | 规则+LLM 双后端，**单结果直接生成**（用户指令去候选） |
| M4 剧本流水线 | ✅ | 解析/路由/调度/归档全通，实时进度面板 |
| M5 合规门禁 | ✅ | 溯源/克隆门禁/敏感词 |
| M6 CLI | ✅ | voicecast.bat 全命令可用（design/blend/run/route/engines） |
| M7 Gradio Web | ✅ | 127.0.0.1:7860（web.bat）；修复 Blocks 嵌套双实例 bug |
| M8 GitHub 收尾 | 🟡 | README/LICENSE/CI/发布清单就绪，**不 push 等用户批准** |
| M9 生产级引擎 | ✅ | **GPT-SoVITS v2pro（RTX50版）接入**：api_v2 服务 + HTTP 适配层 + fallback 降级链 |
| M10 真人参考库 | ✅ | **AISHELL-3**：55 说话人/165 段（性别×年龄A/B/C/D×口音），40 个 3-10s 拼接参考，55 条可路由配方 |
| M11 去AI味后处理 | ✅ | 呼吸声注入+微颤动+EQ+压缩+混响+LUFS，档位 off/clean/natural |
| M12 音色混合器 | ✅ | 主参考×辅助参考 GPT-SoVITS 多说话人融合 → 独特新音色 → 保存为配方 |

## 关键事实（2026-09-02 更新）

- **测试：44 passed**（pytest tests -q）
- 引擎状态：local ✅（F5-TTS 离线）| gpt_sovits ✅（服务在线，127.0.0.1:9880）| edge_tts ✅ | minimax ⛔（无 key）
- **GPT-SoVITS**：整合包 `gptsovits_api.bat` 一键启动；RTX 50 nvidia50 专用版；克隆实测 44.8s/句；**aishell3 真人配方在线走 GPT、离线自动降级 local**
- **参考库**：`recipes/samples/ref/`（205 wav + 对应 txt，wav 本体 gitignore）；配方 78 条（22 基础 + 55 真人 + 1 融合）
- **后处理链**：`postprocess/chain.py`，调度器与设计器自动接入，档位由配方 `params.postprocess` 控制
- **音色混合器**：`voicecast.bat blend aishell3_SSB0016 aishell3_SSB0309 --save` → 融合音色 + 配方入库
- 全流程成本：0 元（免费引擎）；环境：RTX 5060 Laptop 8GB；D 盘余 ~138G

## 实测记录（本轮会话）

- `voicecast.bat design "老年女声"` → **aishell3_SSB0309（真人·女·老年）→ GPT-SoVITS 克隆成功**
- `voicecast.bat blend aishell3_SSB0016 aishell3_SSB0309` → **女青年×老年 融合音色生成并保存为配方**
- 路由升降级：GPT 在线→gpt_sovits；停服→local 兜底不报错
- 大文件事故：18GB tgz 误入 git → filter-branch 历史重写 + gc，仓库 1.4G → 201K

## 执行日志

- 2026-08-31 开工；设计定稿 → M1~M8 推进
- 2026-09-01 本地引擎攻坚（torchcodec DLL 坑→soundfile 兜底）；Web 双实例 bug 修复；edge-tts 重试；候选去重/补足/数量对版；单结果设计器
- 2026-09-02 GPT-SoVITS 下载/解压/服务/适配（JSON body 坑）；AISHELL-3 下载处理入库（扁平结构/spk-info/wav后缀三坑）；后处理链；音色混合器
