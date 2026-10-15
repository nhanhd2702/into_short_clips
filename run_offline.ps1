# ============================================================
# SCRIPT CHẠY CẮT VIDEO SHORTS TỰ ĐỘNG 100% OFFLINE (NO-API)
# ============================================================

param (
    [Parameter(Mandatory=$true, Position=0)]
    [string]$VideoPath,

    [Parameter(Position=1)]
    [int]$NumClips = 3,

    [Parameter(Position=2)]
    [string]$AspectRatio = "9:16"
)

# 1. Kiểm tra và tự động khởi động Ollama nếu chưa chạy
$ollamaRunning = Get-Process ollama -ErrorAction SilentlyContinue
if (-not $ollamaRunning) {
    Write-Host "[Ollama] Dang khoi dong Ollama server ngam..." -ForegroundColor Cyan
    Start-Process -FilePath ".\ollama_bin\ollama.exe" -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 3
} else {
    Write-Host "[Ollama] Server da san sang tren cong 11434." -ForegroundColor Green
}

# 2. Chạy pipeline tao Shorts
Write-Host "[Generator] Bat dau xu ly video: $VideoPath" -ForegroundColor Yellow
& ".\.venv\Scripts\python.exe" main.py $VideoPath --mode local --num-clips $NumClips --aspect-ratio $AspectRatio
