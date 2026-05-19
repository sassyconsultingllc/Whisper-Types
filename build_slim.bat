@echo off
REM Build slim release exe (no bundled CUDA, ~80%% smaller than full build).
REM GPU users run enable_gpu.bat after extracting the zip.
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
pip install kokoro-onnx 2>nul

REM NOTE: Do NOT install nvidia-*-cu12 here - slim build excludes CUDA DLLs
REM       Users who want GPU run enable_gpu.bat after install.

if exist build rmdir /s /q build
if exist dist\WhisperTyper rmdir /s /q dist\WhisperTyper

echo Building slim (no CUDA) with whispertyper_slim.spec...
pyinstaller whispertyper_slim.spec --clean --noconfirm || goto :err

REM Copy user-facing scripts into the dist folder
copy /Y enable_gpu.bat           dist\WhisperTyper\
copy /Y install_context_menu.ps1 dist\WhisperTyper\
copy /Y uninstall_context_menu.ps1 dist\WhisperTyper\

echo.
echo ============================================================
echo  Build complete: dist\WhisperTyper\WhisperTyper.exe
echo  GPU support: users run enable_gpu.bat after extracting
echo ============================================================
echo.
exit /b 0

:err
echo BUILD FAILED.
exit /b 1
