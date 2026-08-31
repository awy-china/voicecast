# 🎙️ VoiceCast 声演工作室

**以角色为中心的 AI 配音工作台** —— 描述/混合/微调"凭空设计"出想要的角色声音，用角色表锁死跨集一致性，剧本一键批量出可进剪映的分句音频。**本地优先、零供应商依赖，无任何 API key 也能全流程运行。**

> MiniMax / edge-tts / F5-TTS 都只是项目里的可插拔引擎——项目本体不依赖任何单一供应商。

---

## ✨ 特性

| 特性 | 说明 |
|---|---|
| 🎨 **音色设计器** | 输入"反派中年男声，低沉阴险"→ LLM/规则引擎翻译成配方 → 出 2-3 个候选音频试听 → 滑杆微调（年龄/低沉/语速/亮度） |
| 🎭 **角色表 Cast** | 角色 ↔ 音色配方 ↔ 情绪参数 持久化（YAML），git 可版本管理，跨集听感不漂移 |
| 📜 **剧本流水线** | txt 标记式剧本（【角色】台词）→ 自动分角色 → 批量生成 → `E01_S02_角色_003.wav` 规范命名 + manifest 账本（成本/引擎/溯源） |
| 💰 **成本路由** | 逐句自动选引擎：本地(0元) → edge-tts(0元) → MiniMax(按量)；质量门槛（如 edge-tts 降调过深自动升级）+ 每集预算上限 |
| 🔒 **合规门禁** | 音色溯源（"这声音哪来的"可追溯）+ 克隆门禁（仅自有授权声音）+ 敏感词过滤 |
| 🖥️ **三件套** | Python 库 + CLI（`voicecast.bat`）+ Gradio Web（试听对比/角色表管理/批量运行） |

## 🚀 快速开始

```bash
# 1. 安装依赖（Python 3.11+）
uv venv .venv --python 3.11
uv pip install --python .venv -e . -i https://pypi.tuna.tsinghua.edu.cn/simple

# 2. 看引擎状态（零配置即可用）
voicecast engines

# 3. 音色设计：描述 → 候选试听
voicecast design "反派中年男声，低沉阴险"

# 4. 剧本一键批量配音
voicecast run examples/script_demo.txt examples/cast_demo.yaml --out-dir outputs/demo

# 5. Web 界面（设计器试听 + 角色表管理）
web.bat   # 打开 http://127.0.0.1:7860
```

> Windows 下直接用仓库根的 `voicecast.bat` / `web.bat`，无需安装。

### 本地引擎（完全离线，可选）

```bash
bash scripts/setup_local_engine.sh   # torch(cu128) + F5-TTS + 模型下载（hf-mirror）
voicecast route male_elderly         # 查看路由结果
```

## 🧩 架构

```
voicecast/
├── core/        数据模型（VoiceProfile / Role / Cast / Script / Project）
├── design/      ★音色设计器（规则翻译器 + LLM增强 + 滑杆 + 种子音色库）
├── engines/     ★引擎适配层（base 抽象：local / edge_tts / minimax）
├── pipeline/    剧本解析 → 成本路由 → 批量调度 → 归档
├── compliance/  溯源 + 克隆门禁 + 敏感词
├── cli/ + web/  typer CLI + Gradio Web
└── recipes/     音色配方库（CC BY-NC 数据资产）
```

**成本路由一句话**：音色归属决定"能不能选"（克隆音色焊死在宿主引擎），成本路由决定"选哪个"（本地→edge-tts→MiniMax），质量门槛和预算决定"敢不敢选便宜的"。本地引擎装得越多，自动省得越多。

## 📄 数据格式（预留格式）

```yaml
# cast.yaml —— 一部剧 = 一份文件
cast:
  lin_feng:
    name: 林锋
    voice: male_young_sunny   # 引用 recipes/voice_profiles.yaml 的配方 id
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
| **F5-TTS（本地）** | 0 元 | 显卡 + 模型下载 | 完全离线，零样本克隆，默认主干 |
| **edge-tts** | 0 元 | 联网 | 零 key 免费兜底，8 个中文音色 + 变调配方 |
| **MiniMax** | 按量 | `MINIMAX_API_KEY` | 可选插件，无 key 自动跳过；支持声音克隆 |

## ⚖️ 合规与伦理

- **音色溯源**：每个配方记录来源（原创/参考/克隆/合成）与授权状态，输出元数据同步携带
- **克隆门禁**：仅允许克隆自有授权声音，禁止克隆名人/他人声音（详见 `compliance/clone_gate.py`）
- **内容审核**：生成前敏感词过滤，词库可插拔（`VOICECAST_SENSITIVE_FILE`）
- 本项目不用于、也不允许用于任何侵权、诈骗、伪造场景

## 📜 许可

- **代码**：MIT License
- **recipes/ 音色配方库与种子音色**：CC BY-NC 4.0（数据资产，保留非商用保护）

## 🗺️ 路线图

- ✅ 一期：设计器（描述+滑杆）/ 角色表 / 剧本流水线 / 成本路由 / 合规门禁 / CLI / Web
- 🔜 二期：GPT-SoVITS 增强克隆、音色混合插值、SRT/Excel 导入、自动混音
