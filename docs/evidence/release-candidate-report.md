# 纯 Git 快照发布验收

验收日期：2026-08-30（北京时间）

验收提交：`77d49f3`

目的：排除本地 `.gitignore` 产物、editable 残留或未跟踪文件让测试“偶然通过”的可能。

## 方法

1. 使用 `git archive HEAD` 只导出当前提交中受 Git 跟踪的文件；
2. 解压到全新的系统临时目录，不复制原工作区的 `artifacts/`、`deliverables/`、缓存或虚拟环境；
3. 设置 `PYTHONPATH=src`，运行主项目测试；
4. 独立运行 one-shot 生成产物测试；
5. 从该干净快照构建普通 wheel，并检查 Web 静态资源和命令入口是否入包。

## 结果

- ForgeLite 主项目：39 项测试通过，其中包含 NDJSON 流顺序、任务结束前刷新、终止错误记录与浅色静态资源断言；
- one-shot 生成项目：5 项测试通过；
- wheel 构建成功：`local_coding_agent-0.1.0-py3-none-any.whl`，37,159 bytes；
- wheel 中确认包含 `coding_agent/web.py`、浅色 ReAct 工作台的 `index.html`、`console.js`、`console.css` 与 `dist-info/entry_points.txt`。
- Qwen3-TTS 生成脚本可编译，但模型依赖、权重、WAV 和 MP4 均不进入 wheel，也不改变 ForgeLite 的零第三方运行依赖。

这证明公开仓库的 tracked files 足以测试和打包主程序，真实运行时才需要由用户通过环境变量提供模型 API key。视频与最终提交 ZIP 按题目要求是仓库外提交物，因此不参与这项纯 Git 快照验证。
