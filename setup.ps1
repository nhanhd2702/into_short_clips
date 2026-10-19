# ============================================================
# 1-CLICK SETUP SCRIPT FOR AI YOUTUBE SHORTS GENERATOR (WINDOWS)
# ============================================================
param (
    [switch]$SportsOnly = $false
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "     AI SHORTS GENERATOR - KHOI TAO MOI TRUONG 1-CLICK   " -ForegroundColor Cyan
if ($SportsOnly) {
    Write-Host "     [Che do: Sports Only - Khong tai Ollama/Model AI]  " -ForegroundColor Yellow
}
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Kiem tra phien ban Python
Write-Host "`n[1/5] Kiem tra phien ban Python..." -ForegroundColor Yellow
$pyCmd = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
    $pyVer = py -0 2>$null | Out-String
    if ($pyVer -match "3\.12") { $pyCmd = "py -3.12" }
    elseif ($pyVer -match "3\.11") { $pyCmd = "py -3.11" }
    elseif ($pyVer -match "3\.10") { $pyCmd = "py -3.10" }
    else { $pyCmd = "python" }
} else {
    $pyCmd = "python"
}

try {
    $pyCheck = Invoke-Expression "$pyCmd -c `"import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')`""
    $parts = $pyCheck.Trim().Split(".")
    $major = [int]$parts[0]
    $minor = [int]$parts[1]
    if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 10)) {
        Write-Host "[Loi] Yeu cau Python >= 3.10 (phien ban hien tai: $pyCheck)" -ForegroundColor Red
        exit 1
    }
    Write-Host "  -> Su dung: $pyCmd (Python $pyCheck)" -ForegroundColor Green
} catch {
    Write-Host "[Loi] Khong the chay $pyCmd. Vui long cai dat Python 3.10+ tu python.org." -ForegroundColor Red
    exit 1
}

# 2. Tao moi truong ao .venv
if (-not (Test-Path "$PSScriptRoot\.venv")) {
    Write-Host "`n[2/5] Dang tao moi truong ao (.venv)..." -ForegroundColor Yellow
    Invoke-Expression "$pyCmd -m venv `"$PSScriptRoot\.venv`""
    if (-not (Test-Path "$PSScriptRoot\.venv\Scripts\python.exe")) {
        Write-Host "[Loi] Tao moi truong .venv that bai!" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "`n[2/5] Moi truong ao .venv da ton tai." -ForegroundColor Green
}

$venvPython = "$PSScriptRoot\.venv\Scripts\python.exe"
$venvPip = "$PSScriptRoot\.venv\Scripts\pip.exe"

# 3. Cai dat thu vien
Write-Host "`n[3/5] Cai dat thu vien phu thuoc..." -ForegroundColor Yellow
try {
    & $venvPython -m pip install --upgrade pip --quiet
    & $venvPython -m pip install -r "$PSScriptRoot\requirements-local.txt"
    if ($LASTEXITCODE -ne 0) {
        throw "pip install failed with exit code $LASTEXITCODE"
    }
} catch {
    Write-Host "[Loi] Cai dat thu vien Python that bai: $_" -ForegroundColor Red
    exit 1
}

# 4. Kiem tra FFmpeg
Write-Host "`n[4/5] Kiem tra FFmpeg..." -ForegroundColor Yellow
$hasFfmpeg = $false
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    $hasFfmpeg = $true
    Write-Host "  -> FFmpeg da co san tren he thong!" -ForegroundColor Green
} elseif (Test-Path "$PSScriptRoot\ffmpeg_bin\ffmpeg.exe") {
    $hasFfmpeg = $true
    Write-Host "  -> Tim thay FFmpeg Portable trong ffmpeg_bin!" -ForegroundColor Green
} else {
    Write-Host "  -> Chua co FFmpeg. Dang tu dong tai ban FFmpeg Portable..." -ForegroundColor Cyan
    try {
        & $venvPython -c "
import urllib.request, zipfile, os, shutil
url = 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'
dest = os.path.join(r'$PSScriptRoot', 'ffmpeg_bin')
zip_f = os.path.join(r'$PSScriptRoot', 'ffmpeg.zip')
os.makedirs(dest, exist_ok=True)
print('Dang tai FFmpeg essentials (khoang 30MB)...', flush=True)
urllib.request.urlretrieve(url, zip_f)
print('Dang giai nen FFmpeg...', flush=True)
with zipfile.ZipFile(zip_f, 'r') as z:
    for m in z.namelist():
        if m.endswith('ffmpeg.exe') or m.endswith('ffprobe.exe'):
            fname = os.path.basename(m)
            with z.open(m) as src, open(os.path.join(dest, fname), 'wb') as dst:
                shutil.copyfileobj(src, dst)
if os.path.exists(zip_f): os.remove(zip_f)
print('FFmpeg da san sang!')
"
        if (Test-Path "$PSScriptRoot\ffmpeg_bin\ffmpeg.exe") {
            $hasFfmpeg = $true
        }
    } catch {
        Write-Host "[Canh bao] Khong the tu dong tai FFmpeg: $_" -ForegroundColor Yellow
    }
}

# 5. Kiem tra Whisper model & Ollama neu khong phai SportsOnly
if (-not $SportsOnly) {
    Write-Host "`n[5/6] Kiem tra model Whisper (phien am offline)..." -ForegroundColor Yellow
    try {
        & $venvPython -c "from shorts_generator.local.model_downloader import ensure_whisper_model; ensure_whisper_model('base')"
        if ($LASTEXITCODE -ne 0) {
            throw "Whisper model download failed with exit code $LASTEXITCODE"
        }
        Write-Host "  -> Whisper base model da san sang!" -ForegroundColor Green
    } catch {
        Write-Host "[Canh bao] Khong the tai hoac xac thuc Whisper base model: $_" -ForegroundColor Yellow
    }

    Write-Host "`n[6/6] Kiem tra Ollama (cho che do Offline Speech)..." -ForegroundColor Yellow
    $ollamaExe = "ollama"
    if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
        if (-not (Test-Path "$PSScriptRoot\ollama_bin\ollama.exe")) {
            Write-Host "  -> Dang tai Ollama Portable vao thu muc ollama_bin..." -ForegroundColor Cyan
            try {
                & $venvPython -c "
import urllib.request, zipfile, os
url = 'https://github.com/ollama/ollama/releases/latest/download/ollama-windows-amd64.zip'
dest = os.path.join(r'$PSScriptRoot', 'ollama_bin')
zip_f = os.path.join(r'$PSScriptRoot', 'ollama.zip')
os.makedirs(dest, exist_ok=True)
print('Dang tai goi Ollama Portable...', flush=True)
urllib.request.urlretrieve(url, zip_f)
with zipfile.ZipFile(zip_f, 'r') as z:
    z.extractall(dest)
if os.path.exists(zip_f): os.remove(zip_f)
print('Giai nen Ollama hoan tat!')
"
            } catch {
                Write-Host "[Canh bao] Khong the tu dong tai Ollama: $_" -ForegroundColor Yellow
            }
        }
        if (Test-Path "$PSScriptRoot\ollama_bin\ollama.exe") {
            $ollamaExe = "$PSScriptRoot\ollama_bin\ollama.exe"
        }
    }

    if ((Get-Command ollama -ErrorAction SilentlyContinue) -or (Test-Path "$PSScriptRoot\ollama_bin\ollama.exe")) {
        $ollamaHealthy = $false
        try {
            $null = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -Method Get -TimeoutSec 2 -ErrorAction Stop
            $ollamaHealthy = $true
        } catch {
            $ollamaHealthy = $false
        }
        if (-not $ollamaHealthy) {
            Start-Process -FilePath $ollamaExe -ArgumentList "serve" -WindowStyle Hidden
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
        }
        if ($ollamaHealthy) {
            Write-Host "  -> Dang kiem tra model qwen2.5:3b trong Ollama..." -ForegroundColor Cyan
            & $ollamaExe pull qwen2.5:3b
        } else {
            Write-Host "  -> [Canh bao] Ollama server chua khoi dong kip." -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "`n[5/6] Bo qua Whisper va Ollama vi da chon che do SportsOnly." -ForegroundColor Green
}

# Tao file .env neu chua co
if (-not (Test-Path "$PSScriptRoot\.env")) {
    Copy-Item "$PSScriptRoot\.env.example" "$PSScriptRoot\.env"
    Write-Host "  -> Da tao file .env mac dinh!" -ForegroundColor Green
}

New-Item -ItemType Directory -Force -Path "$PSScriptRoot\input", "$PSScriptRoot\output" | Out-Null

# Final Verification Checks
Write-Host "`nKiem tra tong the sau cai dat..." -ForegroundColor Yellow
$allChecksPassed = $true

if (-not (Test-Path $venvPython)) {
    Write-Host "[X] Khong tim thay Python venv tai $venvPython" -ForegroundColor Red
    $allChecksPassed = $false
} else {
    Write-Host "[v] Python venv san sang." -ForegroundColor Green
}

if (-not $hasFfmpeg) {
    Write-Host "[X] FFmpeg chua duoc cai dat. Vui long cai FFmpeg vao PATH hoac ffmpeg_bin." -ForegroundColor Red
    $allChecksPassed = $false
} else {
    Write-Host "[v] FFmpeg san sang." -ForegroundColor Green
}

if (-not $SportsOnly) {
    # Kiem tra Whisper base model
    $whisperReady = $false
    try {
        & $venvPython -c "from shorts_generator.local.model_downloader import ensure_whisper_model; ensure_whisper_model('base')"
        if ($LASTEXITCODE -eq 0) { $whisperReady = $true }
    } catch {
        $whisperReady = $false
    }
    if ($whisperReady) {
        Write-Host "[v] Whisper base model san sang." -ForegroundColor Green
    } else {
        Write-Host "[X] Whisper base model chua san sang hoac bi loi hash!" -ForegroundColor Red
        $allChecksPassed = $false
    }

    # Kiem tra Ollama daemon & model qwen2.5:3b
    $ollamaModelReady = $false
    try {
        $tags = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -Method Get -TimeoutSec 3 -ErrorAction Stop
        if ($tags -and $tags.models) {
            foreach ($m in $tags.models) {
                if ($m.name -match "qwen2\.5:3b") {
                    $ollamaModelReady = $true
                    break
                }
            }
        }
    } catch {
        $ollamaModelReady = $false
    }

    if ($ollamaModelReady) {
        Write-Host "[v] Ollama & model qwen2.5:3b san sang." -ForegroundColor Green
    } else {
        Write-Host "[X] Ollama chua chay hoac chua co model qwen2.5:3b!" -ForegroundColor Red
        Write-Host "    Huong dan: Khoi dong Ollama va chay 'ollama pull qwen2.5:3b'" -ForegroundColor Yellow
        $allChecksPassed = $false
    }
}

if ($allChecksPassed) {
    Write-Host "`n==========================================================" -ForegroundColor Green
    Write-Host "      CAI DAT HOAN TAT! HE THONG DA SAN SANG SU DUNG     " -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Green
    Write-Host "Cach su dung:" -ForegroundColor Cyan
    Write-Host "  .\run.ps1 `"video.mp4`" 3"
    Write-Host "Hoac cat sports highlight:" -ForegroundColor Cyan
    Write-Host "  .\run.ps1 `"match.mov`" 10 sports`n"
    exit 0
} else {
    Write-Host "`n==========================================================" -ForegroundColor Red
    Write-Host "  CAI DAT CHUA HOAN TAT! Vui long kiem tra cac loi tren. " -ForegroundColor Red
    Write-Host "==========================================================" -ForegroundColor Red
    exit 1
}
