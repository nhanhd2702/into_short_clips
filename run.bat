@echo off
if "%~1"=="" (
    echo Cach su dung:
    echo   run.bat "duong_dan_video_hoac_youtube_url" [so_luong_clips] [loai: auto/speech/sports]
    echo.
    echo Vi du:
    echo   run.bat "video.mp4" 3 auto
    echo   run.bat "match.mov" 10 sports
    pause
    exit /b 1
)

powershell -ExecutionPolicy Bypass -File "%~dp0run.ps1" "%~1" %2 %3 %4 %5
