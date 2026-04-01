#!/usr/bin/env python3
"""
Test con SSL fix para resolver error de certificado
"""

import os
import sys
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Añadir directorio backend al path
backend_dir = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, backend_dir)

def main():
    """Test con SSL fix"""
    print("🚀 Test Bot de Registro de Citas - SSL Fix")
    print("=" * 50)
    
    # Configuración con SSL fix
    config = {
        'REGISTRO_CITA_USE_REAL_BROWSER': 'false',
        'REGISTRO_CITA_HEADLESS': 'false',
        'REGISTRO_CITA_SKIP_WIZARD': 'true',
        'REGISTRO_CITA_STEALTH': 'true',
        'REGISTRO_CITA_IGNORE_HTTPS_ERRORS': 'true',  # 👈 Ignorar errores SSL
        'REGISTRO_CITA_TIMEOUT_MS': '120000',
        'REGISTRO_CITA_POST_GOTO_MS': '8000',
    }
    
    # Aplicar configuración
    for key, value in config.items():
        os.environ[key] = value
    
    print("🔧 Configuración:")
    print("  - SSL: Ignorar errores de certificado")
    print("  - Wizard: Saltado (directo al formulario)")
    print("  - Navegador: Playwright normal")
    print("  - Modo: Visible (headless=false)")
    print("  - Stealth: playwright-stealth corregido")
    print()
    
    # Verificar stealth
    try:
        from playwright_stealth import Stealth
        print("✅ playwright-stealth: Stealth importado")
    except ImportError as e:
        print(f"❌ playwright-stealth: {e}")
        return
    
    try:
        from app.utils.tasks.registro_cita import registro_cita, STEALTH_AVAILABLE
        print(f"✅ registro_cita importado")
        print(f"🛡️ STEALTH_AVAILABLE: {STEALTH_AVAILABLE}")
        print()
        
        print("🚀 Ejecutando bot con SSL fix...")
        print("✨ Solución aplicada:")
        print("  🔓 Ignorar errores de certificado SSL")
        print("  🎯 Ir directo al formulario de citas")
        print("  📸 Capturar screenshots del proceso")
        print()
        
        result = registro_cita()
        print(f"✅ Bot completado: {result}")
        
        if result:
            print("🎉 ¡ÉXITO! El bot completó el proceso")
            print("📸 Revisa los screenshots guardados")
        else:
            print("⚠️ Bot ejecutado pero sin éxito")
            print("📸 Los screenshots mostrarán qué pasó")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
