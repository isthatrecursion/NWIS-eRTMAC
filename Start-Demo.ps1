param([int]$Port = 8765, [switch]$Rebuild)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$pythonPath = Join-Path $projectRoot 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    & (Join-Path $projectRoot 'Prepare-Offline.ps1') -InstallFromCache
    if ($LASTEXITCODE -ne 0) { throw 'Offline environment setup failed.' }
}
if ($Rebuild -or -not (Test-Path -LiteralPath (Join-Path $projectRoot 'frontend\dist\index.html'))) {
    Push-Location (Join-Path $projectRoot 'frontend')
    try {
        $env:VITE_API_BASE_URL = ''
        & npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    } finally { Pop-Location }
}
$demoRoot = Join-Path $projectRoot 'storage\demo'
New-Item -ItemType Directory -Path $demoRoot -Force | Out-Null
$dbFile = Join-Path $demoRoot 'nwis-demo.db'
$env:NWIS_DATABASE_URL = 'sqlite+pysqlite:///' + $dbFile.Replace('\','/')
$env:NWIS_DATA_ROOT = $demoRoot
$env:NWIS_DEMO_MODE = 'true'
$env:NWIS_SERVE_FRONTEND = 'true'
$env:NWIS_CORS_ORIGINS = "http://127.0.0.1:$Port"
Push-Location (Join-Path $projectRoot 'backend')
try {
    & $pythonPath -m app.seed_demo
    if ($LASTEXITCODE -ne 0) { throw 'Demo seed failed.' }
    Write-Host "Offline local demo: http://127.0.0.1:$Port/#brief  (Ctrl+C stops the server)"
    & $pythonPath -m uvicorn app.main:app --host 127.0.0.1 --port $Port --workers 1
} finally { Pop-Location }
