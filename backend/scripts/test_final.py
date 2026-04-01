#!/usr/bin/env python3
"""
Test final del bot con todo corregido
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
    """Test final con todo corregido"""
    print("🚀 Test Final Bot de Registro de Citas")
    print("=" * 50)
    
    # Configuración clave
    os.environ['REGISTRO_CITA_USE_REAL_BROWSER'] = 'false'  # Playwright normal
    os.environ['REGISTRO_CITA_HEADLESS'] = 'false'          # Modo visible
    os.environ['REGISTRO_CITA_SKIP_WIZARD'] = 'true'       # Saltar asistente
    
    print("🔧 Configuración:")
    print("  - Navegador: Playwright normal (evita conflictos Chrome)")
    print("  - Modo: Visible (headless=false)")
    print("  - Stealth: playwright-stealth corregido")
    print("  - Wizard: Skip (evita problema provincias)")
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
        
        print("🚀 Ejecutando bot...")
        print("✨ Verás el navegador abrirse y navegar a la web de citas")
        print("📸 Se guardarán screenshots automáticos")
        print()
        
        result = registro_cita()
        print(f"✅ Bot completado: {result}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
