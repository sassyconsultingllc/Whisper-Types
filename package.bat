@echo off
REM Zip the built dist folder for distribution.
REM Output: WhisperTyper-win64.zip
setlocal
cd /d "%~dp0"

set TARGET=%1
if "%TARGET%"=="" set TARGET=release

if "%TARGET%"=="release" (
    set SRC=dist\WhisperTyper
    set OUT=WhisperTyper-win64.zip
) else (
    set SRC=dist\WhisperTyper-debug
    set OUT=WhisperTyper-debug-win64.zip
)

if not exist "%SRC%" (
    echo Not built yet: %SRC%
    echo Run build.bat or build_debug.bat first.
    exit /b 1
)

if exist "%OUT%" del "%OUT%"

powershell -NoProfile -Command "Compress-Archive -Path '%SRC%\*' -DestinationPath '%OUT%' -CompressionLevel Optimal" || goto :err

echo.
echo Packaged: %OUT%
for %%I in ("%OUT%") do echo Size: %%~zI bytes
echo.
exit /b 0

:err
echo PACKAGE FAILED.
exit /b 1
