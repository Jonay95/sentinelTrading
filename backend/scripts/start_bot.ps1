# Script para iniciar el bot de citas en Windows PowerShell
# Ejecuta el worker y beat de Celery para tareas automáticas

Write-Host "🚀 Bot de Registro de Citas - Modo Automático" -ForegroundColor Green
Write-Host "=" * 60 -ForegroundColor Green

# Verificar si estamos en el venv
if (-not $env:VIRTUAL_ENV) {
    Write-Host "❌ Error: No estás en el entorno virtual" -ForegroundColor Red
    Write-Host "💡 Activa el venv primero:" -ForegroundColor Yellow
    Write-Host "   .\venv\Scripts\Activate" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ Entorno virtual detectado: $env:VIRTUAL_ENV" -ForegroundColor Green

# Verificar Redis
try {
    $redisTest = Test-NetConnection -ComputerName localhost -Port 6379 -WarningAction SilentlyContinue
    if ($redisTest.TcpTestSucceeded) {
        Write-Host "✅ Redis conectado correctamente" -ForegroundColor Green
    } else {
        Write-Host "❌ Redis no está disponible" -ForegroundColor Red
        Write-Host "💡 Inicia Redis primero:" -ForegroundColor Yellow
        Write-Host "   redis-server" -ForegroundColor Yellow
        exit 1
    }
} catch {
    Write-Host "❌ Error verificando Redis" -ForegroundColor Red
    exit 1
}

# Configurar variables de entorno
$env:PYTHONPATH = (Get-Location).Path
Write-Host "🔧 PYTHONPATH configurado" -ForegroundColor Green

Write-Host "🔄 Iniciando Celery Worker..." -ForegroundColor Blue
$workerJob = Start-Job -ScriptBlock {
    python -m celery -A app.celery worker --loglevel=info --concurrency=1
} -Name "CitaBotWorker"

Write-Host "⏰ Iniciando Celery Beat..." -ForegroundColor Blue  
$beatJob = Start-Job -ScriptBlock {
    python -m celery -A app.celery beat --loglevel=info
} -Name "CitaBotBeat"

Write-Host ""
Write-Host "🎉 Bot de citas iniciado correctamente!" -ForegroundColor Green
Write-Host "📊 El bot se ejecutará cada 2 minutos" -ForegroundColor Green
Write-Host "📧 Revisa los logs para ver el progreso" -ForegroundColor Green
Write-Host "🔍 Presiona Ctrl+C para detener" -ForegroundColor Yellow
Write-Host "=" * 60 -ForegroundColor Green

# Función para limpiar procesos
function Cleanup {
    Write-Host "`n🧹 Deteniendo procesos..." -ForegroundColor Yellow
    
    Stop-Job -Name "CitaBotWorker" -Force 2>$null
    Stop-Job -Name "CitaBotBeat" -Force 2>$null
    Remove-Job -Name "CitaBotWorker" -Force 2>$null
    Remove-Job -Name "CitaBotBeat" -Force 2>$null
    
    # Matar procesos celery si siguen corriendo
    Get-Process | Where-Object {$_.ProcessName -like "*celery*"} | Stop-Process -Force 2>$null
    
    Write-Host "✅ Procesos detenidos" -ForegroundColor Green
    exit 0
}

# Configurar Ctrl+C para limpiar
[Console]::TreatControlCAsInput = $true
try {
    while ($true) {
        Start-Sleep -Seconds 1
        
        # Mostrar estado de los jobs
        $workerState = (Get-Job -Name "CitaBotWorker").State
        $beatState = (Get-Job -Name "CitaBotBeat").State
        
        if ($workerState -eq "Failed" -or $beatState -eq "Failed") {
            Write-Host "❌ Los procesos fallaron" -ForegroundColor Red
            Cleanup
        }
    }
} catch [System.Management.Automation.HaltCommandException] {
    # Ctrl+C presionado
    Cleanup
} catch {
    Write-Host "❌ Error inesperado: $_" -ForegroundColor Red
    Cleanup
}
