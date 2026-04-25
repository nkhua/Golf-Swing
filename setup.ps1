Set-StrictMode -Version Latest

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $repoRoot

Write-Host '=== Golf Swing Setup ==='

if (-Not (Test-Path 'backend\venv')) {
    Write-Host 'Creating backend Python virtual environment...'
    python -m venv backend\venv
} else {
    Write-Host 'Backend virtual environment already exists.'
}

Write-Host 'Activating backend virtual environment...'
$activatePath = Join-Path $repoRoot 'backend\venv\Scripts\Activate.ps1'
if (Test-Path $activatePath) {
    . $activatePath
} else {
    Write-Warning "Could not find activation script at $activatePath. Please activate manually."
}

Write-Host 'Installing backend dependencies...'
pip install --upgrade pip
pip install -r backend\requirements.txt

Write-Host 'Installing mobile dependencies...'
npm install --prefix mobile

Write-Host 'Setup complete. To run the backend, activate the venv and start uvicorn:'
Write-Host '  cd backend'
Write-Host '  .\\venv\\Scripts\\Activate.ps1'
Write-Host '  uvicorn main:app --reload --host 0.0.0.0 --port 8000'
