#!/usr/bin/env python3
"""
Test URLs alternativas para Redis de Render
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

def test_alternative_urls():
    """Probar URLs alternativas de Render"""
    print("🔍 Test URLs Alternativas - Redis Render")
    print("=" * 50)
    
    # URLs alternativas a probar
    alternative_urls = [
        # URLs externas posibles
        "redis://sentinel-redis.onrender.com:6379/0",
        "redis://sentinel-redis.onrender.com:6379",
        
        # URLs internas con dominio completo
        "redis://red-d75rbl0ule4c73d0mjog.a.render.com:6379/0",
        "redis://red-d75rbl0ule4c73d0mjog.a.render.com:6379",
        
        # URLs con subdominio diferente
        "redis://red-d75rbl0ule4c73d0mjog.render.com:6379/0",
        "redis://red-d75rbl0ule4c73d0mjog.render.com:6379",
        
        # URLs con puerto diferente
        "redis://red-d75rbl0ule4c73d0mjog:6380/0",
        "redis://red-d75rbl0ule4c73d0mjog:6380",
    ]
    
    for i, url in enumerate(alternative_urls, 1):
        print(f"\n📡 Probando URL {i}: {url}")
        try:
            r = redis.from_url(url, decode_responses=True, socket_timeout=5)
            
            # Probar ping con timeout
            print("📡 Enviando PING...")
            result = r.ping()
            if result:
                print(f"✅ ¡ÉXITO! URL {i} funciona")
                
                # Probar set/get rápido
                test_key = f"test_{int(time.time())}"
                r.set(test_key, "ok")
                value = r.get(test_key)
                r.delete(test_key)
                
                if value == "ok":
                    print(f"✅ SET/GET funciona")
                    
                    # Obtener info básica
                    try:
                        info = r.info()
                        print(f"📊 Redis versión: {info.get('redis_version', 'unknown')}")
                    except:
                        pass
                    
                    return url
                else:
                    print(f"❌ SET/GET falló")
            else:
                print(f"❌ No responde al PING")
                
        except redis.ConnectionError as e:
            print(f"❌ Error de conexión: {e}")
        except redis.TimeoutError:
            print(f"❌ Timeout (probablemente incorrecta)")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    return None

def test_local_redis():
    """Probar Redis local como fallback"""
    print("\n🔍 Test Redis Local (Fallback)")
    print("=" * 40)
    
    try:
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)
        result = r.ping()
        if result:
            print("✅ Redis local funciona")
            return "redis://localhost:6379/0"
        else:
            print("❌ Redis local no responde")
    except Exception as e:
        print(f"❌ Redis local error: {e}")
    
    return None

def main():
    """Función principal"""
    print("🚀 Test Completo - Redis URLs Alternativas")
    print("=" * 60)
    
    # Probar URLs alternativas
    working_url = test_alternative_urls()
    
    # Si nada funciona, probar local
    if not working_url:
        working_url = test_local_redis()
    
    print("\n🎯 Resultado Final:")
    if working_url:
        print(f"✅ URL funcionando: {working_url}")
        print("\n📝 Actualiza tu .env con:")
        print(f"CELERY_BROKER_URL={working_url}")
        print(f"CELERY_RESULT_BACKEND={working_url}")
        print("\n🚀 Luego prueba el bot:")
        print("python backend/scripts/test_formulario_completo.py")
    else:
        print("❌ Ninguna URL funcionó")
        print("\n💡 Opciones:")
        print("1. Obtén la URL correcta de Render Dashboard")
        print("2. Inicia Redis local: redis-server")
        print("3. Usa un servicio Redis externo")

if __name__ == "__main__":
    main()
