# ForgeLite 源码导读与面试演练

这份材料的目标不是让你背答案，而是让你能沿着一次真实请求解释每个设计决定。建议打开源码，按下面顺序亲自走一遍。

## 一、先掌握一句话边界

模型只返回“下一步想做什么”；本地 Python 决定有哪些工具、参数是否合法、实际执行结果是什么，以及循环何时停止。模型没有 Code Interpreter、Files API 或直接终端权限。

```text
用户任务
  ↓
cli.py / web.py               入口、配置、退出语义
  ↓
CodingAgent.run_task()        本地循环和终止条件
  ├─ compact_history()        对话历史预算
  ├─ LruWorkingMemory.render  近期工作集
  └─ client.complete()        普通 HTTP /chat/completions
          ↓ assistant.tool_calls
WorkspaceTools.execute()      参数归一化、边界检查、本地执行
          ↓ role=tool {ok, output}
下一次模型请求，或模型给出 final 文本
```

## 二、按调用路径读源码

### 1. `cli.py`：入口不是 agent 本身

`main()` 只负责解析 `--workspace`、`--thinking`、`--max-steps` 和审计日志，随后构造 `AgentConfig` 与 `CodingAgent`。单次任务成功返回 0；模型耗尽步数会抛出 `AgentStepLimitError`，CLI 返回 1。交互模式复用同一个 agent，因此消息历史跨任务保留。

你要能回答：为什么 Web 和 CLI 不各写一套 agent？因为它们只是输入适配层，共享同一个 `CodingAgent`，才能保证行为和安全边界一致。

### 2. `config.py` 与 `thinking.py`：三档不是装饰

环境变量只在配置层读取，API key 不写文件。Low、Medium、High 分别给出不同 system instruction、默认最大回合数和上下文字符预算：8/24k、16/48k、28/80k。显式参数优先于默认 profile，所以用户仍能控制成本。

这里没有发送供应商专有 `reasoning_effort`：这是为了兼容不同 OpenAI 网关。你可以坦率说明，它调的是 agent 的本地行为预算，而不是声称改变模型内部隐藏推理。

### 3. `agent.py`：核心控制循环

`run_task()` 先拒绝空任务和超过 16,000 字符的任务，再把 user message 加入 `self.messages`。每个模型回合执行四件事：

1. 在字符预算内压缩历史；
2. 插入 LRU 工作记忆；
3. 调用模型并规范化 assistant message；
4. 有 tool calls 就逐个本地执行，没有 tool calls 且有文本就正常结束。

达到最大回合不会返回一段看似成功的字符串，而是显式失败。连续、完全相同的只读调用在没有状态变化时也会被拒绝，提示模型缩小路径或换 `search_text`。

### 4. 一次标准 tool call 长什么样

模型返回：

```json
{
  "role": "assistant",
  "tool_calls": [{
    "id": "call-1",
    "type": "function",
    "function": {
      "name": "read_file",
      "arguments": "{\"path\":\"src/app.py\",\"start_line\":1,\"end_line\":80}"
    }
  }]
}
```

本地执行后追加：

```json
{
  "role": "tool",
  "tool_call_id": "call-1",
  "content": "{\"ok\":true,\"output\":\"...\"}"
}
```

`tool_call_id` 把动作与观察对应起来。兼容网关若省略 ID，ForgeLite 生成本地稳定 ID；若 arguments 直接是对象，则规范成 JSON 文本。真正无法解释的形状会失败，不污染后续历史。

### 5. `tools.py`：模型能力的真正上限

发给模型的六个 schema 是 `list_files`、`search_text`、`read_file`、`write_file`、`replace_in_file`、`run_command`。执行器还有 `search` 兼容别名，但没有把它作为第七个 schema。

文件路径先与 workspace 拼接并 `resolve()`，再用 `relative_to(root)` 验证祖先关系。读取有 200 KB 文件限制与 30k 字符单次输出限制。写入使用目标目录内随机、独占的临时文件，关闭后由 `os.replace` 原子覆盖；精确替换要求旧文本恰好出现一次。

`run_command` 固定 CWD、限制 1–120 秒、截断输出并拦截少量灾难性模式。但它仍是 shell，不是 OS 沙箱；命令完全可能主动访问工作区外资源。答辩中主动讲清这个边界，比声称“绝对安全”更可信。

### 6. `history.py`：为什么不能直接取最后 N 条消息

assistant 的一组 `tool_calls` 与随后所有 `role=tool` 结果必须作为原子组保留。若只按消息条数切片，可能留下孤立 tool result，下一次 API 请求会被拒绝。ForgeLite 先分组，再保留最近完整组；更早消息变成确定性的活动摘要。

### 7. `lru_memory.py`：亲手算一次 LRU Compact

假设容量为 3，依次观察：

```text
read A.py  → [A]
read B.py  → [A, B]
read A.py  → [B, A]       # A 刷新为最近使用
run tests  → [B, A, tests]
read C.py  → [A, tests, C] # 最久未用的 B 被淘汰
```

key 是文件路径或命令，value 是有限长度观察。它解决“近期最可能继续关注什么”；历史压缩解决“很早以前做过什么”。LRU 不是事实缓存，编辑前仍要求重新读取，因为文件可能在缓存后被改动。

### 8. `client.py`：它真的只是模型客户端

客户端用标准库 `urllib` POST 到 `/chat/completions`，携带 messages 和 tools。429/5xx、网络错误会指数退避；普通 4xx 立即失败。本地 `localhost/127.0.0.1/::1` 自动绕过系统代理，远程地址仍使用系统网络配置。

### 9. `audit.py`：可观察性与隐私取舍

JSONL 只记录时间、事件、工具名、参数键、成功状态、输出长度和终止原因。不记录任务正文、模型回答、源码、命令输出或凭据。它足以证明执行顺序，却不能单独证明生成代码正确；因此 one-shot 证据还需要产物快照、SHA-256 和独立测试。

## 三、如何解释“一次性完成项目”的证据链

不要只说“模型生成成功了”，按三层回答：

1. `one-shot-audit.jsonl`：证明 7 回合里真实发生了 list、三次 write、一次失败 command、一次成功 command 和 final；
2. `one-shot-output/`：保存实际生成的实现、测试、README 和逐字节 SHA-256；
3. `verify_project.ps1`：重新运行生成项目 5 项测试，同时验证主项目测试、证据哈希、README 和视频门槛。

首次测试失败反而是关键证据：错误经 `role=tool` 回到模型，模型下一回合改变命令后成功，形成“规划—行动—观察—修正”闭环。

## 四、90 秒口头介绍模板

“ForgeLite 是我不用任何 agent 框架、只用 Python 标准库实现的本地 coding agent。模型通过 OpenAI 兼容原生 tool calling 决定下一步，本地控制循环负责解析、执行和回传六个工具结果，直到模型给出最终文本或达到硬回合上限。所有文件操作限制在指定 workspace，写入采用随机临时文件原子替换；命令有超时、输出限制和危险模式拦截，但我明确不把它宣传成操作系统沙箱。

上下文方面，我把旧对话压成活动摘要，同时用容量固定的 LRU 保存近期文件和命令观察，并保证 assistant tool call 与 tool result 不会被拆散。Low、Medium、High 会实际改变本地规划提示、最大回合和上下文预算。真实模型曾在 7 回合从空目录交付待办项目，第一次测试命令失败后自行修正，5 项测试与黑盒复验通过；审计、生成产物哈希和复验脚本都在仓库里。”

## 五、请亲自完成的五个练习

1. 不看文档，从 `cli.main()` 指到第一次 `WorkspaceTools.execute()`，口述每一层输入输出。
2. 在纸上写出“两次 tool call 后模型 final”的 messages 角色顺序。
3. 用容量 2 手算 `read A → read B → read A → write C` 的 LRU 淘汰结果。
4. 说明 `relative_to(root)` 能保护文件工具，却为什么保护不了任意 shell 命令。
5. 现场运行 `./scripts/verify_project.ps1`，解释主项目全部测试、生成项目 5 项测试、哈希检查分别证明什么，又不能证明什么。

如果这五项能脱稿完成，你对项目的理解已经足以应对大部分追问。
