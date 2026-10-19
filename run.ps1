# ============================================================
# 1-CLICK RUNNER FOR AI YOUTUBE SHORTS GENERATOR (WINDOWS)
# ============================================================
param (
    [Parameter(Position=0)]
    [string]$UrlOrPath = "",

    [Parameter(Position=1)]
    [int]$NumClips = 3,

    [Parameter(Position=2)]
    [string]$Type = "auto",

    [Parameter(Position=3)]
    [string]$CropStyle = "blur",

    [Parameter(Position=4)]
    [string]$AspectRatio = "9:16",

    [Parameter(Position=5)]
    [float]$Duration = 45.0
)

if (-not $UrlOrPath) {
    Write-Host "==========================================================" -ForegroundColor Cyan
    Write-Host "       AI SHORTS GENERATOR - HUONG DAN SU DUNG           " -ForegroundColor Cyan
    Write-Host "==========================================================" -ForegroundColor Cyan
    Write-Host "Cu phap:" -ForegroundColor Yellow
    Write-Host "  .\run.ps1 <duong_dan_video_hoac_url> [so_luong_clips] [loai: auto/speech/sports] [crop_style: blur/face] [ty_le] [thoi_luong]"
    Write-Host "`nVi du:" -ForegroundColor Green
    Write-Host "  1. Cat video tro chuyen / podcast (Pillarbox Blur 1080x1920 mac dinh):"
    Write-Host "     .\run.ps1 `"video.mp4`" 3 speech blur"
    Write-Host "  2. Cat video tro chuyen bam sat mat nguoi noi (Face Crop):"
    Write-Host "     .\run.ps1 `"podcast.mp4`" 5 speech face"
    Write-Host "  3. Cat video the thao / hanh dong (theo am luong ho reo):"
    Write-Host "     .\run.ps1 `"match.mov`" 10 sports blur 9:16 45"
    Write-Host "  4. Tu dong nhan dien (mac dinh):"
    Write-Host "     .\run.ps1 `"video.mp4`" 3"
    exit 0
}

# 1. Kiem tra va khoi dong Ollama neu chua chay
$ollamaProc = Get-Process ollama -ErrorAction SilentlyContinue
if (-not $ollamaProc) {
    $ollamaExe = "ollama"
    if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
        if (Test-Path "$PSScriptRoot\ollama_bin\ollama.exe") {
            $ollamaExe = "$PSScriptRoot\ollama_bin\ollama.exe"
        }
    }
    Write-Host "[Ollama] Dang khoi dong Ollama server ngam..." -ForegroundColor Cyan
    Start-Process -FilePath $ollamaExe -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 3
}

# 2. Tu dong bo sung ffmpeg_bin va ollama_bin vao PATH neu co
if (Test-Path "$PSScriptRoot\ffmpeg_bin") {
    $env:PATH = "$PSScriptRoot\ffmpeg_bin;$env:PATH"
}
if (Test-Path "$PSScriptRoot\ollama_bin") {
    $env:PATH = "$PSScriptRoot\ollama_bin;$env:PATH"
}

# 3. Goi engine chay tao Shorts
Write-Host "[Generator] Bat dau xu ly: $UrlOrPath (Type: $Type, Clips: $NumClips, Style: $CropStyle)" -ForegroundColor Yellow
& ".\.venv\Scripts\python.exe" main.py $UrlOrPath --type $Type --num-clips $NumClips --aspect-ratio $AspectRatio --duration $Duration --crop-style $CropStyle
