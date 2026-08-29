Git 仓库地址：https://github.com/<请替换为你的账号>/forgelite-coding-agent

运行：Python 3.11+，无需第三方运行依赖。执行 `python -m pip install -e .`；在终端设置 `CODING_AGENT_API_KEY`、`CODING_AGENT_BASE_URL` 和 `CODING_AGENT_MODEL`，再运行 `coding-agent --workspace <目录> --task "你的编程任务"`。密钥只从环境变量读取，未写入仓库。

特色：ForgeLite 是不用任何 agent 框架从零实现的本地编程智能体。模型用 OpenAI 兼容的原生 tool calling；程序自行定义并执行目录、读写、精确替换和命令工具，自行维护多轮消息、解析工具调用、限制最大回合、处理网络重试与工具报错。支持 `--thinking low|medium|high` 三档思考强度，实际改变规划提示、默认回合数和上下文预算。工作区路径边界、输出截断和危险命令拦截降低误操作风险。上下文采用“近期对话 + 旧活动摘要”，另实现 LRU 工作记忆，优先保留最近访问文件及命令结果的紧凑摘要，减少重复读取和上下文膨胀。

视频演示修复一个含失败测试的真实 Python 小项目：agent 阅读代码和测试，修改实现，运行测试并报告结果。项目含不联网单元测试与详细设计说明。
