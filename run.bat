@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating venv...
    python -m venv .venv || goto :err
    call .venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -r requirements.txt || goto :err
) else (
    call .venv\Scripts\activate.bat
)

start "" pythonw main.py
exit /b 0

:err
echo Setup failed.
pause
exit /b 1
