#!/usr/bin/env python3
"""
Test con URL interna de Render (probablemente no funcionará desde local)
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

def test_internal_render():
    """Test URL interna de Render"""
    print("🔍 Test URL Interna de Render")
    print("=" * 40)
    
    internal_url = "redis://red-d75rbl0ule4c73d0mjog:6379/0"
    
    print(f"📡 Probando: {internal_url}")
    print("⚠️  External traffic bloqueado - probablemente falle")
    
    try:
        r = redis.from_url(internal_url, decode_responses=True, socket_timeout=3)
        result = r.ping()
        
        if result:
            print("✅ ¡Sorpresa! Funciona desde local")
            return internal_url
        else:
            print("❌ No responde")
            
    except redis.ConnectionError as e:
        print(f"❌ Error de conexión (esperado): {e}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    return None

def main():
    """Función principal"""
    print("🚀 Test Redis Interno de Render")
    print("=" * 50)
    
    working_url = test_internal_render()
    
    if working_url:
        print(f"\n✅ URL funcionando: {working_url}")
        print("🎉 ¡External traffic está permitido!")
    else:
        print("\n❌ URL interna no funciona desde local")
        print("💡 Soluciones:")
        print("1. Permitir external traffic en Render (Networking → 0.0.0.0/0)")
        print("2. Usar Redis de Upstash con token real")
        print("3. Iniciar Redis local para pruebas")

if __name__ == "__main__":
    main()
