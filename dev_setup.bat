@echo off
REM Bootstrap dev environment.
setlocal
cd /d "%~dp0"

where python >nul 2>&1 || (
    echo Python not on PATH. Install Python 3.11+ first.
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating venv at .venv
    python -m venv .venv || exit /b 1
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt || exit /b 1
pip install pyinstaller

echo.
echo Optional TTS backends (skip if not wanted):
echo   pip install kokoro-onnx
echo   pip install piper-tts
echo.
echo Done. Activate later with: .venv\Scripts\activate.bat
echo Run with: python main.py  or  run.bat
exit /b 0
