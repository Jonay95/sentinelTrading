#!/usr/bin/env python3
"""
Test directo para el formulario ya en la página de rellenar campos
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
    """Test directo al formulario principal"""
    print("🚀 Test Directo Bot de Registro de Citas")
    print("=" * 50)
    
    # Configuración para ir directo al formulario
    config = {
        'REGISTRO_CITA_USE_REAL_BROWSER': 'false',
        'REGISTRO_CITA_HEADLESS': 'false',
        'REGISTRO_CITA_SKIP_WIZARD': 'true',  # 👈 Saltar wizard ya que estamos en el formulario
        'REGISTRO_CITA_STEALTH': 'true',
        'REGISTRO_CITA_TIMEOUT_MS': '120000',
        'REGISTRO_CITA_POST_GOTO_MS': '8000',  # 👈 Más tiempo para carga
    }
    
    # Aplicar configuración
    for key, value in config.items():
        os.environ[key] = value
    
    print("🔧 Configuración:")
    print("  - Wizard: Saltado (ya estamos en formulario)")
    print("  - Navegador: Playwright normal")
    print("  - Modo: Visible (headless=false)")
    print("  - Stealth: playwright-stealth corregido")
    print("  - Timeout: 120s (más tiempo)")
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
        
        print("🚀 Ejecutando bot directo al formulario...")
        print("✨ Basado en diagnóstico:")
        print("  ✅ URL: https://icp.administracionelectronica.gob.es/icpplustieb/acEntrada")
        print("  ✅ Formulario: #citadoForm encontrado")
        print("  ✅ Campo NIE: #txtIdCitado encontrado")
        print("  🎯 Objetivo: Rellenar y enviar formulario")
        print()
        
        result = registro_cita()
        print(f"✅ Bot completado: {result}")
        
        if result:
            print("🎉 ¡ÉXITO! El bot completó el proceso")
        else:
            print("⚠️ Bot ejecutado pero sin éxito")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
