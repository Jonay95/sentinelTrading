#!/usr/bin/env python3
"""
Script rápido para probar el bot de registro de citas con configuración CLAVE
"""

import os
import sys
import logging

# Configurar logging para ver todo
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Añadir directorio backend al path
backend_dir = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, backend_dir)

def test_stealth():
    """Probar que playwright-stealk funciona"""
    try:
        from playwright_stealth import stealth  # 👈 CORREGIDO: stealth, no stealth_sync
        print("✅ playwright-stealth importado correctamente")
        return True
    except ImportError as e:
        print(f"❌ Error importando playwright-stealth: {e}")
        return False

def test_imports():
    """Probar todas las importaciones necesarias"""
    try:
        from app.utils.tasks.registro_cita import registro_cita, STEALTH_AVAILABLE
        print("✅ registro_cita importado correctamente")
        print(f"🛡️ STEALTH_AVAILABLE: {STEALTH_AVAILABLE}")
        return True
    except ImportError as e:
        print(f"❌ Error importando registro_cita: {e}")
        return False

def check_env():
    """Verificar configuración clave"""
    print("\n🔍 Verificando configuración CLAVE:")
    
    # 1. Headless debe ser False
    headless = os.getenv("REGISTRO_CITA_HEADLESS", "false").lower() in ("1", "true", "yes")
    if not headless:
        print("✅ REGISTRO_CITA_HEADLESS=false (correcto)")
    else:
        print("❌ REGISTRO_CITA_HEADLESS=true (debería ser false)")
    
    # 2. Datos obligatorios
    required_vars = ['REGISTRO_CITA_URL', 'REGISTRO_CITA_NIE', 'REGISTRO_CITA_NOMBRE']
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    
    if not missing:
        print("✅ Variables obligatorias configuradas")
    else:
        print(f"❌ Faltan variables: {missing}")
        print("📋 Configura en .env:")
        for var in missing:
            print(f"   {var}=valor")
    
    return len(missing) == 0

def main():
    """Función principal"""
    print("🚀 Test Rápido Bot de Registro de Citas")
    print("=" * 50)
    
    # 1. Probar stealth
    if not test_stealth():
        print("💣 CRÍTICO: playwright-stealth no funciona")
        return False
    
    # 2. Probar imports
    if not test_imports():
        print("💣 CRÍTICO: imports fallan")
        return False
    
    # 3. Verificar configuración
    if not check_env():
        print("💣 CRÍTICO: configuración incompleta")
        return False
    
    print("\n🎯 Todo configurado correctamente!")
    print("👀 Podrás ver el navegador funcionar")
    print("🛡️ playwright-stealth activado")
    print("📸 Screenshots automáticos")
    
    # Preguntar si ejecutar
    response = input("\n¿Ejecutar el bot ahora? (y/N): ").lower().strip()
    if response in ['y', 'yes']:
        try:
            from app.utils.tasks.registro_cita import registro_cita
            print("\n🚀 Ejecutando bot de registro de citas...")
            result = registro_cita()
            print(f"✅ Bot ejecutado: {result}")
        except Exception as e:
            print(f"❌ Error ejecutando bot: {e}")
            import traceback
            traceback.print_exc()
    
    return True

if __name__ == "__main__":
    main()
