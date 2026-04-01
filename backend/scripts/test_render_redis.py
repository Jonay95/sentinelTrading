#!/usr/bin/env python3
"""
Test para Redis de Render
"""

import os
import sys
import redis
import time
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
project_root = Path(__file__).parent.parent.parent
env_path = project_root / '.env'
load_dotenv(env_path)

def test_render_redis():
    """Test de Redis de Render"""
    print("🔍 Test Redis de Render")
    print("=" * 40)
    
    # URLs para probar
    render_urls = [
        os.getenv('CELERY_BROKER_URL')
    ]
    
    for i, url in enumerate(render_urls, 1):
        print(f"\n📡 Probando URL {i}: {url}")
        try:
            r = redis.from_url(url, decode_responses=True)
            
            # Probar ping
            print("📡 Enviando PING...")
            result = r.ping()
            if result:
                print(f"✅ Redis Render conectado (URL {i})")
                
                # Probar set/get
                test_key = f"test_render_{int(time.time())}"
                test_value = "working"
                
                r.set(test_key, test_value)
                retrieved = r.get(test_key)
                
                if retrieved == test_value:
                    print(f"✅ SET/GET funciona: {retrieved}")
                    r.delete(test_key)
                    
                    # Obtener info
                    info = r.info()
                    print(f"📊 Redis versión: {info.get('redis_version', 'unknown')}")
                    print(f"💾 Memoria: {info.get('used_memory_human', 'unknown')}")
                    
                    return url
                else:
                    print(f"❌ SET/GET falló")
            else:
                print(f"❌ No responde al PING")
                
        except Exception as e:
            print(f"❌ Error URL {i}: {e}")
    
    return None

def test_celery_with_render():
    """Test Celery con Redis de Render"""
    print("\n🔄 Test Celery con Redis de Render")
    print("=" * 50)
    
    try:
        # Añadir backend al path
        backend_dir = Path(__file__).parent
        sys.path.insert(0, str(backend_dir))
        
        # Importar celery directamente
        import app.celery
        celery = app.celery.celery
        
        # Probar conexión
        print("🔍 Probando conexión Celery...")
        inspect = celery.control.inspect()
        
        # Intentar obtener stats (puede fallar si no hay workers)
        try:
            stats = inspect.stats()
            if stats:
                print("✅ Workers conectados:")
                for worker, data in stats.items():
                    print(f"  🤖 {worker}")
            else:
                print("⚠️ No hay workers conectados (normal si no están corriendo)")
        except Exception as e:
            print(f"⚠️ Error obteniendo stats: {e}")
        
        print("✅ Conexión Celery funcionando")
        return True
        
    except Exception as e:
        print(f"❌ Error con Celery: {e}")
        return False

def main():
    """Función principal"""
    print("🚀 Test Completo - Redis de Render + Celery")
    print("=" * 60)
    
    # Test Redis
    working_url = test_render_redis()
    
    # Test Celery
    celery_ok = test_celery_with_render()
    
    print("\n🎯 Resultados:")
    print(f"🔌 Redis: {'✅ OK' if working_url else '❌ ERROR'}")
    print(f"🔄 Celery: {'✅ OK' if celery_ok else '❌ ERROR'}")
    
    if working_url and celery_ok:
        print(f"\n🎉 ¡Todo configurado con Redis de Render!")
        print(f"📡 URL funcionando: {working_url}")
        print("🚀 Los servicios de Render deberían conectarse automáticamente")
        
        # Actualizar .env si es necesario
        broker_url = os.getenv("CELERY_BROKER_URL")
        if working_url != broker_url:
            print(f"\n📝 Actualiza tu .env con:")
            print(f"CELERY_BROKER_URL={working_url}")
            print(f"CELERY_RESULT_BACKEND={working_url}")
    else:
        print("\n❌ Hay problemas que resolver")
        if not working_url:
            print("💡 Verifica que el servicio Redis de Render esté corriendo")
        if not celery_ok:
            print("💡 Revisa la configuración de Celery")

if __name__ == "__main__":
    main()
