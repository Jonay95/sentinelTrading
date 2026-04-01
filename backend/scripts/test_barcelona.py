#!/usr/bin/env python3
"""
Test específico para Barcelona con todo corregido
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
    """Test específico para Barcelona"""
    print("🚀 Test Bot de Registro de Citas - Barcelona")
    print("=" * 50)
    
    # Configuración específica para Barcelona
    config = {
        'REGISTRO_CITA_USE_REAL_BROWSER': 'false',
        'REGISTRO_CITA_HEADLESS': 'false',
        'REGISTRO_CITA_SKIP_WIZARD': 'false',  # 👈 Activar wizard para provincias
        'REGISTRO_CITA_PROVINCIA': '/icpplustieb/citar?p=8&locale=es',  # 👈 Barcelona exacto
        'REGISTRO_CITA_STEALTH': 'true',
        'REGISTRO_CITA_TRAMITE': '4010',
        'REGISTRO_CITA_TIMEOUT_MS': '120000',
        'REGISTRO_CITA_POST_GOTO_MS': '5000'
    }
    
    # Aplicar configuración
    for key, value in config.items():
        os.environ[key] = value
    
    print("🔧 Configuración:")
    print("  - Provincia: Barcelona (p=8)")
    print("  - Wizard: Activado (para seleccionar provincia)")
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
        
        print("🚀 Ejecutando bot para Barcelona...")
        print("✨ Pasos:")
        print("  1. Abrir navegador con stealth")
        print("  2. Navegar a web de citas")
        print("  3. Seleccionar provincia Barcelona")
        print("  4. Continuar con el proceso")
        print("  5. Guardar screenshots")
        print()
        
        result = registro_cita()
        print(f"✅ Bot completado: {result}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
