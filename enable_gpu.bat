@echo off
:: WhisperTyper - Enable GPU acceleration (NVIDIA only)
:: Run this once after extracting to add CUDA DLLs alongside the exe.
:: Requires: pip installed (Python for Windows), NVIDIA GPU, driver >= 520

setlocal
set "SCRIPT_DIR=%~dp0"
set "CUDA_DIR=%SCRIPT_DIR%_cuda_dlls"

echo ============================================================
echo  WhisperTyper - GPU Acceleration Setup
echo ============================================================
echo.

:: Check Python
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python from https://python.org/downloads/
    pause
    exit /b 1
)

:: Check for NVIDIA GPU (best-effort)
nvidia-smi >nul 2>&1
if errorlevel 1 (
    echo [WARN] nvidia-smi not found in PATH. If you have an NVIDIA GPU,
    echo        you can still try this setup. Otherwise, WhisperTyper will
    echo        run on CPU - that is totally fine.
    echo.
) else (
    echo [OK] NVIDIA GPU detected.
    echo.
)

:: Check pip via python -m pip
python -m pip --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] pip not found. Install Python from https://python.org/downloads/
    pause
    exit /b 1
)

echo [INFO] Installing CUDA 12 runtime DLLs into a temporary venv...
echo        (This downloads ~700 MB one time only)
echo.

:: Create a temp venv just to extract the DLLs - no permanent changes to system Python
set "TMPVENV=%TEMP%\wt_cuda_venv_%RANDOM%"
python -m venv "%TMPVENV%" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Could not create temporary venv. Is Python installed?
    pause
    exit /b 1
)

"%TMPVENV%\Scripts\python.exe" -m pip install --quiet ^
    nvidia-cublas-cu12 ^
    nvidia-cuda-runtime-cu12 ^
    nvidia-cudnn-cu12

if errorlevel 1 (
    echo [ERROR] pip install failed. Check your internet connection.
    rmdir /s /q "%TMPVENV%"
    pause
    exit /b 1
)

:: Copy all CUDA DLLs into _cuda_dlls/ next to WhisperTyper.exe
if not exist "%CUDA_DIR%" mkdir "%CUDA_DIR%"

set "FOUND=0"
for /d %%P in ("%TMPVENV%\Lib\site-packages\nvidia\*") do (
    if exist "%%P\bin\" (
        copy /Y "%%P\bin\*.dll" "%CUDA_DIR%\" >nul
        set "FOUND=1"
    )
)

rmdir /s /q "%TMPVENV%"

if "%FOUND%"=="0" (
    echo [ERROR] No CUDA DLLs found after install. Something went wrong.
    pause
    exit /b 1
)

echo.
echo [OK] GPU support enabled! CUDA DLLs copied to:
echo      %CUDA_DIR%
echo.
echo Launch WhisperTyper.exe - it will now use your NVIDIA GPU automatically.
echo.
pause
