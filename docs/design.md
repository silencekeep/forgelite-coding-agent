# ForgeLite 设计说明

## 一句话架构

模型负责“决定下一步”，本地程序负责“能做什么、实际做了什么、何时停下”。这条边界是本项目的核心：云端只有一个普通的 OpenAI 兼容文本接口，本机没有把文件或终端控制权交给任何 API 服务。

```text
用户任务
   ↓
CodingAgent ── 受限消息历史 + LRU 摘要 ──→ ChatCompletionsClient ──→ 模型
   ↑                                                              ↓ tool_calls / 最终文本
WorkspaceTools ←── JSON 参数解析、校验和本地执行 ── tool result ──┘
```

## 核心控制循环

`CodingAgent.run_task()` 将用户任务追加到消息列表，然后至多重复 `max_steps` 次：

1. 先压缩历史并加入 LRU 工作记忆；
2. 通过 `urllib.request` 请求 `/chat/completions`，同时发送手写的 JSON Schema 工具定义；
3. 将模型的 assistant message 原样保留到历史；
4. 如果其中有 `tool_calls`，逐个解析其 JSON arguments，本地执行，再把 `{ok, output}` 作为 `role=tool` 消息写回历史；
5. 如果没有 tool call 且有文本，文本就是正常终止结果；达到回合上限则抛出专用失败，CLI 返回非零退出码、Web 返回 422，并提示检查部分改动。

这避免了两种常见问题：把“模型说已经改好”误认为成功，以及因模型不断调用工具而无限循环。

## 工具与安全边界

六个工具为 `list_files`、`search_text`、`read_file`、`write_file`、`replace_in_file` 和 `run_command`。目录默认只列当前层，模型需要时再显式递归；文本搜索按路径、文件 glob 和结果数限制，避免为了定位一个符号而读取整棵目录。每个工具都带模型可见 schema，也在 Python 本地再次校验。所有实际读取或写入的文件路径经过 `Path.resolve()`，再以 `relative_to(workspace)` 检查，故 `../`、绝对路径和指向工作区外的文件链接不能绕过边界。

读取文件有 200 KB 文件上限和 30k 字符单次输出上限，超限时提示模型用行号范围继续，避免一项观察吞掉整个上下文。写文件通过 `NamedTemporaryFile` 在目标目录独占创建随机临时文件，再用 `os.replace` 原子替换；失败时清理临时项，避免固定临时名被预置链接利用。精确替换要求旧文本恰好出现一次，防止模型在过时代码上误改多处。命令固定以 workspace 为 CWD，设超时、合并并截断输出，并拒绝若干显而易见的递归删除、格式化、关机命令。它不是操作系统级安全沙箱，因此 README 仍建议选用专用工作目录。

## 上下文与 LRU Compact

只保存全部历史会让 token 成本和干扰不断增长。`history.py` 保留 system prompt 与最近几轮，把更早的 user、assistant、tool 记录变成带角色的短活动摘要，并为摘要预留字数，确保一条超长工具输出不会吞掉所有上下文。压缩的基本单位不是单条消息，而是“一条 assistant tool_calls 消息及其全部 role=tool 结果”；这样不会留下 API 不接受的孤立工具结果。

仅按时间也不够：修复任务通常会反复关注最近读过的 2–5 个文件。因此 `lru_memory.py` 用 `OrderedDict` 实现固定容量 LRU。每次成功读/写/编辑文件或运行命令，按文件路径或命令作为 key 更新；重复访问会移到队尾，容量满时弹出队首。下一次模型请求前，它按“最新优先、输出时按时间正序”的方式渲染在预算内的紧凑观察。该记忆明确标为非真相，prompt 要求编辑前重新读文件，避免陈旧缓存导致误改。

## Low / Medium / High 思考强度

`--thinking` 由 `thinking.py` 显式映射到三个本地 profile，而不是依赖供应商专有的“推理强度”字段：Low 为 8 回合、24k 字符上下文，强调最小必要检查；Medium 为 16 回合、48k，强调平衡；High 为 28 回合、80k，要求检查相邻代码、测试和替代原因后再验证。用户显式提供的 `--max-steps`、`CODING_AGENT_MAX_STEPS` 或上下文变量仍优先，因而可以控制成本。`ui_assets/` 中的腕表指示器是相同三档配置的可复用视觉素材。

## 可靠性设计

- HTTP 层：对网络错误、超时、429 和 5xx 指数退避重试；普通 4xx 立即报出配置或请求错误。
- 模型输出：检查 `choices[0].message`、每个 function call 及 arguments 类型；坏 JSON 作为工具错误返回给模型修正。对缺失 call ID、对象形式 arguments 这两种可安全解释的兼容方言，会先规范成标准历史形状。
- 循环恢复：连续、完全相同且中间没有工作区变更的只读调用会返回可操作的工具错误，提示模型缩小路径或改用搜索；最大回合数仍是最终硬边界。
- 输入边界：任务最多 16,000 字符，确保 Low 档首次请求也不会把当前用户任务压缩成几行旧活动摘要。
- 兼容性：实际测试发现某些兼容模型会传 `path=""`、`max_entries=1000`、`line_start/line_end`，入口将这些无害方言归一化为本地工具参数，同时不放宽路径边界。
- 可观察性：终端显示每个模型回合、工具名、经脱敏缩短的参数和首行结果；写入内容不会直接回显。
- 审计轨迹：可选 `--audit-log` 逐行记录 UTC 时间、模型回合、工具名、参数键、成功状态和结束原因；它不存 prompt、模型回答、文件内容、命令输出或凭据。因此它既能为视频提供时间线，也不会把敏感内容写入仓库。

## 如何验证“能一次性完成项目”

`tests/test_memory_and_agent.py` 的 `test_one_run_creates_and_verifies_a_small_project` 从全新临时目录开始。它使用 OpenAI 原生 tool-call 格式的脚本化模型响应，要求 agent 在连续三轮内写入 `calculator.py`、单元测试和 README，接着调用 `python -m unittest`，最后核验退出码与文件内容。此测试不声称替代真实模型质量；它精确验证了本项目负责的部分——多工具编排、本地写入、命令执行、结果回传和正常终止——可从零生成并验证一个项目。

## 为什么不使用框架

题目要求的重要逻辑必须自己实现。本项目的模型 client、工具 schema、工具运行器、会话消息列表、历史压缩、LRU、循环和停止条件都在 `src/coding_agent` 内逐个可读；唯一网络依赖是 Python 标准库对模型厂商兼容 REST API 的普通 HTTP 请求。
