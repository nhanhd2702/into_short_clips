@echo off
if "%~1"=="" (
    echo ==========================================================
    echo        AI SHORTS GENERATOR - 1-CLICK RUNNER (WINDOWS)
    echo ==========================================================
    echo Cach su dung:
    echo   run.bat "duong_dan_video_hoac_url" [so_luong] [loai: auto/speech/sports] [style: blur/face]
    echo.
    echo Vi du:
    echo   run.bat "video.mp4" 3 auto blur
    echo   run.bat "match.mov" 10 sports
    echo   run.bat "https://www.youtube.com/watch?v=XYZ" 5 speech
    echo ==========================================================
    pause
    exit /b 2
)

powershell -ExecutionPolicy Bypass -File "%~dp0run.ps1" "%~1" %2 %3 %4 %5 %6
exit /b %ERRORLEVEL%
