# Generates a credential-free 1080p MP4. Run from the repository root.
# It is intentionally source-controlled so the resulting video is reproducible.
param(
    [string]$Output = "deliverables/ForgeLite-demo.mp4"
)

$ErrorActionPreference = "Stop"
$ffmpeg = (Get-Command ffmpeg -ErrorAction Stop).Source
$root = (Get-Location).Path
$assets = Join-Path $root "video_assets"
$target = Join-Path $root $Output
$targetDirectory = Split-Path -Parent $target
New-Item -ItemType Directory -Force -Path $targetDirectory | Out-Null

$temporary = Join-Path $env:TEMP "forgelite-video-scenes"
New-Item -ItemType Directory -Force -Path $temporary | Out-Null
$edgeCandidates = @(
    "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "C:\Program Files\Microsoft\Edge\Application\msedge.exe"
)
$edge = $edgeCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $edge) { throw "Microsoft Edge is required to capture the local Web console scene." }
$webSource = (Resolve-Path (Join-Path $root "src\coding_agent\web_assets\index.html")).Path
$webUri = [System.Uri]::new($webSource).AbsoluteUri + "?preview=open"
$webScreenshot = Join-Path $temporary "web-console.png"
Remove-Item -LiteralPath $webScreenshot -Force -ErrorAction SilentlyContinue
$edgeProfile = Join-Path $temporary "edge-profile"
$edgeArguments = @(
    "--headless",
    "--disable-gpu",
    "--hide-scrollbars",
    "--window-size=1920,1080",
    "--user-data-dir=$edgeProfile",
    "--screenshot=$webScreenshot",
    $webUri
)
$edgeProcess = Start-Process -FilePath $edge -ArgumentList $edgeArguments -PassThru -Wait -WindowStyle Hidden
if ($edgeProcess.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $webScreenshot)) {
    throw "Could not capture the local Web console scene."
}

$font = "C\:/Windows/Fonts/msyh.ttc"
$scenes = @(
    @{ file = "01_title.txt"; duration = 10; background = "0x111827"; size = 50 },
    @{ file = "02_task.txt"; duration = 16; background = "0x1e293b"; size = 30 },
    @{ file = "03_trace.txt"; duration = 25; background = "0x0f172a"; size = 29 },
    @{ file = "04_result.txt"; duration = 15; background = "0x052e16"; size = 33 },
    @{ file = "05_design.txt"; duration = 18; background = "0x312e81"; size = 32 },
    @{ file = "06_features.txt"; duration = 8; background = "0x3f1d2e"; size = 29 },
    @{ image = $webScreenshot; duration = 10 },
    @{ file = "07_close.txt"; duration = 10; background = "0x111827"; size = 35 }
)

$inputArguments = @()
$labels = ""

for ($index = 0; $index -lt $scenes.Count; $index++) {
    $scene = $scenes[$index]
    $sceneFile = Join-Path $temporary ("scene-{0:D2}.mp4" -f $index)
    if ($scene.image) {
        $filter = "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x070b14,fade=t=in:st=0:d=0.5,fade=t=out:st=$($scene.duration - 0.5):d=0.5"
        & $ffmpeg -hide_banner -loglevel error -y -loop 1 -framerate 30 -i $scene.image -t $scene.duration -vf $filter -c:v libx264 -preset medium -crf 23 -pix_fmt yuv420p $sceneFile
        if ($LASTEXITCODE -ne 0) { throw "ffmpeg failed on Web console screenshot" }
    }
    else {
        $text = (Join-Path $assets $scene.file).Replace("\", "/").Replace(":", "\:")
        $filter = "drawtext=fontfile='$font':textfile='$text':fontcolor=white:fontsize=$($scene.size):line_spacing=16:x=90:y=(h-text_h)/2,fade=t=in:st=0:d=0.5,fade=t=out:st=$($scene.duration - 0.5):d=0.5"
        & $ffmpeg -hide_banner -loglevel error -y -f lavfi -i "color=c=$($scene.background):s=1920x1080:r=30:d=$($scene.duration)" -vf $filter -c:v libx264 -preset medium -crf 23 -pix_fmt yuv420p $sceneFile
        if ($LASTEXITCODE -ne 0) { throw "ffmpeg failed on $($scene.file)" }
    }
    $inputArguments += @("-i", $sceneFile)
    $labels += "[$($index):v]"
}

& $ffmpeg -hide_banner -loglevel error -y @inputArguments -filter_complex "$labels`concat=n=$($scenes.Count):v=1:a=0[v]" -map "[v]" -c:v libx264 -preset medium -crf 23 -pix_fmt yuv420p -movflags +faststart $target
if ($LASTEXITCODE -ne 0) { throw "ffmpeg composition failed" }
Get-Item -LiteralPath $target | Select-Object FullName,Length,LastWriteTime
