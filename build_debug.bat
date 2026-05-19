@echo off
REM Build debug exe with visible console for log capture.
REM Output: dist\WhisperTyper-debug\WhisperTyper-debug.exe
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv || goto :err
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt || goto :err
pip install pyinstaller || goto :err
pip install kokoro-onnx 2>nul

if exist build rmdir /s /q build
if exist dist\WhisperTyper-debug rmdir /s /q dist\WhisperTyper-debug

pyinstaller whispertyper_debug.spec --clean --noconfirm || goto :err

echo.
echo Built: dist\WhisperTyper-debug\WhisperTyper-debug.exe
echo Console output captured to stderr; pipe with ^>log.txt 2^>^&1 to save.
echo.
exit /b 0

:err
echo BUILD FAILED.
exit /b 1
