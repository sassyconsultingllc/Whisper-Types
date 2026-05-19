@echo off
REM Build release exe + folder via PyInstaller.
REM Output: dist\WhisperTyper\WhisperTyper.exe
setlocal
cd /d "%~dp0"

REM Use fast spec (excludes problematic QML)
set SPEC=whispertyper_fast.spec

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

REM Install CUDA runtime DLLs (required for ctranslate2)
pip install nvidia-cublas-cu12 nvidia-cuda-runtime-cu12 nvidia-cudnn-cu12 2>nul

if exist build rmdir /s /q build
if exist dist\WhisperTyper rmdir /s /q dist\WhisperTyper

echo Building with %SPEC%...
pyinstaller %SPEC% --clean --noconfirm || goto :err

echo.
echo Built: dist\WhisperTyper\WhisperTyper.exe
echo.
exit /b 0

:err
echo BUILD FAILED.
exit /b 1
