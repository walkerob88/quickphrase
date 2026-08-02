# Builds a standalone QuickPhrase.exe (no Python needed to run it).
# Run from the project folder (the one containing quickphrase.spec):
#   powershell -ExecutionPolicy Bypass -File .\build_windows.ps1
# Output: dist\QuickPhrase.exe

$ErrorActionPreference = "Stop"

python -m pip install --upgrade pyinstaller | Out-Null
python -m PyInstaller quickphrase.spec --noconfirm

if (Test-Path "dist\QuickPhrase.exe") {
    Write-Host "`nDone: dist\QuickPhrase.exe" -ForegroundColor Green
    Write-Host "Share that single file - it runs on any 64-bit Windows 10/11 PC."
} else {
    Write-Host "Build finished but dist\QuickPhrase.exe not found - check output above." -ForegroundColor Red
}
