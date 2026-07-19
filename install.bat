@echo off
setlocal EnableDelayedExpansion
title Restaurant POS – First-Time Setup

echo.
echo  ============================================================
echo   Restaurant POS – Windows Setup
echo  ============================================================
echo.

:: ── Check Python ──────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python is not installed or not in PATH.
    echo  Download it from https://www.python.org/downloads/
    echo  Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo  Python %PYVER% found.
echo.

:: ── Get install directory ─────────────────────────────────────
set "INSTALL_DIR=%~dp0"
set "INSTALL_DIR=%INSTALL_DIR:~0,-1%"
echo  Install directory: %INSTALL_DIR%
echo.

:: ── Create virtual environment ────────────────────────────────
if not exist "%INSTALL_DIR%\venv" (
    echo  Creating virtual environment...
    python -m venv "%INSTALL_DIR%\venv"
    if errorlevel 1 (
        echo  [ERROR] Failed to create virtual environment.
        pause & exit /b 1
    )
    echo  Virtual environment created.
) else (
    echo  Virtual environment already exists — skipping creation.
)
echo.

:: ── Install dependencies ──────────────────────────────────────
echo  Installing Python packages (this may take a minute)...
"%INSTALL_DIR%\venv\Scripts\pip.exe" install --upgrade pip -q
"%INSTALL_DIR%\venv\Scripts\pip.exe" install -r "%INSTALL_DIR%\requirements.txt" -q
if errorlevel 1 (
    echo  [ERROR] Package installation failed.
    pause & exit /b 1
)
echo  Packages installed.
echo.

:: ── Create .env from example ──────────────────────────────────
if not exist "%INSTALL_DIR%\.env" (
    echo  Creating .env configuration file...
    copy "%INSTALL_DIR%\.env.example" "%INSTALL_DIR%\.env" >nul

    :: Generate a random secret key
    for /f %%k in ('python -c "import secrets; print(secrets.token_hex(32))"') do set SKEY=%%k
    powershell -Command "(Get-Content '%INSTALL_DIR%\.env') -replace 'change-this-to-a-long-random-secret-key-in-production', '%SKEY%' | Set-Content '%INSTALL_DIR%\.env'"

    echo  .env created with a random secret key.
    echo.
    echo  *** IMPORTANT: Open .env in Notepad and set your restaurant details. ***
    echo.
) else (
    echo  .env already exists — skipping.
)

:: ── Create data directories ───────────────────────────────────
if not exist "%INSTALL_DIR%\data"           mkdir "%INSTALL_DIR%\data"
if not exist "%INSTALL_DIR%\data\backups"   mkdir "%INSTALL_DIR%\data\backups"

:: ── Register Windows Task Scheduler (auto-start on boot) ──────
echo  Registering auto-start task in Windows Task Scheduler...

set "TASK_NAME=Restaurant POS"
set "TASK_CMD=%INSTALL_DIR%\start.bat"

:: Remove existing task if present
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

:: Create task: runs at system startup, hidden window, 60-second delay
schtasks /create ^
  /tn "%TASK_NAME%" ^
  /tr "cmd /c \"start /min \"\" \"%TASK_CMD%\"\"" ^
  /sc onstart ^
  /delay 0001:00 ^
  /ru "%USERNAME%" ^
  /rl HIGHEST ^
  /f >nul 2>&1

if errorlevel 1 (
    echo  [WARNING] Could not register auto-start task (may need Administrator).
    echo  You can still launch manually with start.bat.
) else (
    echo  Auto-start task registered. POS will start automatically on boot.
)
echo.

:: ── Create desktop shortcut ───────────────────────────────────
set "DESKTOP=%USERPROFILE%\Desktop"
set "SHORTCUT=%DESKTOP%\Restaurant POS.lnk"

powershell -Command ^
  "$s=(New-Object -COM WScript.Shell).CreateShortcut('%SHORTCUT%');" ^
  "$s.TargetPath='%INSTALL_DIR%\start.bat';" ^
  "$s.WorkingDirectory='%INSTALL_DIR%';" ^
  "$s.WindowStyle=7;" ^
  "$s.IconLocation='%SystemRoot%\System32\SHELL32.dll,14';" ^
  "$s.Description='Restaurant POS';" ^
  "$s.Save()" >nul 2>&1

if exist "%SHORTCUT%" (
    echo  Desktop shortcut created.
) else (
    echo  [WARNING] Could not create desktop shortcut.
)
echo.

:: ── Done ──────────────────────────────────────────────────────
echo  ============================================================
echo   Setup complete!
echo  ============================================================
echo.
echo   Next steps:
echo    1. Edit .env with your FonePay credentials (if using QR pay)
echo    2. Double-click "Restaurant POS" on your desktop to launch
echo    3. Open your browser to http://127.0.0.1:8000
echo    4. Login: code=demo  user=admin  password=admin123
echo.
echo   The POS will auto-start every time Windows boots.
echo   To remove auto-start, run uninstall.bat
echo.
pause
