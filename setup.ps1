# ============================================================
# 1-CLICK SETUP SCRIPT FOR AI YOUTUBE SHORTS GENERATOR
# ============================================================
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "     AI SHORTS GENERATOR - KHOI TAO MOI TRUONG 1-CLICK   " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Kiem tra Python
Write-Host "`n[1/5] Kiem tra phien ban Python..." -ForegroundColor Yellow
$pyCmd = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
    # Uu tien Python 3.12 hoac 3.11 hoac 3.10
    $pyVer = py -0 2>$null | Out-String
    if ($pyVer -match "3\.12") { $pyCmd = "py -3.12" }
    elseif ($pyVer -match "3\.11") { $pyCmd = "py -3.11" }
    elseif ($pyVer -match "3\.10") { $pyCmd = "py -3.10" }
    else { $pyCmd = "python" }
} else {
    $pyCmd = "python"
}
Write-Host "  -> Su dung: $pyCmd" -ForegroundColor Green

# 2. Tao moi truong ao .venv
if (-not (Test-Path ".venv")) {
    Write-Host "`n[2/5] Dang tao moi truong ao (.venv)..." -ForegroundColor Yellow
    Invoke-Expression "$pyCmd -m venv .venv"
} else {
    Write-Host "`n[2/5] Moi truong ao .venv da ton tai." -ForegroundColor Green
}

# 3. Cai dat cac thu vien phu thuoc
Write-Host "`n[3/5] Cai dat thu vien AI (faster-whisper, opencv, av<14, yt-dlp)..." -ForegroundColor Yellow
& ".\.venv\Scripts\pip.exe" install --upgrade pip --quiet
& ".\.venv\Scripts\pip.exe" install -r requirements-local.txt

# 4. Kiem tra FFmpeg
Write-Host "`n[4/5] Kiem tra FFmpeg..." -ForegroundColor Yellow
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    Write-Host "  -> FFmpeg da co san tren he thong!" -ForegroundColor Green
} elseif (Test-Path "ffmpeg_bin\ffmpeg.exe") {
    Write-Host "  -> Tim thay FFmpeg Portable trong ffmpeg_bin!" -ForegroundColor Green
} else {
    Write-Host "  -> Chua co FFmpeg. Dang tu dong tai ban FFmpeg Portable..." -ForegroundColor Cyan
    & ".\.venv\Scripts\python.exe" -c "
import urllib.request, zipfile, os, shutil
url = 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'
dest = 'ffmpeg_bin'
zip_f = 'ffmpeg.zip'
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
}

# 5. Kiem tra Ollama va tai phien ban Portable neu chua co
Write-Host "`n[5/5] Kiem tra Ollama (cho che do Offline Local)..." -ForegroundColor Yellow
$ollamaExe = "ollama"
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    if (-not (Test-Path "ollama_bin\ollama.exe")) {
        Write-Host "  -> Dang tai Ollama Portable vao thu muc ollama_bin..." -ForegroundColor Cyan
        & ".\.venv\Scripts\python.exe" -c "
import urllib.request, zipfile, os
url = 'https://github.com/ollama/ollama/releases/latest/download/ollama-windows-amd64.zip'
dest = 'ollama_bin'
zip_f = 'ollama.zip'
os.makedirs(dest, exist_ok=True)
print('Dang tai goi Ollama Portable...', flush=True)
urllib.request.urlretrieve(url, zip_f)
with zipfile.ZipFile(zip_f, 'r') as z:
    z.extractall(dest)
if os.path.exists(zip_f): os.remove(zip_f)
print('Giai nen Ollama hoan tat!')
"
    }
    $ollamaExe = ".\ollama_bin\ollama.exe"
}

# Khoi dong Ollama va tai model qwen2.5:3b neu can
$ollamaProc = Get-Process ollama -ErrorAction SilentlyContinue
if (-not $ollamaProc) {
    Start-Process -FilePath $ollamaExe -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 3
}
Write-Host "  -> Dang kiem tra model qwen2.5:3b trong Ollama..." -ForegroundColor Cyan
& $ollamaExe pull qwen2.5:3b

# 6. Tao file .env neu chua co
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "  -> Da tao file .env mac dinh!" -ForegroundColor Green
}

New-Item -ItemType Directory -Force -Path input, output | Out-Null

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "      CAI DAT HOAN TAT! HE THONG DA SAN SANG SU DUNG     " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "Cach su dung:" -ForegroundColor Cyan
Write-Host "  .\run.ps1 `"video.mp4`" 3"
Write-Host "Hoac:" -ForegroundColor Cyan
Write-Host "  .\.venv\Scripts\python.exe main.py `"video.mp4`" --num-clips 3`n"
