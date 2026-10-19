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
    exit 2
}

# 1. Kiem tra va khoi dong Ollama neu can thiet (chi khi chay speech hoac auto voi provider ollama)
if ($Type -ne "sports") {
    $needsOllama = $true
    if (Test-Path "$PSScriptRoot\.env") {
        $envContent = Get-Content "$PSScriptRoot\.env" -Raw
        if ($envContent -match 'LLM_PROVIDER\s*=\s*["'']?(openai|gemini)["'']?') {
            $needsOllama = $false
        }
    }
    if ($needsOllama) {
        $ollamaHealthy = $false
        try {
            $null = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -Method Get -TimeoutSec 2 -ErrorAction Stop
            $ollamaHealthy = $true
        } catch {
            $ollamaHealthy = $false
        }

        if (-not $ollamaHealthy) {
            $ollamaExe = "ollama"
            if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
                if (Test-Path "$PSScriptRoot\ollama_bin\ollama.exe") {
                    $ollamaExe = "$PSScriptRoot\ollama_bin\ollama.exe"
                }
            }
            Write-Host "[Ollama] Dang khoi dong Ollama server ngam..." -ForegroundColor Cyan
            try {
                Start-Process -FilePath $ollamaExe -ArgumentList "serve" -WindowStyle Hidden
            } catch {
                Write-Host "[Ollama] Khong the tu dong khoi dong Ollama: $_" -ForegroundColor Yellow
            }

            # Polling cho toi khi server phan hoi (toi da 15 giay)
            $timeout = 15
            $elapsed = 0
            while ($elapsed -lt $timeout) {
                Start-Sleep -Seconds 1
                $elapsed += 1
                try {
                    $null = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -Method Get -TimeoutSec 2 -ErrorAction Stop
                    $ollamaHealthy = $true
                    break
                } catch {
                    $ollamaHealthy = $false
                }
            }
            if ($ollamaHealthy) {
                Write-Host "[Ollama] Server da san sang!" -ForegroundColor Green
            } else {
                Write-Host "[Ollama] Canh bao: Chua the ket noi toi Ollama tai http://127.0.0.1:11434 sau ${timeout}s." -ForegroundColor Yellow
            }
        }
    }
}

# 2. Tu dong bo sung ffmpeg_bin va ollama_bin vao PATH neu co
if (Test-Path "$PSScriptRoot\ffmpeg_bin") {
    $env:PATH = "$PSScriptRoot\ffmpeg_bin;$env:PATH"
}
if (Test-Path "$PSScriptRoot\ollama_bin") {
    $env:PATH = "$PSScriptRoot\ollama_bin;$env:PATH"
}

# 3. Kiem tra moi truong Python
$pyExe = "$PSScriptRoot\.venv\Scripts\python.exe"
if (-not (Test-Path $pyExe)) {
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $pyExe = "python"
    } else {
        Write-Host "[Loi] Khong tim thay Python hoac moi truong .venv! Vui long chay setup.bat truoc." -ForegroundColor Red
        exit 1
    }
}

# 4. Goi engine chay tao Shorts
Write-Host "[Generator] Bat dau xu ly: $UrlOrPath (Type: $Type, Clips: $NumClips, Style: $CropStyle)" -ForegroundColor Yellow
& $pyExe "$PSScriptRoot\main.py" $UrlOrPath --type $Type --num-clips $NumClips --aspect-ratio $AspectRatio --duration $Duration --crop-style $CropStyle
exit $LASTEXITCODE
