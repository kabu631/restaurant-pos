@echo off
title Restaurant POS – Uninstall

echo.
echo  Removing Restaurant POS auto-start task...
schtasks /delete /tn "Restaurant POS" /f >nul 2>&1
if errorlevel 1 (
    echo  Task not found or already removed.
) else (
    echo  Auto-start task removed.
)

echo.
echo  Removing desktop shortcut...
del /f /q "%USERPROFILE%\Desktop\Restaurant POS.lnk" >nul 2>&1
echo  Done.

echo.
echo  NOTE: Your data (database + backups) has NOT been deleted.
echo  Data is stored in: %~dp0data\
echo.
pause
