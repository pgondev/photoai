@echo off
cd /d "%~dp0"

where py >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python Launcher (py.exe) not found.
    echo Please install Python from https://www.python.org/downloads/
    pause
    exit /b 1
)

py gui_flet.py
