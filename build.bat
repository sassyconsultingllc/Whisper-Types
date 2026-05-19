@echo off
REM Build release exe + folder via PyInstaller.
REM Output: dist\WhisperTyper\WhisperTyper.exe
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating venv...
    python -m venv .venv || goto :err
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt || goto :err
pip install pyinstaller || goto :err

REM Optional: install TTS backends so they get bundled
pip install kokoro-onnx 2>nul

if exist build rmdir /s /q build
if exist dist\WhisperTyper rmdir /s /q dist\WhisperTyper

pyinstaller whispertyper.spec --clean --noconfirm || goto :err

echo.
echo Built: dist\WhisperTyper\WhisperTyper.exe
echo.
exit /b 0

:err
echo BUILD FAILED.
exit /b 1
