#!/usr/bin/env python3
"""
Esperar y probar conexión a Redis de Render después de configurar external traffic
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

def test_render_connection():
    """Test conexión a Redis de Render"""
    url = "redis://red-d75rbl0ule4c73d0mjog:6379/0"
    
    print(f"📡 Probando conexión a: {url}")
    try:
        r = redis.from_url(url, decode_responses=True, socket_timeout=5)
        result = r.ping()
        
        if result:
            print("✅ ¡Conexión exitosa!")
            
            # Probar operaciones básicas
            test_key = f"render_test_{int(time.time())}"
            r.set(test_key, "working")
            value = r.get(test_key)
            r.delete(test_key)
            
            if value == "working":
                print("✅ Operaciones SET/GET funcionando")
                
                # Actualizar .env
                update_env_file(url)
                return True
            else:
                print("❌ SET/GET falló")
        else:
            print("❌ No responde al PING")
            
    except redis.ConnectionError as e:
        print(f"❌ Error de conexión: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    return False

def update_env_file(redis_url):
    """Actualizar archivo .env con URL funcionando"""
    try:
        # Leer .env actual
        env_lines = []
        if env_path.exists():
            with open(env_path, 'r', encoding='utf-8') as f:
                env_lines = f.readlines()
        
        # Actualizar o agregar URLs de Redis
        updated = False
        for i, line in enumerate(env_lines):
            if line.startswith('CELERY_BROKER_URL='):
                env_lines[i] = f'CELERY_BROKER_URL={redis_url}\n'
                updated = True
            elif line.startswith('CELERY_RESULT_BACKEND='):
                env_lines[i] = f'CELERY_RESULT_BACKEND={redis_url}\n'
                updated = True
        
        # Si no existían, agregarlas
        if not updated:
            env_lines.append(f'\nCELERY_BROKER_URL={redis_url}\n')
            env_lines.append(f'CELERY_RESULT_BACKEND={redis_url}\n')
        
        # Escribir archivo actualizado
        with open(env_path, 'w', encoding='utf-8') as f:
            f.writelines(env_lines)
        
        print(f"✅ .env actualizado con URL de Redis")
        return True
        
    except Exception as e:
        print(f"❌ Error actualizando .env: {e}")
        return False

def main():
    """Función principal - esperar y probar conexión"""
    print("🚀 Esperando Configuración de External Traffic - Render Redis")
    print("=" * 70)
    
    print("📋 Pasos que deberías haber completado:")
    print("1. ✅ Ir a Render Dashboard")
    print("2. ✅ Buscar servicio 'sentinel-redis'")
    print("3. ✅ Ir a pestaña 'Networking'")
    print("4. ✅ Agregar '0.0.0.0/0' en Inbound IP Restrictions")
    print("5. ✅ Guardar cambios")
    print()
    
    print("⏳ Esperando que se aplique la configuración...")
    print("🔄 Probando conexión cada 30 segundos...")
    print("🔍 Presiona Ctrl+C para detener")
    print()
    
    attempt = 0
    max_attempts = 20  # 10 minutos máximo
    
    try:
        while attempt < max_attempts:
            attempt += 1
            print(f"📡 Intento {attempt}/{max_attempts} - {time.strftime('%H:%M:%S')}")
            
            if test_render_connection():
                print("\n🎉 ¡ÉXITO! Redis de Render configurado")
                print("🚀 Ahora puedes ejecutar el bot:")
                print("   python backend/scripts/test_formulario_completo.py")
                break
            else:
                print("⏳ Esperando 30 segundos...")
                time.sleep(30)
        
        if attempt >= max_attempts:
            print("\n❌ Tiempo de espera agotado")
            print("💡 Verifica:")
            print("1. Que el external traffic esté configurado")
            print("2. Que el servicio Redis esté 'Deployed'")
            print("3. Que no haya errores en el dashboard")
    
    except KeyboardInterrupt:
        print("\n⏹️ Espera detenida por el usuario")
    
    print("\n📊 Estado actual:")
    print("🔗 Render Dashboard: https://dashboard.render.com/")
    print("🔍 Servicio: sentinel-redis")
    print("📡 URL: redis://red-d75rbl0ule4c73d0mjog:6379/0")

if __name__ == "__main__":
    main()
