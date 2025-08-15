@echo off

net session >nul 2>&1
if %errorLevel%==0 (
    goto :main
)

if "%~1"=="-elevated" (
    echo Elevation failed. UAC is likely disabled.
    pause
    exit /b 1
)

echo Requesting administrator privileges...
powershell -Command "Start-Process cmd.exe -ArgumentList '/k \"%~f0\" -elevated' -Verb RunAs"
exit /b

:main
set "SCRIPT_PATH=%~dp0"
call "%SCRIPT_PATH%env\Scripts\activate"
python "%SCRIPT_PATH%cli.py"
deactivate
echo Script execution completed.
pause
