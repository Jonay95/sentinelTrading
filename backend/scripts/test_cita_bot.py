#!/usr/bin/env python3
"""
Script de testing para el bot de registro de citas.
Uso: python scripts/test_cita_bot.py [--debug] [--headless]
"""

import os
import sys
import logging
from pathlib import Path

# Añadir el directorio backend al path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.utils.tasks.registro_cita import registro_cita

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_environment():
    """Verifica que las variables de entorno necesarias estén configuradas."""
    required_vars = [
        'REGISTRO_CITA_URL',
        'REGISTRO_CITA_NIE', 
        'REGISTRO_CITA_NOMBRE',
        'REGISTRO_CITA_MAIL_TO'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error("❌ Faltan variables de entorno obligatorias:")
        for var in missing_vars:
            logger.error(f"   - {var}")
        logger.error("\n📋 Copia backend/.env.cita.example a .env y configura los valores")
        return False
    
    logger.info("✅ Variables de entorno verificadas")
    return True


def main():
    """Función principal del script de testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test del bot de registro de citas')
    parser.add_argument('--debug', action='store_true', help='Activar modo debug')
    parser.add_argument('--headless', action='store_true', help='Ejecutar en modo headless')
    parser.add_argument('--install', action='store_true', help='Instalar dependencias de Playwright')
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.info("🐛 Modo debug activado")
    
    if args.headless:
        os.environ['REGISTRO_CITA_HEADLESS'] = 'true'
        logger.info("🖥️  Modo headless activado")
    else:
        os.environ['REGISTRO_CITA_HEADLESS'] = 'false'
        logger.info("👁️  Modo visual activado (podrás ver el navegador)")
    
    if args.install:
        logger.info("📦 Instalando dependencias de Playwright...")
        os.system("pip install playwright playwright-stealth")
        os.system("playwright install chromium")
        logger.info("✅ Dependencias instaladas")
        return
    
    # Verificar configuración
    if not check_environment():
        sys.exit(1)
    
    # Mostrar configuración actual
    logger.info("🚀 Iniciando test del bot de registro de citas")
    logger.info(f"🌐 URL: {os.getenv('REGISTRO_CITA_URL')}")
    logger.info(f"👤 NIE: {os.getenv('REGISTRO_CITA_NIE')}")
    logger.info(f"📧 Notificaciones a: {os.getenv('REGISTRO_CITA_MAIL_TO')}")
    logger.info(f"🖥️  Headless: {os.getenv('REGISTRO_CITA_HEADLESS')}")
    
    try:
        # Ejecutar la tarea
        logger.info("⏳ Ejecutando bot de registro de citas...")
        result = registro_cita()
        
        if result is None:
            logger.info("✅ Test completado exitosamente")
        else:
            logger.info("ℹ️  Test completado con resultado: %s", result)
            
    except KeyboardInterrupt:
        logger.info("⏹️  Test interrumpido por el usuario")
    except Exception as e:
        logger.error(f"❌ Error durante el test: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
