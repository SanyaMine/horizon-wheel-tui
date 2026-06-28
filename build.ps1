# build.ps1 — build the standalone Windows executable(s) with PyInstaller.
#
# Usage:
#   .\build.ps1                 # build both: standalone .exe + portable .zip
#   .\build.ps1 -Target exe     # single-file dist\horizon-wheel-tui.exe only
#   .\build.ps1 -Target zip     # portable dist\horizon-wheel-tui-portable.zip only
#   .\build.ps1 -Clean          # remove build/ and dist/ first
#
# Outputs (in dist\):
#   horizon-wheel-tui.exe           — standalone single-file executable
#   horizon-wheel-tui-portable.zip  — portable folder build (extract and run the .exe inside)
#
# Note: PyInstaller logs progress to stderr — that is normal, not an error.
# Success/failure is determined by exit codes, not by stderr output.

param(
    [ValidateSet("exe", "zip", "all")]
    [string]$Target = "all",
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

$artifacts = @()

# ── Standalone single-file executable ────────────────────────────────────────
if ($Target -eq "exe" -or $Target -eq "all") {
    Write-Host "Building standalone executable (single file)..." -ForegroundColor Cyan
    python -m PyInstaller `
        --onefile `
        --name horizon-wheel-tui `
        --collect-all textual `
        --console `
        --noconfirm `
        --distpath dist `
        --workpath build `
        main.py

    $exePath = "dist\horizon-wheel-tui.exe"
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $exePath)) {
        Write-Host "Standalone build failed (exit code $LASTEXITCODE)." -ForegroundColor Red
        exit 1
    }
    $artifacts += $exePath
}

# ── Portable folder build, zipped ────────────────────────────────────────────
if ($Target -eq "zip" -or $Target -eq "all") {
    Write-Host "Building portable folder build (zip)..." -ForegroundColor Cyan
    python -m PyInstaller `
        --onedir `
        --name horizon-wheel-tui `
        --collect-all textual `
        --console `
        --noconfirm `
        --distpath dist\portable `
        --workpath build `
        main.py

    $portableDir = "dist\portable\horizon-wheel-tui"
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $portableDir)) {
        Write-Host "Portable build failed (exit code $LASTEXITCODE)." -ForegroundColor Red
        exit 1
    }

    $zipPath = "dist\horizon-wheel-tui-portable.zip"
    Remove-Item -Force $zipPath -ErrorAction SilentlyContinue

    # Use .NET ZipFile (includeBaseDirectory=$true keeps the top-level folder in the archive),
    # with a short retry: antivirus may briefly lock freshly-written files after the build.
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $srcDir = (Resolve-Path $portableDir).Path
    $dstZip = Join-Path (Resolve-Path "dist").Path "horizon-wheel-tui-portable.zip"
    $zipped = $false
    foreach ($attempt in 1..5) {
        try {
            [System.IO.Compression.ZipFile]::CreateFromDirectory(
                $srcDir, $dstZip, [System.IO.Compression.CompressionLevel]::Optimal, $true)
            $zipped = $true
            break
        } catch {
            Write-Host "  zip attempt $attempt failed (file lock?), retrying..." -ForegroundColor Yellow
            Start-Sleep -Seconds 2
        }
    }
    if (-not $zipped) { Write-Host "Failed to create portable zip." -ForegroundColor Red; exit 1 }
    $artifacts += $zipPath
}

# ── Summary ──────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Build complete:" -ForegroundColor Green
foreach ($a in $artifacts) {
    $sizeMB = [math]::Round((Get-Item $a).Length / 1MB, 1)
    Write-Host "  $a ($sizeMB MB)" -ForegroundColor Green
}
