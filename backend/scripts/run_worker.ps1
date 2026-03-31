# backend/scripts/run_worker.ps1
# Script para ejecutar Celery worker en Windows

Write-Host "Iniciando worker Celery (Playwright)..."

# Ruta actual (backend/scripts)
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path

# Subir a backend
$projectRoot = Resolve-Path "$scriptPath\.."

Write-Host "Project root: $projectRoot"

# Activar entorno virtual
$venvPath = "$projectRoot\venv\Scripts\Activate.ps1"
& $venvPath

# Ir a backend
Set-Location "$projectRoot"

# PYTHONPATH
$env:PYTHONPATH = "$projectRoot"

Write-Host "PYTHONPATH=$env:PYTHONPATH"

# Lanzar Celery
celery -A app.celery worker `
  --loglevel=info `
  --concurrency=1 `
  --pool=solo `
  --hostname=worker_local