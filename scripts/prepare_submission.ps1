# Create the exact archive requested by the competition after the account-bound
# details (public repository URL and your name) are available.
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[^\\/:*?"<>|]+$')]
    [string]$Name,
    [string]$Video = "deliverables/ForgeLite-demo.mp4"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$readme = Join-Path $root "README.txt"
$videoPath = Join-Path $root $Video
$outputDirectory = Join-Path $root "deliverables"
$output = Join-Path $outputDirectory "$Name.zip"

if (-not (Test-Path -LiteralPath $readme)) { throw "README.txt is missing." }
if (-not (Test-Path -LiteralPath $videoPath)) { throw "Video is missing: $videoPath" }

$readmeText = Get-Content -LiteralPath $readme -Raw -Encoding utf8
if ($readmeText.Length -gt 1000) { throw "README.txt is $($readmeText.Length) characters; the limit is 1000." }
if ($readmeText -match '<请替换为你的账号>' -or $readmeText -match 'github\.com/<') {
    throw "Replace the repository URL placeholder in README.txt before packing."
}

$ffprobe = (Get-Command ffprobe -ErrorAction Stop).Source
$metadata = & $ffprobe -v error -show_entries format=duration,size -of default=noprint_wrappers=1 $videoPath
if ($LASTEXITCODE -ne 0) { throw "ffprobe could not read the video." }
$duration = [double](($metadata | Select-String '^duration=').ToString().Split('=')[1])
$size = [int64](($metadata | Select-String '^size=').ToString().Split('=')[1])
if ($duration -gt 120) { throw "Video is $duration seconds; it must not exceed 120 seconds." }
if ($size -gt 200MB) { throw "Video is $size bytes; it must not exceed 200 MB." }

New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
if (Test-Path -LiteralPath $output) { throw "Output already exists: $output" }
Compress-Archive -LiteralPath $readme, $videoPath -DestinationPath $output -CompressionLevel Optimal
Get-Item -LiteralPath $output | Select-Object FullName,Length,LastWriteTime
