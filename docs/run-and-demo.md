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

## 2. 推荐的视频演示任务

`demo_target` 是一个刻意带 bug 的独立 Python 项目。开始录屏前，可先确认它失败：

```powershell
Push-Location .\demo_target
python -m unittest discover -s tests -v
Pop-Location
```

然后只录制下面一条命令以及后续终端输出：

```powershell
coding-agent --workspace .\demo_target --thinking high --max-steps 12 --task "修复这个项目的统计函数。不要修改测试；先阅读实现与测试，定位失败原因，进行最小修改，然后运行全部测试验证。最后简洁说明改了什么。"
```

如果模型已经改完，可以用 `git diff -- demo_target` 或 `Get-Content .\demo_target\text_stats.py` 展示最终代码，再运行一次测试作为收尾。为保证下次能重录，恢复演示夹时使用 `git restore demo_target`；这只会恢复仓库内的演示文件，执行前先确认没有需要保留的演示改动。

## 3. 两分钟剪辑建议

| 时长 | 画面与讲解 |
| --- | --- |
| 0–12 秒 | 标题：ForgeLite，从零实现的本地编程智能体；展示项目树。 |
| 12–24 秒 | 快速显示失败测试，说明任务是修复真实 bug，测试不可修改。 |
| 24–78 秒 | 加速播放 agent 的 `list_files`、`read_file`、`replace_in_file`、`run_command` 输出。指出每个工具都由本地 Python 实现。 |
| 78–100 秒 | 展示通过的三项测试和改动 diff。 |
| 100–120 秒 | 讲架构：模型只负责规划，控制循环、工具执行、上下文压缩、LRU 和错误处理全部在本地。 |

用 OBS、系统录屏或任意剪辑软件导出 MP4；建议 1080p/30fps、H.264，检查文件小于 200 MB。视频中不要显示 API key、环境变量值、浏览器密码管理器或用户目录中的敏感文件。

录制时可先用浏览器打开 `docs/thinking-indicator-demo.html`，停留两秒展示 Medium/High 选择；随后在终端使用相同的 `--thinking high` 参数。三档不是供应商接口的装饰字段：它会改变本地提示策略和默认资源预算。
