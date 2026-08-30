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

    $evidenceRoot = Join-Path $root "docs\evidence\one-shot-output"
    python -m unittest discover -s (Join-Path $evidenceRoot "tests") -q
    if ($LASTEXITCODE -ne 0) { throw "Committed one-shot output tests failed." }

    $manifest = Get-Content -LiteralPath (Join-Path $evidenceRoot "manifest.json") -Raw -Encoding utf8 |
        ConvertFrom-Json
    foreach ($entry in $manifest.files) {
        $evidenceFile = Join-Path $evidenceRoot $entry.path
        $actualHash = (Get-FileHash -LiteralPath $evidenceFile -Algorithm SHA256).Hash
        if ($actualHash -ne $entry.sha256) {
            throw "One-shot evidence hash mismatch: $($entry.path)"
        }
    }

    python -m compileall -q src
    if ($LASTEXITCODE -ne 0) { throw "Source compilation failed." }

    $readme = Get-Content -LiteralPath "README.txt" -Raw -Encoding utf8
    if ($readme.Length -gt 1000) { throw "README.txt exceeds 1000 characters: $($readme.Length)." }
    if ($SubmissionReady -and $readme -match '<请替换为你的账号>') {
        throw "README.txt still contains the repository URL placeholder."
    }
    if ($SubmissionReady) {
        $worktreeState = git status --porcelain
        if ($LASTEXITCODE -ne 0) { throw "Git working-tree status could not be read." }
        if ($worktreeState) { throw "Git working tree is not clean." }

        $branch = git branch --show-current
        if ($LASTEXITCODE -ne 0 -or $branch.Trim() -ne "main") {
            throw "Submission must be made from the local main branch."
        }

        $repositoryMatch = [regex]::Match($readme, 'Git 仓库地址：(https://github\.com/[^/\s]+/[^\s]+)')
        if (-not $repositoryMatch.Success) {
            throw "README.txt does not contain a valid GitHub repository URL."
        }
        $repositoryUrl = $repositoryMatch.Groups[1].Value.TrimEnd('/')
        $originUrl = git remote get-url origin 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $originUrl) {
            throw "Git remote 'origin' is not configured."
        }
        $normalizedOrigin = $originUrl.TrimEnd('/') -replace '\.git$', ''
        if ($normalizedOrigin -ne $repositoryUrl) {
            throw "README repository URL does not match git remote origin."
        }
        try {
            $publicCheck = Invoke-WebRequest -Uri $repositoryUrl -Method Head -MaximumRedirection 3 -TimeoutSec 20
        }
        catch {
            throw "Public repository URL is not anonymously reachable: $repositoryUrl"
        }
        if ($publicCheck.StatusCode -ne 200) {
            throw "Public repository returned HTTP $($publicCheck.StatusCode): $repositoryUrl"
        }

        $localHead = (git rev-parse HEAD).Trim()
        if ($LASTEXITCODE -ne 0 -or -not $localHead) {
            throw "Local HEAD could not be resolved."
        }
        $remoteMainLine = git ls-remote origin refs/heads/main 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $remoteMainLine) {
            throw "Remote main branch could not be resolved."
        }
        $remoteMain = ($remoteMainLine -split '\s+')[0]
        if ($remoteMain -ne $localHead) {
            throw "Remote main is not at local HEAD. Push the complete local history first."
        }
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

    Write-Host "PASS: main/evidence tests, compilation, README, credential scan, one-shot hashes, and video gates."
    if (-not $SubmissionReady -and $readme -match '<请替换为你的账号>') {
        Write-Host "NOTE: replace the repository URL, then rerun with -SubmissionReady."
    }
}
finally {
    Pop-Location
}
