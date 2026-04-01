#!/usr/bin/env python3
"""
Script para iniciar el bot de citas con Celery
Ejecuta el worker y el beat para tareas periódicas
"""

import os
import sys
import subprocess
import time
import signal
from pathlib import Path

# Añadir directorio backend al path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

def print_banner():
    """Muestra banner de inicio"""
    print("🚀 Bot de Registro de Citas - Modo Automático")
    print("=" * 60)
    print("📋 Configuración:")
    print("  🔄 Tarea: registro_cita cada 2 minutos")
    print("  📧 Worker: Celery con Redis")
    print("  ⏰ Scheduler: Celery Beat")
    print("  📧 Email: Notificaciones automáticas")
    print("  🛡️ Stealth: playwright-stealth activado")
    print("  📍 Provincia: Barcelona")
    print("=" * 60)

def check_redis():
    """Verifica si Redis está corriendo"""
    try:
        import redis
        redis_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
        r = redis.from_url(redis_url)
        r.ping()
        print("✅ Redis conectado correctamente")
        return True
    except Exception as e:
        print(f"❌ Error conectando a Redis: {e}")
        print("💡 Inicia Redis: redis-server")
        return False

def start_celery_worker():
    """Inicia el worker de Celery"""
    print("🔄 Iniciando Celery Worker...")
    
    cmd = [
        sys.executable, "-m", "celery", 
        "-A", "app.celery",
        "worker",
        "--loglevel=info",
        "--concurrency=1",  # Un worker es suficiente
        "--without-gossip",
        "--without-mingle",
        "--without-heartbeat"
    ]
    
    try:
        process = subprocess.Popen(cmd, cwd=backend_dir)
        print(f"✅ Worker iniciado (PID: {process.pid})")
        return process
    except Exception as e:
        print(f"❌ Error iniciando worker: {e}")
        return None

def start_celery_beat():
    """Inicia el scheduler de Celery"""
    print("⏰ Iniciando Celery Beat...")
    
    cmd = [
        sys.executable, "-m", "celery",
        "-A", "app.celery", 
        "beat",
        "--loglevel=info",
        "--pidfile=celerybeat.pid"
    ]
    
    try:
        process = subprocess.Popen(cmd, cwd=backend_dir)
        print(f"✅ Beat iniciado (PID: {process.pid})")
        return process
    except Exception as e:
        print(f"❌ Error iniciando beat: {e}")
        return None

def cleanup():
    """Limpia procesos al salir"""
    print("\n🧹 Limpiando procesos...")
    
    # Matar worker
    try:
        subprocess.run(["pkill", "-f", "celery worker"], check=False)
    except:
        pass
    
    # Matar beat
    try:
        subprocess.run(["pkill", "-f", "celery beat"], check=False)
    except:
        pass
    
    # Limpiar PID file
    try:
        os.remove("celerybeat.pid")
    except:
        pass
    
    print("✅ Limpieza completada")

def main():
    """Función principal"""
    print_banner()
    
    # Verificar Redis
    if not check_redis():
        print("❌ Redis no está disponible. Inicia Redis primero:")
        print("   redis-server")
        return
    
    # Configurar signal handlers
    def signal_handler(signum, frame):
        cleanup()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Iniciar procesos
    worker_process = start_celery_worker()
    beat_process = start_celery_beat()
    
    if not worker_process or not beat_process:
        print("❌ No se pudieron iniciar los procesos")
        cleanup()
        return
    
    print("\n🎉 Bot de citas iniciado correctamente!")
    print("📊 El bot se ejecutará cada 2 minutos")
    print("📧 Revisa los logs para ver el progreso")
    print("🔍 Presiona Ctrl+C para detener")
    print("=" * 60)
    
    try:
        # Mantener el script corriendo
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        cleanup()

if __name__ == "__main__":
    main()
