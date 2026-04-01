#!/usr/bin/env python3
"""
Script para encontrar el selector correcto del botón "Solicitar Cita"
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

def find_button_selectors():
    """Encontrar todos los selectores posibles para el botón"""
    print("🔍 Buscando botón 'Solicitar Cita'")
    print("=" * 50)
    
    try:
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()
            
            # Navegar a la página
            page.goto("https://icp.administracionelectronica.gob.es/icpplustieb/index.html")
            page.wait_for_timeout(3000)
            
            print("🌐 Página cargada")
            
            # Buscar el botón por diferentes métodos
            selectors_to_try = [
                # Botones por texto
                'button:has-text("Solicitar Cita")',
                'input[value="Solicitar Cita"]',
                'a:has-text("Solicitar Cita")',
                '[role="button"]:has-text("Solicitar Cita")',
                
                # Botones por clase o ID común
                'button.btn-primary',
                'button.btn',
                'input[type="submit"]',
                'button[type="submit"]',
                
                # Textos similares
                'button:has-text("Solicitar")',
                'button:has-text("Cita")',
                'a:has-text("Solicitar")',
                'a:has-text("Cita")',
                
                # Selectores genéricos
                'button',
                'input[type="button"]',
                'a[href*="cita"]',
            ]
            
            found_buttons = []
            
            for selector in selectors_to_try:
                try:
                    elements = page.query_selector_all(selector)
                    if elements:
                        for i, element in enumerate(elements):
                            text = element.inner_text().strip()
                            if text and ('cita' in text.lower() or 'solicitar' in text.lower()):
                                found_buttons.append({
                                    'selector': selector,
                                    'text': text,
                                    'tag': element.evaluate('el => el.tagName.toLowerCase()'),
                                    'id': element.get_attribute('id'),
                                    'class': element.get_attribute('class'),
                                })
                                print(f"✅ Encontrado: {selector}")
                                print(f"   📝 Texto: '{text}'")
                                print(f"   🏷️  Tag: {element.evaluate('el => el.tagName.toLowerCase()')}")
                                print(f"   🆔 ID: {element.get_attribute('id')}")
                                print(f"   🎨 Clase: {element.get_attribute('class')}")
                                print()
                except Exception as e:
                    print(f"❌ Error con selector '{selector}': {e}")
            
            # Buscar todos los botones en la página
            print("🔍 Buscando TODOS los botones en la página...")
            all_buttons = page.query_selector_all('button, input[type="button"], input[type="submit"], a')
            
            print(f"📊 Total de botones encontrados: {len(all_buttons)}")
            for i, button in enumerate(all_buttons):
                try:
                    text = button.inner_text().strip()
                    tag = button.evaluate('el => el.tagName.toLowerCase()')
                    btn_id = button.get_attribute('id')
                    btn_class = button.get_attribute('class')
                    
                    print(f"\n🔘 Botón {i+1}:")
                    print(f"   📝 Texto: '{text}'")
                    print(f"   🏷️  Tag: {tag}")
                    print(f"   🆔 ID: {btn_id}")
                    print(f"   🎨 Clase: {btn_class}")
                    
                    if text and ('cita' in text.lower() or 'solicitar' in text.lower()):
                        print(f"   ✅ ¡ESTE PODRÍA SER EL BOTÓN BUSCADO!")
                except Exception as e:
                    print(f"❌ Error analizando botón {i+1}: {e}")
            
            # Guardar screenshot para referencia
            screenshot_path = project_root / "button_search.png"
            page.screenshot(path=str(screenshot_path), full_page=True)
            print(f"\n📸 Screenshot guardado: {screenshot_path}")
            
            browser.close()
            
            if found_buttons:
                print(f"\n🎯 Botones candidatos encontrados: {len(found_buttons)}")
                for btn in found_buttons:
                    print(f"   ✅ {btn['selector']}: '{btn['text']}'")
                return found_buttons
            else:
                print("\n❌ No se encontró el botón 'Solicitar Cita'")
                return []
                
    except Exception as e:
        print(f"❌ Error general: {e}")
        import traceback
        traceback.print_exc()
        return []

def main():
    """Función principal"""
    print("🚀 Buscador de Botones - Cita Previa")
    print("=" * 60)
    
    buttons = find_button_selectors()
    
    if buttons:
        print("\n🎉 ¡Botones encontrados!")
        print("📝 Actualiza el selector en el código:")
        for btn in buttons:
            print(f"   _get_by_role_click(root, page, \"{btn['text']}\", timeout_ms)")
    else:
        print("\n❌ No se encontraron botones")
        print("💡 Revisa:")
        print("   - Que la página haya cargado completamente")
        print("   - Que no haya CAPTCHA o bloqueos")
        print("   - Que el botón tenga otro nombre")

if __name__ == "__main__":
    main()
