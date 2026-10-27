@echo off
setlocal enabledelayedexpansion
title OpenMontage AI Video Editor

echo ======================================================================
echo Starting OpenMontage AI Video Editor...
echo ======================================================================

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

:: 1. Check for Virtual Environment Python
if exist "%SCRIPT_DIR%.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%SCRIPT_DIR%.venv\Scripts\python.exe"
) else (
    where python >nul 2>nul
    if %errorlevel% equ 0 (
        set "PYTHON_EXE=python"
    ) else (
        echo [ERROR] Python 3.10+ is required but was not found in PATH or .venv.
        echo Please install Python 3.10 or later from https://www.python.org/
        pause
        exit /b 1
    )
)

:: 2. Launch OpenMontage through unified Python launcher
"%PYTHON_EXE%" "%SCRIPT_DIR%scripts\launcher.py"
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] OpenMontage encountered an error during launch.
    pause
)

exit /b %errorlevel%
