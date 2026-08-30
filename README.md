# ForgeLite：从零实现的本地编程智能体

ForgeLite 是一个仅用 Python 标准库实现的 coding agent。它通过 OpenAI 兼容的 `chat/completions` 接口调用支持原生 tool calling 的大语言模型，并在本地自己完成工具注册、调用循环、上下文压缩、错误恢复和终止判断。

它没有使用 LangChain、LlamaIndex、OpenAI Agents SDK 或任何 agent 框架/SDK，也没有使用云端代码执行、文件管理工具。

## 能做什么

- 在指定工作区内列目录、搜索文本、读文件、写文件、精确替换文本、执行开发命令
- 先查看代码，再修改，再运行测试，并基于真实命令输出汇报结果
- 单次任务与持续多轮对话两种模式
- 统一限制在 `--workspace` 目录；阻止路径穿越和少量明显危险的命令
- 本地历史压缩与 LRU 工作记忆：近期访问的文件/命令结果优先保留为短摘要
- Low / Medium / High 思考强度：实际改变本地规划提示、默认回合数和上下文预算
- 可选无密钥 JSONL 审计日志：记录回合、工具与成功状态，不保存 prompts、文件内容、命令输出或凭据
- API 的超时、429/5xx 重试、工具参数错误和模型非标准参数名兼容处理
- 浅层目录浏览、有限文本搜索和重复只读调用反馈，减少大仓库上下文浪费与无效循环

## 运行

要求 Python 3.11+。本项目没有第三方运行依赖。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .

$env:CODING_AGENT_API_KEY = "在当前终端填写你的密钥"
$env:CODING_AGENT_BASE_URL = "http://127.0.0.1:13000/v1"  # 或其他 OpenAI 兼容网关
$env:CODING_AGENT_MODEL = "openai/gpt-oss-120b"

coding-agent --workspace .\demo_target --thinking high --task "修复这个项目的统计函数。不要修改测试；先阅读代码和测试，再运行测试验证。"
```

录制或答辩时可加 `--audit-log run-audit.jsonl`，得到结构化的本地操作时间线。

也可以启动交互模式：

```powershell
coding-agent --workspace .\demo_target
```

可选的本地 Web 控制台会把腕表式 Low/Medium/High 选择器接到同一套真实 agent 配置，并展示无敏感内容工具时间线：

```powershell
coding-agent-web --workspace .\demo_target
```

控制台只监听 `127.0.0.1`，工作区在启动时固定；同一工作区同时只运行一个任务。

密钥只从环境变量读取；请不要把它写进仓库、`.env`、README 或录屏。更多变量与录屏流程见 [docs/run-and-demo.md](docs/run-and-demo.md)。

当 `CODING_AGENT_BASE_URL` 是 `localhost`、`127.0.0.1` 或 `::1` 时，ForgeLite 会自动绕过系统 HTTP 代理直连本地网关；远程 API 保持系统网络配置。

`--thinking low|medium|high` 不是表面标签：Low 默认 8 回合/24k 字符上下文，Medium 为 16/48k，High 为 28/80k，且三档会向模型提供不同的本地规划策略。提供的腕表式组件已改造成三档选择器，可在浏览器打开 [docs/thinking-indicator-demo.html](docs/thinking-indicator-demo.html) 预览。

## 项目结构

```text
src/coding_agent/
  agent.py        # 控制循环与模型输出解析
  client.py       # 手写 OpenAI 兼容 HTTP 客户端与重试
  tools.py        # 本地工具 schema、路径约束和执行
  history.py      # 对话历史压缩
  lru_memory.py   # 最近使用工作记忆
  thinking.py     # Low / Medium / High 配置档
  web.py          # 仅监听本机的可选 Web 控制台
  web_assets/     # 腕表选择器与控制台静态资源
tests/            # 不联网的单元测试
demo_target/      # 视频中使用的真实小型修复任务
docs/             # 设计、答辩和录屏材料
ui_assets/        # 可复用的腕表式思考强度指示器
```

## 验证

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
python -m compileall -q src
```

测试集不仅覆盖单个工具，还包含 Web 请求边界和“空工作区 → 创建实现、测试和 README → 执行测试 → 收到最终结论”的完整控制循环测试，因此无需 API key 也能复现 agent 的本地执行链路。

完整设计取舍、运行流程和面试准备见 [docs/design.md](docs/design.md) 与 [docs/interview-qa.md](docs/interview-qa.md)。

真实模型从空工作区一次性生成待办项目的 7 回合验收记录见 [docs/evidence/one-shot-report.md](docs/evidence/one-shot-report.md)，对应结构化日志不含 prompt、文件内容或凭据。

Web 控制台通过 `search_text` 定点分析当前仓库的 3 回合真实验收见 [docs/evidence/web-search-report.md](docs/evidence/web-search-report.md)。

可复现的两分钟内 MP4 底片和配音稿在 [video_assets](video_assets)；运行 `./video_assets/render_demo_video.ps1` 会生成不含密钥的 1080p 演示视频。

账号与姓名相关的最终提交步骤见 [docs/submission-checklist.md](docs/submission-checklist.md)；`scripts/prepare_submission.ps1` 会检查 README、视频并生成姓名命名的 ZIP。

运行 `./scripts/verify_project.ps1` 可一次检查测试、编译、README 长度、tracked-file 密钥扫描、真实 one-shot 证据和视频门槛；逐项要求映射见 [docs/requirements-traceability.md](docs/requirements-traceability.md)。
