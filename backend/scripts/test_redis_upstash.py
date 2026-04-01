#!/usr/bin/env python3
"""
Script para probar la conexión con Redis de Upstash
"""

import os
import sys
import redis
import time
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno (desde el directorio raíz)
project_root = Path(__file__).parent.parent.parent
env_path = project_root / '.env'
load_dotenv(env_path)

# Añadir directorio backend al path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

def test_redis_connection():
    """Prueba la conexión con Redis de Upstash"""
    print("🔍 Probando conexión con Redis de Upstash...")
    print("=" * 50)
    
    # Obtener configuración
    broker_url = os.getenv("CELERY_BROKER_URL")
    backend_url = os.getenv("CELERY_RESULT_BACKEND")
    use_ssl = os.getenv("CELERY_BROKER_USE_SSL", "true").lower() in ("1", "true", "yes")
    
    print(f"📡 Broker URL: {broker_url}")
    print(f"🔐 SSL Activo: {use_ssl}")
    print()
    
    if not broker_url:
        print("❌ CELERY_BROKER_URL no configurado")
        return False
    
    try:
        # Conectar a Redis con SSL correcto
        print("🔌 Conectando a Redis...")
        r = redis.from_url(broker_url)
        
        # Probar ping
        print("📡 Enviando PING...")
        result = r.ping()
        if result:
            print("✅ Redis conectado correctamente")
        else:
            print("❌ Redis no responde al PING")
            return False
        
        # Probar set/get
        print("💾 Probando SET/GET...")
        test_key = "test_sentinel_connection"
        test_value = "working_" + str(int(time.time()))
        
        r.set(test_key, test_value)
        retrieved = r.get(test_key)
        
        if retrieved and retrieved.decode() == test_value:
            print("✅ SET/GET funcionando correctamente")
            r.delete(test_key)
        else:
            print("❌ SET/GET falló")
            return False
        
        # Probar info
        print("📊 Obteniendo información del servidor...")
        info = r.info()
        print(f"📍 Servidor: {info.get('server', {}).get('redis_version', 'unknown')}")
        print(f"💾 Memoria usada: {info.get('used_memory_human', 'unknown')}")
        print(f"📈 Clientes conectados: {info.get('connected_clients', 'unknown')}")
        
        print("✅ Todas las pruebas pasaron correctamente")
        return True
        
    except Exception as e:
        print(f"❌ Error conectando a Redis: {e}")
        return False

def test_celery_connection():
    """Prueba la conexión con Celery"""
    print("\n🔄 Probando conexión con Celery...")
    print("=" * 50)
    
    try:
        from app.celery import celery
        
        # Probar inspect
        print("🔍 Probando Celery inspect...")
        inspect = celery.control.inspect()
        
        # Obtener stats
        print("📊 Obteniendo estadísticas...")
        stats = inspect.stats()
        
        if stats:
            print("✅ Workers conectados:")
            for worker_name, worker_stats in stats.items():
                print(f"  🤖 {worker_name}")
                print(f"     📦 Tareas: {worker_stats.get('total', 'unknown')}")
        else:
            print("⚠️ No hay workers conectados (normal si no están corriendo)")
        
        print("✅ Conexión con Celery funcionando")
        return True
        
    except Exception as e:
        print(f"❌ Error con Celery: {e}")
        return False

def main():
    """Función principal"""
    print("🚀 Test de Conexión - Redis Upstash + Celery")
    print("=" * 60)
    
    # Probar Redis
    redis_ok = test_redis_connection()
    
    # Probar Celery
    celery_ok = test_celery_connection()
    
    print("\n🎯 Resultados:")
    print(f"🔌 Redis: {'✅ OK' if redis_ok else '❌ ERROR'}")
    print(f"🔄 Celery: {'✅ OK' if celery_ok else '❌ ERROR'}")
    
    if redis_ok and celery_ok:
        print("\n🎉 ¡Todo configurado correctamente!")
        print("🚀 Puedes iniciar el bot:")
        print("   python scripts/start_cita_bot.py")
    else:
        print("\n❌ Hay problemas que resolver antes de iniciar el bot")
    
    return redis_ok and celery_ok

if __name__ == "__main__":
    import time
    main()
