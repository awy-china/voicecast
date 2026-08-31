# 发布清单（GitHub 推送前逐项核对）

> ⛔ **门禁**：仅在用户明确允许后，才创建远程仓库并 push。此清单是发布前的自查。

## 必核项

- [x] 仓库名：`voicecast`（声演工作室）
- [x] README.md：定位/快速开始/架构/格式/许可/合规 齐全
- [x] LICENSE（MIT，代码）
- [x] recipes/LICENSE（CC BY-NC 4.0，配方数据）
- [x] CI：.github/workflows/ci.yml（pytest + ffmpeg）
- [x] 示例：examples/script_demo.txt + cast_demo.yaml（原创演示数据）
- [x] 无密钥泄露：.env / API key 全部走环境变量，.gitignore 已挡
- [x] 无版权风险：示例剧本为原创；种子音色为 edge-tts 合成
- [x] 合规声明：README 已含克隆门禁/溯源/审核说明
- [x] 测试：36 项全过（本地）；CI 跑通后绿标

## 推送命令（等用户允许后执行）

```bash
git remote add origin https://github.com/<用户名>/voicecast.git
git push -u origin main
```

## 可选增强（发布前可补）

- [ ] 仓库 Topics：ai-tts, voice-cloning, tts, dubbing, gradio
- [ ] 首页截图/试听 demo 链接（可放 outputs/ 示例音频到 README）
- [ ] `.gitattributes`（防止 wav/二进制被当文本）
