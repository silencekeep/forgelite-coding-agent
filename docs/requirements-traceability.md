# 题目要求与验收证据

这份表用于提交前自查和面试定位。它把题目要求映射到可检查的实现与证据，而不是以功能描述代替证明。

| 题目要求 | 实现位置 | 验收证据 | 状态 |
| --- | --- | --- | --- |
| 与大语言模型交互 | `client.py` 手写 `/chat/completions` HTTP 请求，携带原生 tools schema | 真实 `openai/gpt-oss-120b` one-shot 审计 | 已验证 |
| 自主读写文件、执行命令 | `tools.py` 的六个本地工具 | 工具单测；真实轨迹包含 list/write/run | 已验证 |
| 不使用 agent 框架/SDK | `pyproject.toml` 无运行依赖；模型客户端仅用标准库 `urllib` | 纯 Git 快照测试与 wheel 构建报告 | 已验证 |
| 不依赖服务端文件/代码工具 | 所有工具由 `WorkspaceTools` 在本机执行 | 源码审查；审计轨迹 | 已验证 |
| 自行维护对话历史 | `CodingAgent.messages` 与 `history.py` | 历史压缩测试 | 已验证 |
| 自行实现上下文管理 | 历史摘要 + `LruWorkingMemory` | LRU 淘汰、预算与渲染测试 | 已验证 |
| 自行解析模型输出 | `_assistant_message`、JSON arguments 解析与方言归一化 | 模型参数别名与坏参数测试 | 已验证 |
| 循环与终止条件 | `run_task` 显式模型—工具循环；final/空响应/专用步数异常 | 脚本化端到端测试；CLI/Web 非成功语义；真实 7 回合终止 | 已验证 |
| 错误处理 | 429/5xx 重试、HTTP 4xx 快速失败、工具错误回传、命令超时 | 错误路径单测；真实轨迹 step 5 失败、step 6 自纠正 | 已验证 |
| API key 不入库 | `AgentConfig` 只读环境变量；`.gitignore` 排除 `.env*` | tracked-files 密钥模式扫描 | 已验证 |
| 完整一次性交付项目 | High 模式 + 本地工具循环 | 审计轨迹；带 SHA-256 的生成产物快照；5/5 + 黑盒验证 | 已验证 |
| Low/Medium/High 可交互调节 | 三档 profile + loopback Web 腕表选择器 | profile 单测、Web 传参单测、`web-search-report.md` | 已验证 |
| ReAct 工作过程可见 | `/api/run-stream` 手写 NDJSON；浅色 UI 增量渲染 Reason/Act/Observe | 流顺序、HTTP content type、终止错误记录测试；视频关键帧 | 已验证 |
| README.txt ≤1000 字 | 根目录 `README.txt` | 验收脚本动态检查字符数 | 已验证 |
| MP4 ≤2分钟、≤200MB | 可复现 FFmpeg 渲染脚本 | 112 秒、2,439,689 字节、工作过程关键帧检查 | 已验证 |
| 公开 Git 仓库与真实地址 | README 与 `origin` 均指向 `silencekeep/forgelite-coding-agent` | 匿名 HTTP 200；远端 `main` SHA 与本地 `HEAD` 一致 | 已验证 |
| 姓名命名的最终 ZIP | `prepare_submission.ps1` | 仅含根目录 README/视频；名称、哈希、时长和大小复核 | 已验证 |

## 真实 one-shot 证据边界

`evidence/one-shot-audit.jsonl` 证明事件顺序、工具名、成功状态和终止原因；它有意不保存 prompt 和命令输出。生成项目的 5 项测试与手工黑盒结果记录在 `one-shot-report.md`，三个文本产物及哈希保存在 `one-shot-output/`。轨迹、逐字节快照与独立复验共同证明“发生了什么”和“产物是否工作”，同时避免把敏感内容写入仓库。

## 已知边界

- 命令工具是带超时和危险模式拦截的 shell，不是操作系统级沙箱；生产使用应放入容器或低权限账户。
- 字符预算是可解释的近似上下文预算，不是供应商 tokenizer 的精确 token 计数。
- LRU 摘要只是工作记忆，编辑前仍要求重新读取文件，避免陈旧缓存成为事实来源。
- 模型质量影响规划，但文件边界、工具执行、终止和证据验证由本地程序负责。
- Web 控制台只监听 loopback，且同一工作区拒绝并发任务；它是可选界面，CLI 是核心执行入口。
