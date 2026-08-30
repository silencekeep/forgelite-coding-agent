Git 仓库地址：https://github.com/<请替换为你的账号>/forgelite-coding-agent

运行：Python 3.11+，无需第三方运行依赖。执行 `python -m pip install -e .`；在终端设置 `CODING_AGENT_API_KEY`、`CODING_AGENT_BASE_URL` 和 `CODING_AGENT_MODEL`，再运行 `coding-agent --workspace <目录> --task "你的编程任务"`。密钥只从环境变量读取，未写入仓库。

特色：ForgeLite 是不用任何 agent 框架从零实现的本地编程智能体。模型用 OpenAI 兼容的原生 tool calling；程序自行实现目录、文本搜索、读写、精确替换和命令工具，自行维护多轮消息、解析调用、限制最大回合、处理网络重试与工具报错。CLI 之外还提供仅监听本机的 Web 控制台。腕表式 `low|medium|high` 三档会实际改变规划提示、默认回合数和上下文预算。工作区路径边界、输出截断和危险命令拦截降低误操作风险；浅层目录浏览与重复只读调用反馈减少无效循环。上下文采用“近期对话 + 旧活动摘要”，另以 LRU 工作记忆优先保留最近文件和命令结果的紧凑摘要。

视频演示真实模型从空目录一次性交付完整 Python 待办项目：7 个模型回合内创建实现、测试和 README，首次测试命令失败后自行纠正，最终 5 项测试及手工黑盒验证通过。主项目含不联网测试、无敏感内容审计日志与详细设计说明。
