param(
    [string]$PackageName = "Materials-DMP-Portable"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $repoRoot "venv\Scripts\python.exe"
$frontendRoot = Join-Path $repoRoot "frontend"
$runtimeRoot = Join-Path $repoRoot ".runtime\portable-build"
$distRoot = Join-Path $runtimeRoot "dist"
$workRoot = Join-Path $runtimeRoot "work"
$specRoot = Join-Path $runtimeRoot "spec"
$releaseRoot = Join-Path $repoRoot "release"
$packageRoot = Join-Path $releaseRoot $PackageName
$zipPath = "$packageRoot.zip"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Project Python was not found: $python"
}
if (Test-Path -LiteralPath $packageRoot) {
    throw "Refusing to overwrite existing package: $packageRoot"
}
if (Test-Path -LiteralPath $zipPath) {
    throw "Refusing to overwrite existing archive: $zipPath"
}

Push-Location $frontendRoot
try {
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed with exit code $LASTEXITCODE" }
} finally {
    Pop-Location
}

New-Item -ItemType Directory -Path $distRoot, $workRoot, $specRoot, $releaseRoot -Force | Out-Null

& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --name MaterialsDMP `
    --paths (Join-Path $repoRoot "backend") `
    --hidden-import aiosqlite `
    --hidden-import passlib.handlers.bcrypt `
    --hidden-import sqlalchemy.dialects.sqlite.aiosqlite `
    --collect-submodules app `
    --collect-submodules scripts `
    --distpath $distRoot `
    --workpath $workRoot `
    --specpath $specRoot `
    (Join-Path $repoRoot "backend\portable_entry.py")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }

$builtApp = Join-Path $distRoot "MaterialsDMP"
$pythonBase = (& $python -c "import sys; print(sys.base_prefix)").Trim()
$runtimeBin = Join-Path $pythonBase "Library\bin"
foreach ($runtimeDll in @("ffi.dll", "sqlite3.dll")) {
    $sourceDll = Join-Path $runtimeBin $runtimeDll
    if (-not (Test-Path -LiteralPath $sourceDll)) {
        throw "Required Python runtime DLL was not found: $sourceDll"
    }
    Copy-Item -LiteralPath $sourceDll -Destination (Join-Path $builtApp "_internal")
}

Copy-Item -LiteralPath $builtApp -Destination $packageRoot -Recurse
Copy-Item -LiteralPath (Join-Path $frontendRoot "dist") -Destination (Join-Path $packageRoot "web") -Recurse
Copy-Item -LiteralPath (Join-Path $repoRoot "portable\Start-Materials-DMP.bat") -Destination $packageRoot
Copy-Item -LiteralPath (Join-Path $repoRoot "portable\Stop-Materials-DMP.bat") -Destination $packageRoot
Copy-Item -LiteralPath (Join-Path $repoRoot "portable\LLM_CONFIG.env") -Destination $packageRoot
Copy-Item -LiteralPath (Join-Path $repoRoot "portable\README-PORTABLE.txt") -Destination $packageRoot
New-Item -ItemType Directory -Path (Join-Path $packageRoot "data") | Out-Null

Compress-Archive -Path (Join-Path $packageRoot "*") -DestinationPath $zipPath -CompressionLevel Optimal

$packageSize = (Get-ChildItem -LiteralPath $packageRoot -File -Recurse | Measure-Object Length -Sum).Sum
$archiveSize = (Get-Item -LiteralPath $zipPath).Length
Write-Output "Portable folder: $packageRoot"
Write-Output "Portable folder bytes: $packageSize"
Write-Output "Portable archive: $zipPath"
Write-Output "Portable archive bytes: $archiveSize"
