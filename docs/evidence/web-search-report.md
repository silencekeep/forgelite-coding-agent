# Web 控制台只读搜索验收

验收日期：2026-08-30（北京时间）

环境：本地 loopback OpenAI 兼容网关，模型 `openai/gpt-oss-120b`，Medium profile。API key 仅作为进程环境变量提供，未保存到报告或仓库。

## 任务与结果

通过 `POST /api/run` 要求 agent 只读定位 `TOOL_SCHEMAS`，然后回答模型可见工具的数量和名称；明确禁止修改文件和执行命令。

最终成功路径共 3 个模型回合：

1. `search_text` 成功定位定义；
2. `read_file` 读取必要源码；
3. `model_final` 正确回答共有 6 个工具：`list_files`、`search_text`、`read_file`、`write_file`、`replace_in_file`、`run_command`。

模型还正确说明，本地执行器接受的 `search` 只是兼容别名，没有加入发给模型的 `TOOL_SCHEMAS`，所以不应计为第七个模型可见工具。全过程没有写工具或命令工具事件。

## 由真实测试驱动的改进

首次大仓库只读测试中，模型反复递归 `list_files`，直到达到回合上限。针对这个失败，目录列表改为默认浅层、递归必须显式请求，并增加本地有限文本搜索和连续重复只读调用反馈。另一次测试发现兼容模型给搜索传 `path=""`；参数归一化将其安全映射到工作区根目录后，上述验收从 4 回合降为 3 回合。

这份报告是结果摘要，不替代 one-shot 交付证据。完整项目生成及失败后自纠正的结构化轨迹见 `one-shot-audit.jsonl` 和 `one-shot-report.md`。
