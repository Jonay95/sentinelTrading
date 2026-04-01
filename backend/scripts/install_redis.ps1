# Script para instalar e iniciar Redis en Windows

Write-Host "🔧 Instalación de Redis para Bot de Citas" -ForegroundColor Green
Write-Host "=" * 50 -ForegroundColor Green

# Verificar si Redis ya está instalado
try {
    $redisVersion = redis-server --version 2>$null
    if ($redisVersion) {
        Write-Host "✅ Redis ya está instalado: $redisVersion" -ForegroundColor Green
    } else {
        Write-Host "❌ Redis no encontrado" -ForegroundColor Red
    }
} catch {
    Write-Host "❌ Redis no está instalado" -ForegroundColor Red
}

# Verificar si Chocolatey está instalado
try {
    $chocoVersion = choco --version 2>$null
    if ($chocoVersion) {
        Write-Host "✅ Chocolatey encontrado: $chocoVersion" -ForegroundColor Green
    } else {
        Write-Host "📦 Instalando Chocolatey..." -ForegroundColor Yellow
        Set-ExecutionPolicy Bypass -Scope Process -Force
        [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
        iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
    }
} catch {
    Write-Host "❌ Error verificando Chocolatey" -ForegroundColor Red
    exit 1
}

# Instalar Redis si no está
try {
    $redisTest = Get-Command redis-server -ErrorAction SilentlyContinue
    if (-not $redisTest) {
        Write-Host "📦 Instalando Redis..." -ForegroundColor Yellow
        choco install redis-64 -y
        Write-Host "✅ Redis instalado correctamente" -ForegroundColor Green
    }
} catch {
    Write-Host "❌ Error instalando Redis: $_" -ForegroundColor Red
    exit 1
}

# Iniciar Redis
Write-Host "🚀 Iniciando Redis..." -ForegroundColor Blue
try {
    Start-Process redis-server -WindowStyle Hidden
    Write-Host "✅ Redis iniciado correctamente" -ForegroundColor Green
    
    # Verificar que está corriendo
    Start-Sleep -Seconds 2
    $redisTest = Test-NetConnection -ComputerName localhost -Port 6379 -WarningAction SilentlyContinue
    if ($redisTest.TcpTestSucceeded) {
        Write-Host "✅ Redis verificado en puerto 6379" -ForegroundColor Green
    } else {
        Write-Host "❌ Redis no responde en puerto 6379" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "❌ Error iniciando Redis: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "🎉 Redis listo para el bot de citas!" -ForegroundColor Green
Write-Host "📊 Ahora puedes iniciar el bot:" -ForegroundColor Yellow
Write-Host "   .\scripts\start_bot.ps1" -ForegroundColor Cyan
Write-Host ""
