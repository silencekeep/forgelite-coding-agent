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

$font = "C\:/Windows/Fonts/msyh.ttc"
$scenes = @(
    @{ file = "01_title.txt"; duration = 10; background = "0x111827"; size = 50 },
    @{ file = "02_task.txt"; duration = 16; background = "0x1e293b"; size = 30 },
    @{ file = "03_trace.txt"; duration = 25; background = "0x0f172a"; size = 29 },
    @{ file = "04_result.txt"; duration = 15; background = "0x052e16"; size = 33 },
    @{ file = "05_design.txt"; duration = 18; background = "0x312e81"; size = 32 },
    @{ file = "06_features.txt"; duration = 18; background = "0x3f1d2e"; size = 29 },
    @{ file = "07_close.txt"; duration = 10; background = "0x111827"; size = 35 }
)

$temporary = Join-Path $env:TEMP "forgelite-video-scenes"
New-Item -ItemType Directory -Force -Path $temporary | Out-Null
$inputArguments = @()
$labels = ""

for ($index = 0; $index -lt $scenes.Count; $index++) {
    $scene = $scenes[$index]
    $text = (Join-Path $assets $scene.file).Replace("\", "/").Replace(":", "\:")
    $sceneFile = Join-Path $temporary ("scene-{0:D2}.mp4" -f $index)
    $filter = "drawtext=fontfile='$font':textfile='$text':fontcolor=white:fontsize=$($scene.size):line_spacing=16:x=90:y=(h-text_h)/2,fade=t=in:st=0:d=0.5,fade=t=out:st=$($scene.duration - 0.5):d=0.5"
    & $ffmpeg -hide_banner -loglevel error -y -f lavfi -i "color=c=$($scene.background):s=1920x1080:r=30:d=$($scene.duration)" -vf $filter -c:v libx264 -preset medium -crf 23 -pix_fmt yuv420p $sceneFile
    if ($LASTEXITCODE -ne 0) { throw "ffmpeg failed on $($scene.file)" }
    $inputArguments += @("-i", $sceneFile)
    $labels += "[$($index):v]"
}

& $ffmpeg -hide_banner -loglevel error -y @inputArguments -filter_complex "$labels`concat=n=$($scenes.Count):v=1:a=0[v]" -map "[v]" -c:v libx264 -preset medium -crf 23 -pix_fmt yuv420p -movflags +faststart $target
if ($LASTEXITCODE -ne 0) { throw "ffmpeg composition failed" }
Get-Item -LiteralPath $target | Select-Object FullName,Length,LastWriteTime
