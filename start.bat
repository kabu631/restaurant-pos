@echo off
setlocal
set "DIR=%~dp0"
set "DIR=%DIR:~0,-1%"

:: Use venv python if it exists, otherwise system python
if exist "%DIR%\venv\Scripts\python.exe" (
    set "PYTHON=%DIR%\venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)

cd /d "%DIR%"
"%PYTHON%" run.py
