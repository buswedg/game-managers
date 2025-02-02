@echo off
set "SCRIPT_PATH=%~dp0"
net session >nul 2>&1
if %errorlevel% equ 0 (
    call "%SCRIPT_PATH%env\Scripts\activate"
    python "%SCRIPT_PATH%cli.py"
    deactivate
    pause
) else (
    echo Script must be run with Administrator privileges.
    pause
)
