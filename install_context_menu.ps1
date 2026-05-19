# WhisperTyper - Install Right-Click Context Menu
# Adds "Open WhisperTyper" to the right-click menu on desktop and folder backgrounds.
# No admin rights required (writes to HKCU).

$ErrorActionPreference = "Stop"

$exePath = Join-Path $PSScriptRoot "WhisperTyper.exe"
if (-not (Test-Path $exePath)) {
    Write-Host "[ERROR] WhisperTyper.exe not found at: $exePath" -ForegroundColor Red
    Write-Host "        Run this script from the WhisperTyper folder." -ForegroundColor Red
    exit 1
}

$menuName  = "WhisperTyper"
$menuLabel = "Open WhisperTyper"
$command   = "`"$exePath`""

# Right-click on folder / desktop background
$bgBase = "HKCU:\Software\Classes\Directory\Background\shell\$menuName"
New-Item -Path "$bgBase"          -Force | Out-Null
New-Item -Path "$bgBase\command"  -Force | Out-Null
Set-ItemProperty -Path $bgBase           -Name "(Default)" -Value $menuLabel
Set-ItemProperty -Path $bgBase           -Name "Icon"      -Value $exePath
Set-ItemProperty -Path "$bgBase\command" -Name "(Default)" -Value $command

Write-Host "[OK] Context menu installed." -ForegroundColor Green
Write-Host "     Right-click any folder or the desktop to find '$menuLabel'."
Write-Host ""
Write-Host "To remove: run uninstall_context_menu.ps1"
