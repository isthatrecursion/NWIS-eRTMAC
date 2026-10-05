param([switch]$InstallFromCache)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$pythonPath = Join-Path $projectRoot 'backend\.venv\Scripts\python.exe'
$wheelRoot = Join-Path $projectRoot 'storage\packaging\wheels'
$lockPath = Join-Path $projectRoot 'backend\requirements.offline-lock.txt'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    $bootstrapPython = Join-Path $projectRoot 'storage\packaging\python\python.exe'
    if (-not (Test-Path -LiteralPath $bootstrapPython)) {
        $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
        if (-not $pythonCommand) { throw 'Python runtime missing. Include storage/packaging/python from the prepared offline package, or install Windows x64 Python 3.12.' }
        $bootstrapPython = $pythonCommand.Source
    }
    & $bootstrapPython -m venv (Join-Path $projectRoot 'backend\.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Python environment setup failed.' }
}
New-Item -ItemType Directory -Path $wheelRoot -Force | Out-Null
if (-not $InstallFromCache) {
    & $pythonPath -m pip download --only-binary=:all: --dest $wheelRoot -r $lockPath
    if ($LASTEXITCODE -ne 0) { throw 'Dependency cache incomplete; stay connected and resolve download errors before moving the package.' }
}
& $pythonPath -m pip install --no-index --find-links $wheelRoot -r $lockPath
if ($LASTEXITCODE -ne 0) { throw 'Offline dependency installation failed.' }
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'frontend\dist\index.html'))) { throw 'Include the built frontend/dist directory in the offline package; Node is needed only to rebuild.' }
Write-Host 'Offline Python cache installed. Start-Demo.ps1 serves the prebuilt frontend without npm or network access.'
