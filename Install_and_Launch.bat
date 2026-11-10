@echo off
setlocal
cd /d "%~dp0"
title Lilith Download Desk - Setup

echo ============================================================
echo  LILITH DOWNLOAD DESK v1.3.2 - AUTOMATIC MEDIA SETUP
echo ============================================================
echo.
echo No separate FFmpeg installation or PATH editing needed.
echo The installer downloads a licensed Python package with FFmpeg
 echo and prepares a private copy for Lilith (download roughly 40 MB).
echo.

where py >nul 2>nul
if not errorlevel 1 (
  set "PYTHON=py"
  goto :install
)
where python >nul 2>nul
if not errorlevel 1 (
  set "PYTHON=python"
  goto :install
)
echo ERROR: Python 3.11+ was not found. Install Python and try again.
goto :fail

:install
%PYTHON% -m pip install --upgrade "yt-dlp[default]" pillow pystray "imageio-ffmpeg>=0.6.0"
if errorlevel 1 goto :fail

echo.
echo Preparing Lilith's private FFmpeg executable...
%PYTHON% "%~dp0Prepare_Media_Engine.py"
if errorlevel 1 goto :fail

echo.
echo Ready. Starting Lilith without a console window...
call "%~dp0Launch.bat"
exit /b 0

:fail
echo.
echo Setup could not finish. See the error text above.
echo Your previous working Lilith installation has not been modified.
pause
exit /b 1
