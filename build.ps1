# build.ps1 — build the standalone Windows executable with PyInstaller.
#
# Usage:
#   .\build.ps1            # build dist\horizon-wheel-tui.exe
#   .\build.ps1 -Clean     # remove build/ and dist/ first
#
# Output: dist\horizon-wheel-tui.exe (single file, no Python install required).
#
# Note: PyInstaller logs progress to stderr — that is normal, not an error.
# Success/failure is determined by the exit code, not by stderr output.

param(
    [switch]$Clean
)

Set-Location $PSScriptRoot

# Ensure PyInstaller is available (exit code, not stderr, signals absence).
python -m PyInstaller --version | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "PyInstaller not found - installing..." -ForegroundColor Yellow
    python -m pip install pyinstaller
    if ($LASTEXITCODE -ne 0) { Write-Host "Failed to install PyInstaller." -ForegroundColor Red; exit 1 }
}

if ($Clean) {
    Write-Host "Cleaning build/ and dist/..." -ForegroundColor Cyan
    Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
}

Write-Host "Building horizon-wheel-tui.exe..." -ForegroundColor Cyan
python -m PyInstaller `
    --onefile `
    --name horizon-wheel-tui `
    --collect-all textual `
    --console `
    --noconfirm `
    main.py

$exePath = "dist\horizon-wheel-tui.exe"
if ($LASTEXITCODE -eq 0 -and (Test-Path $exePath)) {
    $sizeMB = [math]::Round((Get-Item $exePath).Length / 1MB, 1)
    Write-Host ""
    Write-Host "Done -> $exePath ($sizeMB MB)" -ForegroundColor Green
} else {
    Write-Host "Build failed (exit code $LASTEXITCODE)." -ForegroundColor Red
    exit 1
}
