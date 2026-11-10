@echo off
setlocal
cd /d "%~dp0"
where pyw >nul 2>nul
if not errorlevel 1 (
  start "" pyw "%~dp0Lilith_Download_Desk.pyw"
  exit /b 0
)
where pythonw >nul 2>nul
if not errorlevel 1 (
  start "" pythonw "%~dp0Lilith_Download_Desk.pyw"
  exit /b 0
)
echo Could not locate the console-free Python launcher pyw.exe or pythonw.exe.
echo Install Python with the Windows launcher, then try again.
pause
exit /b 1
