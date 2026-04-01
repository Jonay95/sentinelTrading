#!/usr/bin/env python3
"""
Test completo para rellenar el formulario con todos los campos
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
    """Test completo del formulario"""
    print("🚀 Test Formulario Completo - Bot de Citas")
    print("=" * 50)
    
    # Configuración completa para el formulario
    config = {
        'REGISTRO_CITA_USE_REAL_BROWSER': 'false',
        'REGISTRO_CITA_HEADLESS': 'false',
        'REGISTRO_CITA_SKIP_WIZARD': 'false',  # 👈 Activar wizard para provincias
        'REGISTRO_CITA_PROVINCIA': '/icpplustieb/citar?p=8&locale=es',  # Barcelona
        'REGISTRO_CITA_STEALTH': 'true',
        'REGISTRO_CITA_IGNORE_HTTPS_ERRORS': 'true',
        'REGISTRO_CITA_TIMEOUT_MS': '120000',
        'REGISTRO_CITA_POST_GOTO_MS': '8000',
        
        # 👈 Selectores exactos del HTML
        'REGISTRO_CITA_SEL_NIE': '#txtIdCitado',
        'REGISTRO_CITA_SEL_NOMBRE': '#txtDesCitado', 
        'REGISTRO_CITA_SEL_PAIS': '#txtPaisNac',
        
        # 👈 Valores exactos
        'REGISTRO_CITA_NIE': 'Y7223767X',
        'REGISTRO_CITA_NOMBRE': 'Jonay Gonzalez',
        'REGISTRO_CITA_PAIS': '248',  # Venezuela
    }
    
    # Aplicar configuración
    for key, value in config.items():
        os.environ[key] = value
    
    print("🔧 Configuración completa:")
    print("  - Provincia: Barcelona (p=8)")
    print("  - Wizard: Activado (selección automática)")
    print("  - NIE: Y7223767X")
    print("  - Nombre: Jonay Gonzalez")
    print("  - País: Venezuela (248)")
    print("  - Selectores: Exactos del HTML")
    print("  - SSL: Ignorar errores")
    print("  - Stealth: playwright-stealth activado")
    print()
    
    # Verificar imports
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
        
        print("🚀 Ejecutando bot con formulario completo...")
        print("✨ Proceso completo:")
        print("  1. 📍 Seleccionar provincia Barcelona")
        print("  2. 🎯 Completar wizard de trámites")
        print("  3. 📝 Rellenar formulario:")
        print("     - NIE: #txtIdCitado")
        print("     - Nombre: #txtDesCitado")
        print("     - País: #txtPaisNac (Venezuela)")
        print("  4. 🖱️ Hacer clic en botones")
        print("  5. 📸 Capturar screenshots")
        print()
        
        result = registro_cita()
        print(f"✅ Bot completado: {result}")
        
        if result:
            print("🎉 ¡ÉXITO! El bot completó todo el proceso")
            print("📸 Revisa los screenshots: debug_cita_bot.png y debug_cita_bot_final.png")
        else:
            print("⚠️ Bot ejecutado pero sin éxito")
            print("📸 Los screenshots mostrarán qué pasó")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
