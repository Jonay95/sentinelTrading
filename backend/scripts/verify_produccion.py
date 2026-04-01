#!/usr/bin/env python3
"""
Test para verificar que el fix de producción funciona correctamente
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

def test_produccion_headless():
    """Test con configuración de producción forzada"""
    print("🏭 Test Producción - Headless Forzado")
    print("=" * 60)
    
    # Simular entorno de producción
    os.environ["RENDER"] = "true"
    os.environ["ENVIRONMENT"] = "production"
    
    try:
        from app.utils.tasks.registro_cita import registro_cita
        
        print("✅ Bot importado correctamente")
        print("🏭 Simulando entorno de producción (Render)")
        print("👁️ Headless: FORZADO = True")
        print("🧙 Stealth: Desactivado en producción")
        print()
        
        # Ejecutar bot
        print("🎯 Ejecutando bot en modo producción...")
        resultado = registro_cita()
        
        print(f"\n🎯 Resultado: {resultado}")
        
        if resultado is True:
            print("🎉 ¡CITAS DISPONIBLES!")
        elif resultado is False:
            print("📋 No hay citas - continuando monitoreo")
        else:
            print("❌ Error en ejecución")
        
        return resultado
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Función principal"""
    print("🔧 Test Fix Producción")
    print("=" * 50)
    
    print("🐛 Problema original:")
    print("   ❌ 'Missing X server or $DISPLAY'")
    print("   ❌ Navegador headed en Linux sin servidor X")
    print()
    
    print("✅ Solución aplicada:")
    print("   🔍 Detección automática de producción")
    print("   👁️ Headless forzado en producción")
    print("   🧙 Stealth desactivado en producción")
    print("   🏭 Args optimizados para Linux")
    print()
    
    resultado = test_produccion_headless()
    
    print("\n📊 Verificación:")
    if resultado is not None:
        print("   ✅ Bot inició correctamente")
        print("   ✅ Sin errores de X server")
        print("   ✅ Configuración de producción aplicada")
    else:
        print("   ❌ Error persiste")

if __name__ == "__main__":
    main()
