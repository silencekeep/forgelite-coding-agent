# 提交前 5 分钟清单

- [ ] 在 GitHub 或 Gitee 新建**公开**仓库，并将当前 `main` 的完整提交历史推送上去；不要 squash 或改写已推送历史。
- [ ] 把真实仓库地址替换到根目录 `README.txt` 第一行；确认它与 `origin` 一致、匿名访问返回 HTTP 200、远端 `main` 与本地 `HEAD` 完全一致，且全文仍不超过 1000 字符。
- [ ] 如需要重建视频，先按 `docs/run-and-demo.md` 生成 Qwen3-TTS 旁白，再把 WAV 传给 `./video_assets/render_demo_video.ps1 -NarrationWave ...`。视频为 112 秒、1080p、H.264。
- [ ] 确认视频中没有 API key、终端环境变量值或私人文件路径。
- [ ] 在项目根目录运行：`./scripts/prepare_submission.ps1 -Name "你的姓名"`。
- [ ] 检查 `deliverables/你的姓名.zip`：压缩包内**只**有 `README.txt` 和一个 MP4。
- [ ] 上传该 ZIP 至题目指定表单；确认本地和网页显示的提交时间早于截止时间。

本仓库的现成 MP4 为 `deliverables/ForgeLite-demo.mp4`。它不进 Git，避免把二进制文件和生成素材混进源代码历史。
