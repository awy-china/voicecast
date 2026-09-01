# 🎙️ VoiceCast 声演工作室

**以角色为中心的 AI 配音工作台** —— 描述/混合/微调"造出"想要的角色声音，用角色表锁死跨集一致性，剧本一键批量出可进剪映的分句音频。**本地优先、零供应商依赖，无任何 API key 也能全流程运行。**

> GPT-SoVITS / F5-TTS / edge-tts / MiniMax 都只是可插拔引擎——项目本体不依赖任何单一供应商。

---

## ✨ 特性

| 特性 | 说明 |
|---|---|
| 🎨 **音色设计器** | 输入"老年女声"→ 规则/LLM 翻译 → **直接生成一个最匹配的音色**（真人参考→GPT-SoVITS 克隆）→ 滑杆微调 |
| 🎭 **音色混合器** | 主参考 × 辅助参考 → **GPT-SoVITS 多说话人融合出独特新音色** → 保存为配方（55 个真人参考两两组合 = 数千种潜在音色） |
| 🎚️ **去AI味后处理** | 呼吸声注入 + 微颤动 + EQ 塑形 + 压缩限幅 + 微量混响 + LUFS 响度归一化（off/clean/natural 三档） |
| 🎭 **角色表 Cast** | 角色 ↔ 音色配方 ↔ 情绪参数 持久化（YAML），跨集听感不漂移 |
| 📜 **剧本流水线** | txt 标记式剧本 → 自动分角色 → 批量生成 → `E01_S02_角色_003.wav` + manifest 账本（成本/引擎/溯源） |
| 💰 **成本路由 + 降级链** | 本地(0元) → GPT-SoVITS(0元) → edge-tts(0元) → MiniMax(按量)；宿主引擎不可用自动降级（如 GPT 服务未启动 → F5-TTS） |
| 🔒 **合规门禁** | 音色溯源 + 克隆门禁（仅自有授权声音）+ 敏感词过滤 |
| 🖥️ **三件套** | Python 库 + CLI（`voicecast.bat`）+ Gradio Web（试听/角色表/批量） |

## 🚀 快速开始

```bash
# 1. 安装依赖（Python 3.11+）
uv venv .venv --python 3.11
uv pip install --python .venv -e . -i https://pypi.tuna.tsinghua.edu.cn/simple

# 2. 看引擎状态（零配置即可用）
voicecast engines

# 3. 音色设计：描述 → 直接生成
voicecast design "老年女声"

# 4. 音色混合：造独特新音色（GPT-SoVITS 在线时）
voicecast blend aishell3_SSB0016 aishell3_SSB0309 --save

# 5. 剧本一键批量配音
voicecast run examples/script_demo.txt examples/cast_demo.yaml --out-dir outputs/demo

# 6. Web 界面
web.bat   # http://127.0.0.1:7860
```

> Windows 下直接用仓库根的 `voicecast.bat` / `web.bat`，无需安装。

### GPT-SoVITS（生产级克隆，推荐）

```bash
gptsovits_api.bat        # 一键启动 API 服务（http://127.0.0.1:9880，首次加载模型 1-2 分钟）
voicecast engines        # 确认 gpt_sovits 显示 ✅ 可用
```

- 整合包：`lj1995/GPT-SoVITS-windows-package` 的 **v2pro-nvidia50** 版（RTX 50 系专用，8.23GB，hf-mirror）
- aishell3 真人配方在服务在线时自动走 GPT-SoVITS；离线自动降级 F5-TTS，**不会报错**

### 真人参考库（AISHELL-3，Apache-2.0）

- 55 说话人 / 165 段（性别 × 年龄组 A<14/B14-25/C26-40/D>41 × 口音），40 个 3-10s 拼接参考
- 配方：`recipes/ref_voices_aishell3.yaml`（55 条，host=gpt_sovits + fallback local）
- 重新生成：`scripts/prepare_aishell3.py`（下载 18GB tgz 后）+ `scripts/build_gptsovits_refs.py`

### 本地引擎（F5-TTS，完全离线）

```bash
bash scripts/setup_local_engine.sh   # torch(cu128) + F5-TTS + 模型下载（hf-mirror）
voicecast route male_elderly         # 查看路由结果
```

## 🧩 架构

```
voicecast/
├── core/        数据模型（VoiceProfile / Role / Cast / Script / Project / EnginePref.fallback）
├── design/      ★设计器（规则翻译 + LLM增强 + 滑杆）+ ★音色混合器（blender）
├── engines/     ★适配层：local(F5-TTS) / gpt_sovits / edge_tts / minimax
├── postprocess/ ★去AI味后处理链（ffmpeg，off/clean/natural 三档）
├── pipeline/    剧本解析 → 成本路由 → 批量调度 → 归档
├── compliance/  溯源 + 克隆门禁 + 敏感词
├── cli/ + web/  typer CLI + Gradio Web
└── recipes/     配方库（voice_profiles + ref_voices_aishell3 + ref_voices_blend；CC BY-NC）
```

**路由一句话**：音色归属决定"能不能选"（克隆音色焊死宿主引擎），宿主不可用走 fallback 降级链，成本路由决定"选哪个"（本地→GPT→edge→MiniMax），质量门槛和预算决定"敢不敢选便宜的"。

## 📄 数据格式（预留格式）

```yaml
# cast.yaml —— 一部剧 = 一份文件
cast:
  lin_feng:
    name: 林锋
    voice: aishell3_SSB0016     # 真人参考配方（GPT-SoVITS 克隆）
    default_emotion: 坚定
```

```txt
# script.txt —— 标记式剧本（主格式），JSON 内部标准可双向互转
【场景】S01
【情绪】平静
【林锋】这把剑，是我师父传下来的。
```

## 🔌 引擎支持

| 引擎 | 成本 | 依赖 | 说明 |
|---|---|---|---|
| **GPT-SoVITS（本地）** | 0 元 | 整合包 + `gptsovits_api.bat` | **生产级中文克隆**（多说话人融合/情感/语速控制），RTX 50 专用版 |
| **F5-TTS（本地）** | 0 元 | 显卡 + 模型下载 | 完全离线零样本克隆，GPT 离线时的自动降级目标 |
| **edge-tts** | 0 元 | 联网 | 零 key 免费兜底，8 个中文音色 + 变调配方 |
| **MiniMax** | 按量 | `MINIMAX_API_KEY` | 可选插件，无 key 自动跳过 |

## ⚖️ 合规与伦理

- **音色溯源**：每个配方记录来源与授权状态（AISHELL-3 = Apache-2.0，见 `recipes/samples/ref/LICENSE-DATA.md`）
- **克隆门禁**：仅允许克隆自有授权声音，禁止克隆名人/他人声音
- **内容审核**：生成前敏感词过滤，词库可插拔
- 本项目不用于、也不允许用于任何侵权、诈骗、伪造场景

## 📜 许可

- **代码**：MIT License
- **recipes/ 音色配方库**：CC BY-NC 4.0（数据资产，保留非商用保护）
- **AISHELL-3 参考音频**：Apache License 2.0（数据集自带许可，见 LICENSE-DATA.md）

## 🗺️ 路线图

- ✅ 一期：设计器（单结果）/ 音色混合器 / 后处理链 / 角色表 / 剧本流水线 / 成本路由+降级链 / 合规门禁 / CLI / Web
- 🔜 二期：Web 音色混合器界面、融合配方描述匹配、SRT/Excel 导入、自动混音、情感指令
