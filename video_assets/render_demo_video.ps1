# Generates a credential-free 1080p MP4. Run from the repository root.
# It is intentionally source-controlled so the resulting video is reproducible.
param(
    [string]$Output = "deliverables/ForgeLite-demo.mp4",
    [string]$NarrationWave = ""
)

$ErrorActionPreference = "Stop"
$ffmpeg = (Get-Command ffmpeg -ErrorAction Stop).Source
$ffprobe = (Get-Command ffprobe -ErrorAction Stop).Source
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
$webUri = [System.Uri]::new($webSource).AbsoluteUri
$webScreenshots = @{}
foreach ($mode in @("task", "build", "recover", "complete")) {
    $screenshot = Join-Path $temporary "web-$mode.png"
    Remove-Item -LiteralPath $screenshot -Force -ErrorAction SilentlyContinue
    $edgeProfile = Join-Path $temporary "edge-profile-$mode"
    $edgeArguments = @(
        "--headless",
        "--disable-gpu",
        "--hide-scrollbars",
        "--window-size=1920,1080",
        "--virtual-time-budget=1500",
        "--user-data-dir=$edgeProfile",
        "--screenshot=$screenshot",
        "$webUri`?preview=$mode"
    )
    $edgeProcess = Start-Process -FilePath $edge -ArgumentList $edgeArguments -PassThru -Wait -WindowStyle Hidden
    if ($edgeProcess.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $screenshot)) {
        throw "Could not capture the local Web console scene: $mode"
    }
    $webScreenshots[$mode] = $screenshot
}

$font = "C\:/Windows/Fonts/msyh.ttc"
$scenes = @(
    @{ file = "01_title.txt"; duration = 5; background = "0xf6f5f2"; size = 48 },
    @{ image = $webScreenshots["task"]; duration = 14 },
    @{ image = $webScreenshots["build"]; duration = 24 },
    @{ image = $webScreenshots["recover"]; duration = 30 },
    @{ image = $webScreenshots["complete"]; duration = 29 },
    @{ file = "07_close.txt"; duration = 10; background = "0xf6f5f2"; size = 34 }
)

$inputArguments = @()
$labels = ""

for ($index = 0; $index -lt $scenes.Count; $index++) {
    $scene = $scenes[$index]
    $sceneFile = Join-Path $temporary ("scene-{0:D2}.mp4" -f $index)
    if ($scene.image) {
        $filter = "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0xf6f5f2,fade=t=in:st=0:d=0.35:color=white,fade=t=out:st=$($scene.duration - 0.35):d=0.35:color=white"
        & $ffmpeg -hide_banner -loglevel error -y -loop 1 -framerate 30 -i $scene.image -t $scene.duration -vf $filter -c:v libx264 -preset medium -crf 23 -pix_fmt yuv420p $sceneFile
        if ($LASTEXITCODE -ne 0) { throw "ffmpeg failed on Web console screenshot" }
    }
    else {
        $text = (Join-Path $assets $scene.file).Replace("\", "/").Replace(":", "\:")
        $filter = "drawtext=fontfile='$font':textfile='$text':fontcolor=0x252521:fontsize=$($scene.size):line_spacing=16:x=90:y=(h-text_h)/2,fade=t=in:st=0:d=0.35:color=white,fade=t=out:st=$($scene.duration - 0.35):d=0.35:color=white"
        & $ffmpeg -hide_banner -loglevel error -y -f lavfi -i "color=c=$($scene.background):s=1920x1080:r=30:d=$($scene.duration)" -vf $filter -c:v libx264 -preset medium -crf 23 -pix_fmt yuv420p $sceneFile
        if ($LASTEXITCODE -ne 0) { throw "ffmpeg failed on $($scene.file)" }
    }
    $inputArguments += @("-i", $sceneFile)
    $labels += "[$($index):v]"
}

$silentVideo = Join-Path $temporary "forgelite-silent.mp4"
& $ffmpeg -hide_banner -loglevel error -y @inputArguments -filter_complex "$labels`concat=n=$($scenes.Count):v=1:a=0[v]" -map "[v]" -c:v libx264 -preset medium -crf 23 -pix_fmt yuv420p $silentVideo
if ($LASTEXITCODE -ne 0) { throw "ffmpeg video composition failed" }

if ($NarrationWave) {
    $narrationWavePath = (Resolve-Path -LiteralPath $NarrationWave -ErrorAction Stop).Path
}
else {
    Add-Type -AssemblyName System.Speech
    $speaker = [System.Speech.Synthesis.SpeechSynthesizer]::new()
    try {
        $chineseVoice = $speaker.GetInstalledVoices() |
            Where-Object { $_.VoiceInfo.Culture.Name -eq "zh-CN" } |
            Select-Object -First 1
        if (-not $chineseVoice) { throw "A zh-CN Windows speech voice is required for narration." }
        $speaker.SelectVoice($chineseVoice.VoiceInfo.Name)
        $speaker.Rate = 3
        $narrationText = Get-Content -LiteralPath (Join-Path $assets "narration.md") -Raw -Encoding utf8
        $narrationText = ($narrationText -replace '(?m)^#.*$', '' -replace '[`“”]', '').Trim()
        $narrationWavePath = Join-Path $temporary "forgelite-narration.wav"
        $speaker.SetOutputToWaveFile($narrationWavePath)
        $speaker.Speak($narrationText)
    }
    finally {
        $speaker.Dispose()
    }
}

$narrationDuration = [double](& $ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 $narrationWavePath)
$videoDuration = [double](& $ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 $silentVideo)
if ($narrationDuration -gt $videoDuration) {
    throw "Narration is $([math]::Round($narrationDuration, 2)) seconds, longer than the $([math]::Round($videoDuration, 2))-second video."
}

& $ffmpeg -hide_banner -loglevel error -y -i $silentVideo -i $narrationWavePath -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 128k -af "loudnorm=I=-16:TP=-1.5:LRA=11,apad" -shortest -movflags +faststart $target
if ($LASTEXITCODE -ne 0) { throw "ffmpeg narration composition failed" }
Get-Item -LiteralPath $target | Select-Object FullName,Length,LastWriteTime
