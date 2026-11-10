@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  py "%~dp0Prepare_Media_Engine.py"
  goto :done
)
where python >nul 2>nul
if not errorlevel 1 (
  python "%~dp0Prepare_Media_Engine.py"
  goto :done
)
echo Python was not found. Run 01_Install_and_Launch.bat again.
:done
echo.
echo This diagnostic window can be closed now.
pause
