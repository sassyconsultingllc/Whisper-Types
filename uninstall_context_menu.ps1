# WhisperTyper - Uninstall Right-Click Context Menu

$menuName = "WhisperTyper"
$bgBase   = "HKCU:\Software\Classes\Directory\Background\shell\$menuName"

if (Test-Path $bgBase) {
    Remove-Item -Path $bgBase -Recurse -Force
    Write-Host "[OK] Context menu removed." -ForegroundColor Green
} else {
    Write-Host "[INFO] Context menu entry not found (already removed)." -ForegroundColor Yellow
}
