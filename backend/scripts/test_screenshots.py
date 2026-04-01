#!/usr/bin/env python3
"""
Test para verificar que los screenshots se guarden correctamente
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

def test_screenshot_save():
    """Test guardar screenshots"""
    print("📸 Test de Screenshots")
    print("=" * 40)
    
    try:
        from playwright.sync_api import sync_playwright
        
        print("🚀 Iniciando navegador para test de screenshots...")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()
            
            # Navegar a una página simple
            page.goto("https://www.google.com")
            page.wait_for_timeout(2000)
            
            # Test screenshot 1
            screenshot_path1 = "debug_cita_bot.png"
            full_path1 = project_root / screenshot_path1
            
            print(f"📸 Guardando screenshot 1 en: {full_path1}")
            page.screenshot(path=str(full_path1), full_page=True)
            
            if full_path1.exists():
                print(f"✅ Screenshot 1 guardado: {full_path1}")
                print(f"📊 Tamaño: {full_path1.stat().st_size} bytes")
            else:
                print(f"❌ Screenshot 1 NO guardado")
            
            # Navegar a otra página
            page.goto("https://www.github.com")
            page.wait_for_timeout(2000)
            
            # Test screenshot 2
            screenshot_path2 = "debug_cita_bot_final.png"
            full_path2 = project_root / screenshot_path2
            
            print(f"📸 Guardando screenshot 2 en: {full_path2}")
            page.screenshot(path=str(full_path2), full_page=True)
            
            if full_path2.exists():
                print(f"✅ Screenshot 2 guardado: {full_path2}")
                print(f"📊 Tamaño: {full_path2.stat().st_size} bytes")
            else:
                print(f"❌ Screenshot 2 NO guardado")
            
            browser.close()
            
        print("\n🎯 Verificando screenshots en directorio raíz:")
        screenshots = list(project_root.glob("debug_cita_bot*.png"))
        
        if screenshots:
            for screenshot in screenshots:
                print(f"✅ {screenshot.name} - {screenshot.stat().st_size} bytes")
        else:
            print("❌ No se encontraron screenshots")
            
        return len(screenshots) > 0
        
    except Exception as e:
        print(f"❌ Error en test de screenshots: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Función principal"""
    print("🚀 Test de Screenshots del Bot")
    print("=" * 50)
    
    success = test_screenshot_save()
    
    if success:
        print("\n✅ Screenshots funcionando correctamente")
        print("📸 Los archivos se guardan en el directorio raíz")
    else:
        print("\n❌ Problemas con los screenshots")
        print("💡 Posibles causas:")
        print("   - Permisos del directorio")
        print("   - Espacio en disco")
        print("   - Problemas con Playwright")

if __name__ == "__main__":
    main()
