# 纯 Git 快照发布验收

验收日期：2026-08-30（北京时间）  
验收提交：`18ecff7`  
目的：排除本地 `.gitignore` 产物、editable 残留或未跟踪文件让测试“偶然通过”的可能。

## 方法

1. 使用 `git archive HEAD` 只导出当前提交中受 Git 跟踪的文件；
2. 解压到全新的系统临时目录，不复制原工作区的 `artifacts/`、`deliverables/`、缓存或虚拟环境；
3. 设置 `PYTHONPATH=src`，运行主项目测试；
4. 独立运行 one-shot 生成产物测试；
5. 从该干净快照构建普通 wheel，并检查 Web 静态资源和命令入口是否入包。

## 结果

- ForgeLite 主项目：36 项测试通过；
- one-shot 生成项目：5 项测试通过；
- wheel 构建成功：`local_coding_agent-0.1.0-py3-none-any.whl`，31,307 bytes；
- wheel 中确认包含 `coding_agent/web.py`、`web_assets/index.html`、`web_assets/console.css` 与 `dist-info/entry_points.txt`。

这证明公开仓库的 tracked files 足以测试和打包主程序，真实运行时才需要由用户通过环境变量提供模型 API key。视频与最终提交 ZIP 按题目要求是仓库外提交物，因此不参与这项纯 Git 快照验证。
