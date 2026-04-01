#!/usr/bin/env python3
"""
Test para ejecutar tarea de Celery manualmente
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
project_root = Path(__file__).parent.parent.parent
env_path = project_root / '.env'
load_dotenv(env_path)

# Añadir directorio backend al path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

def test_celery_task():
    """Test ejecutar tarea de Celery"""
    print("🚀 Test Tarea de Celery")
    print("=" * 40)
    
    try:
        from app.celery import celery
        from app.utils.tasks.registro_cita import registro_cita
        
        print("✅ Celery importado correctamente")
        print("✅ Tarea registro_cita importada")
        
        # Ejecutar tarea directamente (sin .delay())
        print("\n🔄 Ejecutando tarea registro_cita directamente...")
        result = registro_cita()
        
        print(f"✅ Tarea completada: {result}")
        return True
        
    except Exception as e:
        print(f"❌ Error ejecutando tarea: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_celery_delay():
    """Test ejecutar tarea con .delay()"""
    print("\n🚀 Test Tarea con .delay()")
    print("=" * 40)
    
    try:
        from app.celery import celery
        from app.utils.tasks.registro_cita import registro_cita
        
        print("✅ Celery importado correctamente")
        
        # Verificar conexión con Redis
        print("\n🔍 Verificando conexión con Redis...")
        inspect = celery.control.inspect()
        
        try:
            stats = inspect.stats()
            if stats:
                print("✅ Workers conectados:")
                for worker, data in stats.items():
                    print(f"  🤖 {worker}")
            else:
                print("⚠️ No hay workers conectados")
        except Exception as e:
            print(f"⚠️ Error obteniendo stats: {e}")
        
        # Enviar tarea con delay
        print("\n📤 Enviando tarea con .delay()...")
        task_result = registro_cita.delay()
        
        print(f"✅ Tarea enviada: {task_result.id}")
        print(f"📊 Estado: {task_result.status}")
        
        # Esperar resultado (opcional)
        print("\n⏳ Esperando resultado (10 segundos)...")
        import time
        
        for i in range(10):
            task_result.refresh()
            print(f"📊 Intento {i+1}/10 - Estado: {task_result.status}")
            
            if task_result.ready():
                print(f"✅ Tarea completada: {task_result.result}")
                break
            elif task_result.failed():
                print(f"❌ Tarea fallida: {task_result.result}")
                break
                
            time.sleep(1)
        
        return True
        
    except Exception as e:
        print(f"❌ Error con .delay(): {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Función principal"""
    print("🚀 Test Completo de Tareas Celery")
    print("=" * 50)
    
    # Test 1: Ejecución directa
    print("📋 Test 1: Ejecución directa de la tarea")
    direct_success = test_celery_task()
    
    # Test 2: Ejecución con delay
    print("\n📋 Test 2: Ejecución con .delay()")
    delay_success = test_celery_delay()
    
    print("\n🎯 Resultados:")
    print(f"🔄 Ejecución directa: {'✅ OK' if direct_success else '❌ ERROR'}")
    print(f"📤 Ejecución con delay: {'✅ OK' if delay_success else '❌ ERROR'}")
    
    if direct_success and delay_success:
        print("\n🎉 ¡Celery funcionando perfectamente!")
        print("🚀 Los workers de Render deberían procesar tareas automáticamente")
    else:
        print("\n❌ Hay problemas con Celery")
        print("💡 Verifica:")
        print("   - Conexión con Redis")
        print("   - Workers corriendo en Render")
        print("   - Configuración de Celery")

if __name__ == "__main__":
    main()
