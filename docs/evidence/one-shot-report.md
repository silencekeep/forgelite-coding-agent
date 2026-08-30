# 真实模型 one-shot 验收记录

时间：2026-08-30（北京时间）  
模型：`openai/gpt-oss-120b`，OpenAI 兼容原生 tool calling  
模式：`--thinking high --max-steps 18`  
起始状态：空工作区

## 任务

一次性创建纯标准库 Python 待办应用：`add/list/done` 命令、`todos.json` 持久化、非法参数和不存在 ID 的非零退出码、完整 unittest 与 README，并自行运行测试。

## 实际轨迹

Agent 在 7 个模型回合内完成：列目录；依次写入 `todo_app.py`、`tests/test_todo_app.py`、`README.md`；第一次测试命令失败后读取工具错误并自动更正；第二次测试命令成功；模型给出最终结论。完整无内容审计见 `one-shot-audit.jsonl`。

## 独立复验

- 生成文件：3 个，要求全部满足。
- `python -m unittest discover -s tests -v`：5/5 通过。
- 手工黑盒测试：添加、列出、完成均成功；`done 99` 输出明确错误且退出码为 1。
- `python -m py_compile todo_app.py`：通过。

审计日志不含用户任务正文、模型文本、文件内容、命令输出或 API key；它只证明操作顺序和结果状态。为使公开仓库的评委能够复核，`one-shot-output/` 保存了这次运行三个文本产物的逐字节快照与 SHA-256 清单；验收脚本会验证哈希并再次运行其中 5 项测试。该目录明确是生成证据，不参与 ForgeLite 主程序。
