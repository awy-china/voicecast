# VoiceCast 发布清单（RELEASE CHECKLIST）

> 本地 git 全程维护；**推送 GitHub 必须由用户明确确认**。此清单 = 发布前逐项自查。

## 1. 代码健康

- [x] `pytest tests -q` 全绿（45 passed）
- [x] 无真实密钥入库（`.env` 已 gitignore；代码中无硬编码 key）
- [x] git 历史干净（曾发生 18GB tgz 误入库 → filter-branch 重写已清除，仓库 ~200KB）
- [ ] 发布前最终跑一次全量测试 + `git status` 确认工作区干净

## 2. 仓库内容自查

- [x] `README.md` —— 发布级（特性/快速开始/架构/许可齐全）
- [x] `LICENSE` —— MIT
- [x] `pyproject.toml` —— 0.2.0，依赖 = fastapi/uvicorn/edge-tts/httpx…（gradio 已移除）
- [x] `.github/workflows/ci.yml` —— ubuntu + py3.11 + ffmpeg + pytest
- [x] `.gitignore` —— outputs/模型/密钥/缓存全排除
- [x] `examples/` —— script_demo.txt + cast_demo.yaml
- [x] `recipes/samples/ref/LICENSE-DATA.md` —— AISHELL-3 Apache-2.0 授权声明
- [ ] 删除本地调试痕迹：`outputs/`、`.cache_tmp/`、`models/`（均已 ignore，push 不受影响——确认 .git 内无大对象）

## 3. 大文件与数据红线（关键）

- [ ] `git count-objects -vH` 确认 size-pack < 5MB（当前 ~95KB）
- [ ] 确认 wav/mp3/tgz/模型文件无一被 git 跟踪：`git ls-files | grep -E '\.(wav|mp3|tgz|pt|ckpt)$'` 应为空
- [ ] 参考音频文本（*.txt）与配方 yaml 入库是**有意为之**（数据资产文本部分）

## 4. 平台字段

- [ ] `pyproject.toml` 的 `[project.urls]` 占位 URL（yourname/voicecast）→ 替换为真实 GitHub 地址
- [ ] README 中 hf-mirror/国内下载说明：保留（面向国内用户）或补充 GitHub 镜像说明

## 5. 发布步骤（用户批准后执行）

```bash
# 1. 最终自查
pytest tests -q && git status --short && git log --oneline -3

# 2. 建远程 + 推送（等待用户明确说"发"）
git remote add origin https://github.com/<user>/voicecast.git
git push -u origin main

# 3. GitHub 侧
#    - 创建 Release（tag v0.2.0）
#    - Release notes：写清"本地免费/无 key 可跑/GPT-SoVITS 可选加速"三条卖点
#    - 仓库 Settings：确认无 secrets 泄露
```

## 6. 发布后注意事项

- 国内用户拉模型：README 已指向 hf-mirror 镜像（GitHub release 大文件被 RST 已知）
- 配方库 CC BY-NC vs 代码 MIT：README 已分列——若有人 fork 商用代码 OK、配方数据不可商用
- 如有 Issue：优先回应用户关于"模型下载/本地引擎安装"的提问（最高频）
