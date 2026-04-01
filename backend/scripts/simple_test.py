#!/usr/bin/env python3
"""
Script simple para probar el bot con Playwright normal (sin Chrome persistente)
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
    """Test simple con Playwright normal"""
    print("🚀 Test Simple Bot de Registro de Citas")
    print("=" * 50)
    
    # Configurar para usar Playwright normal (sin Chrome persistente)
    os.environ['REGISTRO_CITA_USE_REAL_BROWSER'] = 'false'
    os.environ['REGISTRO_CITA_HEADLESS'] = 'false'
    
    print("🔧 Configuración:")
    print("  - Navegador: Playwright normal (sin Chrome persistente)")
    print("  - Modo: Visible (headless=false)")
    print("  - Stealth: playwright-stealth activado")
    print()
    
    try:
        from app.utils.tasks.registro_cita import registro_cita
        print("✅ Imports correctos")
        print("🚀 Ejecutando bot...")
        print()
        
        result = registro_cita()
        print(f"✅ Bot ejecutado: {result}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
