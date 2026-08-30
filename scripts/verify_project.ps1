# Read-only project acceptance checks. Use -SubmissionReady after replacing the
# repository URL to enforce every upload gate.
param(
    [switch]$SubmissionReady
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    $env:PYTHONPATH = Join-Path $root "src"

    python -m unittest discover -s tests -q
    if ($LASTEXITCODE -ne 0) { throw "Main test suite failed." }

    python -m compileall -q src
    if ($LASTEXITCODE -ne 0) { throw "Source compilation failed." }

    $readme = Get-Content -LiteralPath "README.txt" -Raw -Encoding utf8
    if ($readme.Length -gt 1000) { throw "README.txt exceeds 1000 characters: $($readme.Length)." }
    if ($SubmissionReady -and $readme -match '<请替换为你的账号>') {
        throw "README.txt still contains the repository URL placeholder."
    }

    $secretMatches = git grep -n -E 'sk-[A-Za-z0-9_-]{12,}' -- . 2>$null
    if ($LASTEXITCODE -eq 0) { throw "A possible API key exists in a tracked file." }
    if ($LASTEXITCODE -ne 1) { throw "Tracked-file credential scan could not run." }

    $audit = Get-Content -LiteralPath "docs\evidence\one-shot-audit.jsonl" -Encoding utf8 |
        ForEach-Object { $_ | ConvertFrom-Json }
    if ($audit[-1].event -ne "run_finished" -or $audit[-1].outcome -ne "model_final") {
        throw "One-shot evidence does not end in model_final."
    }

    $video = Join-Path $root "deliverables\ForgeLite-demo.mp4"
    if (Test-Path -LiteralPath $video) {
        $ffprobe = (Get-Command ffprobe -ErrorAction Stop).Source
        $metadata = & $ffprobe -v error -show_entries format=duration,size -of default=noprint_wrappers=1 $video
        $duration = [double](($metadata | Select-String '^duration=').ToString().Split('=')[1])
        $size = [int64](($metadata | Select-String '^size=').ToString().Split('=')[1])
        if ($duration -gt 120) { throw "Video exceeds 120 seconds: $duration." }
        if ($size -gt 200MB) { throw "Video exceeds 200 MB: $size bytes." }
    }
    elseif ($SubmissionReady) {
        throw "Submission video is missing."
    }

    Write-Host "PASS: 15 tests, compilation, README, credential scan, one-shot evidence, and video gates."
    if (-not $SubmissionReady -and $readme -match '<请替换为你的账号>') {
        Write-Host "NOTE: replace the repository URL, then rerun with -SubmissionReady."
    }
}
finally {
    Pop-Location
}
