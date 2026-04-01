#!/usr/bin/env python3
"""
Test con configuración de email para verificar notificaciones
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
    """Test con email configurado"""
    print("🚀 Test Bot con Email - Citas Disponibles")
    print("=" * 50)
    
    # Configuración completa con email
    config = {
        'REGISTRO_CITA_USE_REAL_BROWSER': 'false',
        'REGISTRO_CITA_HEADLESS': 'false',
        'REGISTRO_CITA_SKIP_WIZARD': 'false',
        'REGISTRO_CITA_PROVINCIA': '/icpplustieb/citar?p=8&locale=es',
        'REGISTRO_CITA_STEALTH': 'true',
        'REGISTRO_CITA_IGNORE_HTTPS_ERRORS': 'true',
        'REGISTRO_CITA_TIMEOUT_MS': '120000',
        'REGISTRO_CITA_POST_GOTO_MS': '8000',
        
        # Selectores exactos
        'REGISTRO_CITA_SEL_NIE': '#txtIdCitado',
        'REGISTRO_CITA_SEL_NOMBRE': '#txtDesCitado', 
        'REGISTRO_CITA_SEL_PAIS': '#txtPaisNac',
        
        # Valores exactos
        'REGISTRO_CITA_NIE': 'Y7223767X',
        'REGISTRO_CITA_NOMBRE': 'Jonay Gonzalez',
        'REGISTRO_CITA_PAIS': '248',
        'REGISTRO_CITA_MAIL_TO': 'jojalosa95@gmail.com,michellegonzalez14111@gmail.com',
        
        # Email configuration
        'MAIL_DEFAULT_SENDER': 'no-reply@sentineltrading.com',
        'MAIL_SERVER': 'smtp.gmail.com',
        'MAIL_PORT': '587',
        'MAIL_USE_TLS': 'true',
        'MAIL_USERNAME': 'sentineltrading@gmail.com',
        'MAIL_PASSWORD': 'tu_password_aqui',  # Necesitarás configurar esto
    }
    
    # Aplicar configuración
    for key, value in config.items():
        os.environ[key] = value
    
    print("🔧 Configuración completa:")
    print("  - Provincia: Barcelona (p=8)")
    print("  - Formulario: Todos los campos configurados")
    print("  - Email: Notificaciones activadas")
    print("  - Lógica: Si hay citas → envía email")
    print("  - Lógica: Si no hay citas → no hace nada")
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
        
        print("🚀 Ejecutando bot con lógica de email...")
        print("✨ Comportamiento esperado:")
        print("  📍 1. Seleccionar Barcelona")
        print("  📝 2. Rellenar formulario completo")
        print("  🔍 3. Detectar disponibilidad:")
        print("     - Si hay citas 📧 → Enviar email a jojalosa95@gmail.com")
        print("     - Si no hay citas 😴 → No hacer nada (correcto)")
        print("  📸 4. Guardar screenshots del resultado")
        print()
        
        result = registro_cita()
        print(f"✅ Bot completado: {result}")
        
        if result:
            print("🎉 ¡ÉXITO! Hubo citas disponibles y se envió email")
            print("📧 Revisa tu correo: jojalosa95@gmail.com")
        elif result is False:
            print("😴 CORRECTO: No hay citas disponibles (comportamiento normal)")
            print("📸 Los screenshots muestran el mensaje 'no hay citas'")
        else:
            print("⚠️ Bot ejecutado pero resultado ambiguo")
        
        print("📸 Revisa los screenshots: debug_cita_bot.png y debug_cita_bot_final.png")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
