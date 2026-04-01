#!/usr/bin/env python3
"""
Test simple para Redis Upstash
"""

import os
import sys
import redis
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
project_root = Path(__file__).parent.parent.parent
env_path = project_root / '.env'
load_dotenv(env_path)

def test_redis():
    """Test simple de Redis"""
    print("🔍 Test Simple Redis Upstash")
    print("=" * 40)
    
    # Probar diferentes URLs
    urls_to_test = [
        "redis://default:US1T3AIQGd8mM7QyU3Fh7qQ1pUv3Y2ZfW@nearby-pheasant-89010.upstash.io:6379",
        "rediss://default:US1T3AIQGd8mM7QyU3Fh7qQ1pUv3Y2ZfW@nearby-pheasant-89010.upstash.io:6379",
        "redis://default:US1T3AIQGd8mM7QyU3Fh7qQ1pUv3Y2ZfW@nearby-pheasant-89010.upstash.io:6379/0",
        "rediss://default:US1T3AIQGd8mM7QyU3Fh7qQ1pUv3Y2ZfW@nearby-pheasant-89010.upstash.io:6379/0",
    ]
    
    for i, url in enumerate(urls_to_test, 1):
        print(f"\n📡 Probando URL {i}: {url[:50]}...")
        try:
            r = redis.from_url(url)
            result = r.ping()
            if result:
                print(f"✅ URL {i} funciona correctamente")
                
                # Probar set/get
                r.set("test_key", "test_value")
                value = r.get("test_key")
                if value:
                    print(f"✅ SET/GET funciona: {value}")
                    r.delete("test_key")
                
                return url
            else:
                print(f"❌ URL {i} no responde")
        except Exception as e:
            print(f"❌ URL {i} error: {e}")
    
    return None

def main():
    """Función principal"""
    working_url = test_redis()
    
    if working_url:
        print(f"\n🎉 URL funcionando: {working_url}")
        print("📝 Actualiza tu .env con esta URL:")
        print(f"CELERY_BROKER_URL={working_url}")
        print(f"CELERY_RESULT_BACKEND={working_url}")
    else:
        print("\n❌ Ninguna URL funcionó")
        print("💡 Verifica tu token de Upstash")

if __name__ == "__main__":
    main()
