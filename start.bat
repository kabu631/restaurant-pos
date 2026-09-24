@echo off
setlocal
set "DIR=%~dp0"
set "DIR=%DIR:~0,-1%"

:: Use venv python if it exists, otherwise system python
set "PYTHON=python"
if exist "%DIR%\venv\Scripts\python.exe" (
    "%DIR%\venv\Scripts\python.exe" -c "import fastapi" >nul 2>&1
    if errorlevel 1 (
        echo.
        echo  [!] The POS Python environment is broken or incomplete
        echo      ^(this happens after copying the folder to a new PC or reinstalling Python^).
        echo      Double-click install.bat once to repair it, then start the POS again.
        echo.
        pause
        exit /b 1
    )
    set "PYTHON=%DIR%\venv\Scripts\python.exe"
)

cd /d "%DIR%"
"%PYTHON%" run.py
