# backend/scripts/run_worker.ps1
# Script para ejecutar Celery worker en Windows (PowerShell)
# Compatible con Playwright + estructura backend/app

Write-Host "🚀 Iniciando worker Celery (Playwright)..."

# Obtener ruta del proyecto (sube 2 niveles desde /scripts)
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Resolve-Path "$scriptPath\.."

Write-Host "📂 Project root: $projectRoot"

# Activar entorno virtual
$venvPath = "$projectRoot\venv\Scripts\Activate.ps1"
& $venvPath

# Ir al backend
Set-Location "$projectRoot"

# Configurar PYTHONPATH
$env:PYTHONPATH = "$projectRoot"

Write-Host "🐍 PYTHONPATH=$env:PYTHONPATH"

# Lanzar worker Celery
celery -A app.celery worker `
  --loglevel=info `
  --concurrency=1 `
  --pool=solo `
  --hostname=worker_local@%COMPUTERNAME%