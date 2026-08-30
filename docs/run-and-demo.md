# 运行与两分钟视频录制

## 1. 首次运行

在项目根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
$env:CODING_AGENT_API_KEY = "你的密钥"
$env:CODING_AGENT_BASE_URL = "http://127.0.0.1:13000/v1"
$env:CODING_AGENT_MODEL = "openai/gpt-oss-120b"
```

上面是当前环境已经验证过的 OpenAI 兼容基址和模型名。`CODING_AGENT_API_KEY` 必须由你在当前终端填写，绝不能录进视频。可以在录制前关闭终端历史回显，或先在系统环境变量中设置后重开终端。

运行项目自身测试：

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

腕表式思考强度选择器已接入真实 agent，而非独立素材。可选 Web 控制台的启动方式为：

```powershell
coding-agent-web --workspace .\demo_target
```

它只监听 `127.0.0.1`，启动时固定工作区，并拒绝同一工作区的并发任务。浏览器时间线只显示事件名、工具名、成败和长度等审计字段，不展示 prompt、文件内容或密钥。

## 2. 推荐的视频演示任务

最能证明“一次性完整交付”的录屏方式是运行：

```powershell
.\scripts\run_one_shot_demo.ps1
```

脚本每次创建新的空工作区，让真实模型交付带实现、测试和 README 的命令行待办项目，然后在模型结束后独立再跑一次测试。它不会打印或保存 API key。本项目已用该流程完成真实验收：7 个模型回合、生成项目 5/5 测试通过；证据见 `docs/evidence/one-shot-report.md`。

下面的 bug 修复任务可作为更短的备用录屏：

`demo_target` 是一个刻意带 bug 的独立 Python 项目。开始录屏前，可先确认它失败：

```powershell
Push-Location .\demo_target
python -m unittest discover -s tests -v
Pop-Location
```

然后只录制下面一条命令以及后续终端输出：

```powershell
coding-agent --workspace .\demo_target --thinking high --max-steps 12 --audit-log .\run-audit.jsonl --task "修复这个项目的统计函数。不要修改测试；先阅读实现与测试，定位失败原因，进行最小修改，然后运行全部测试验证。最后简洁说明改了什么。"
```

如果模型已经改完，可以用 `git diff -- demo_target` 或 `Get-Content .\demo_target\text_stats.py` 展示最终代码，再运行一次测试作为收尾。为保证下次能重录，恢复演示夹时使用 `git restore demo_target`；这只会恢复仓库内的演示文件，执行前先确认没有需要保留的演示改动。

`run-audit.jsonl` 会记录每一轮请求、工具名、成功状态、输出长度和结束原因。它特意不记录用户 prompt、模型文本、文件内容、命令输出或 API key，适合在答辩中展示“模型并没有直接操作机器，所有动作都经过本地工具层”。

## 3. 两分钟剪辑建议

| 时长 | 画面与讲解 |
| --- | --- |
| 0–12 秒 | 标题：ForgeLite，从零实现的本地编程智能体；展示项目树。 |
| 12–24 秒 | 展示空工作区和 one-shot 任务要求。 |
| 24–78 秒 | 加速播放 agent 的 `list_files`、三次 `write_file`、失败后自纠正的两次 `run_command`。 |
| 78–100 秒 | 展示生成的三个文件、5/5 测试和一次黑盒 CLI 操作。 |
| 100–120 秒 | 讲架构：模型只负责规划，控制循环、工具执行、上下文压缩、LRU 和错误处理全部在本地。 |

用 OBS、系统录屏或任意剪辑软件导出 MP4；建议 1080p/30fps、H.264，检查文件小于 200 MB。视频中不要显示 API key、环境变量值、浏览器密码管理器或用户目录中的敏感文件。

录制时可先启动 `coding-agent-web`，展示腕表菜单并选择 Medium/High；随后提交只读分析任务，或在终端使用相同的 `--thinking high` 参数执行 one-shot。三档不是供应商接口的装饰字段：Web 和 CLI 都会把它映射到相同的本地提示策略与默认资源预算。若只想离线预览组件，也可打开 `docs/thinking-indicator-demo.html`。

## 4. 可复现 MP4 底片

项目已提供不含密钥的 112 秒、1080p/H.264 视频底片。它以字幕呈现真实任务、工具循环、测试证据与设计讲解；生成命令为：

```powershell
.\video_assets\render_demo_video.ps1
```

会生成 `deliverables/ForgeLite-demo.mp4`，通常只有数 MB，远小于 200 MB 上限。脚本用 FFmpeg 生成字幕场景，让本机 Edge 无联网打开仓库内 HTML、截取 Web 控制台画面，再用 Windows 已安装的中文语音朗读 `video_assets/narration.md` 并合成 AAC 旁白；总时长仍为 112 秒。提交前建议用你自己的录音替换合成旁白，这样现场介绍更自然。若网关可用，也可在 24–78 秒处插入本机终端的实时 agent 录屏，更直观地证明 tool call 是实时发生的。无论采用何种剪辑，都不得显示密钥。
