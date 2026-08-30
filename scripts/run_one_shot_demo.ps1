# Create a fresh workspace and ask the real model to build a complete project.
# Set CODING_AGENT_API_KEY before running; this script never prints or stores it.
param(
    [string]$OutputDirectory = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
if (-not $env:CODING_AGENT_API_KEY) { throw "Set CODING_AGENT_API_KEY in this terminal first." }
if (-not $env:CODING_AGENT_BASE_URL) { $env:CODING_AGENT_BASE_URL = "http://127.0.0.1:13000/v1" }
if (-not $env:CODING_AGENT_MODEL) { $env:CODING_AGENT_MODEL = "openai/gpt-oss-120b" }
$env:PYTHONPATH = Join-Path $root "src"

if (-not $OutputDirectory) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $OutputDirectory = Join-Path $root "recordings\one-shot-$stamp"
}
$session = [System.IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $session) { throw "Output directory already exists: $session" }
New-Item -ItemType Directory -Path $session | Out-Null
$workspace = Join-Path $session "workspace"
New-Item -ItemType Directory -Path $workspace | Out-Null
$audit = Join-Path $session "agent-audit.jsonl"

$task = @"
请在这个空工作区一次性完成一个可运行的小型 Python 项目：实现一个纯标准库的命令行待办事项管理器。创建 todo_app.py，支持 add、list、done 三个子命令并将任务持久化到当前目录的 todos.json；参数错误和找不到任务时返回非零退出码并给出明确错误；创建 tests/test_todo_app.py 覆盖添加、列出、完成和错误 ID；创建 README.md 说明运行和测试方式；不使用第三方依赖。先规划文件，再创建实现和测试，最后务必运行 python -m unittest discover -s tests -v。不要询问，直接完成。
"@

python -m coding_agent --workspace $workspace --thinking high --max-steps 18 --audit-log $audit --task $task
if ($LASTEXITCODE -ne 0) { throw "Agent run failed with exit code $LASTEXITCODE" }

Push-Location $workspace
try {
    python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw "Independent verification failed." }
}
finally {
    Pop-Location
}

Write-Host "Demo workspace: $workspace"
Write-Host "Credential-safe audit: $audit"
