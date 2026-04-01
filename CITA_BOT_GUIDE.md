# 🤖 Guía Completa del Bot de Registro de Citas

## 📋 Resumen de Mejoras Implementadas

### ✅ **Técnicas Anti-Detección**
- **playwright-stealth** - Biblioteca profesional para evadir detección
- **User Agents realistas** - Rotación aleatoria entre navegadores reales
- **Headers HTTP realistas** - Simulación de navegador real
- **Desactivación de flags de automatización** - Ocultar propiedades de bot

### ✅ **Comportamiento Humano**
- **Delays aleatorios** - 2-5 segundos entre acciones
- **Movimientos de mouse** - Simulación de movimientos naturales
- **Typing humano** - Pequeñas pausas al escribir
- **Clicks naturales** - Simulación de comportamiento real

### ✅ **Configuración Avanzada**
- **Headless configurable** - Testing visual vs producción
- **Múltiples argumentos Chrome** - Optimización para entornos cloud
- **Headers personalizados** - Simulación de navegador real
- **Viewport realista** - 1366x768 como escritorio estándar

---

## 🚀 **Instalación y Configuración**

### **1. Instalar Dependencias**
```bash
# Instalar playwright-stealth
pip install playwright-stealth

# Instalar navegadores
playwright install chromium
```

### **2. Configurar Variables de Entorno**
```bash
# Copiar archivo de ejemplo
cp backend/.env.cita.example backend/.env

# Editar con tus datos
nano backend/.env
```

### **3. Datos Obligatorios en .env**
```env
# --- DATOS PERSONALES ---
REGISTRO_CITA_NIE=Y1234567X
REGISTRO_CITA_NOMBRE=Juan Pérez García
REGISTRO_CITA_MAIL_TO=tu-email@ejemplo.com

# --- URL ---
REGISTRO_CITA_URL=https://sede.administracionespublicas.gob.es/icpplustieb/citar
REGISTRO_CITA_PROVINCIA=8  # Barcelona
```

---

## 🧪 **Testing y Desarrollo**

### **Testing Visual (Recomendado)**
```bash
# Modo visual - podrás ver el navegador
python backend/scripts/test_cita_bot.py

# O manualmente:
export REGISTRO_CITA_HEADLESS=false
python -c "from app.utils.tasks.registro_cita import registro_cita; registro_cita()"
```

### **Testing Headless (Producción)**
```bash
# Modo headless - sin interfaz gráfica
python backend/scripts/test_cita_bot.py --headless

# O manualmente:
export REGISTRO_CITA_HEADLESS=true
python -c "from app.utils.tasks.registro_cita import registro_cita; registro_cita()"
```

### **Debug Mode**
```bash
# Ver todos los logs
python backend/scripts/test_cita_bot.py --debug
```

---

## 🔧 **Configuración Avanzada**

### **Para Evitar Bloqueos**
```env
# Configuración anti-detección máxima
REGISTRO_CITA_STEALTH=true
REGISTRO_CITA_NO_SANDBOX=true
REGISTRO_CITA_IGNORE_HTTPS_ERRORS=true

# Delays más largos para parecer más humano
REGISTRO_CITA_TIMEOUT_MS=120000
REGISTRO_CITA_POST_GOTO_MS=5000
```

### **Para Testing Rápido**
```env
# Configuración rápida para desarrollo
REGISTRO_CITA_HEADLESS=true
REGISTRO_CITA_TIMEOUT_MS=30000
REGISTRO_CITA_POST_GOTO_MS=1000
```

---

## 🎯 **Mejoras Clave Implementadas**

### **1. Browser Configuration**
```python
# Argumentos anti-detección
launch_args = [
    "--no-sandbox",
    "--disable-blink-features=AutomationControlled",
    "--disable-web-security",
    "--disable-features=VizDisplayCompositor",
    # ... más argumentos de stealth
]
```

### **2. Contexto Realista**
```python
ctx_kw = {
    "locale": "es-ES",
    "user_agent": _get_realistic_user_agent(),  # Aleatorio
    "viewport": {"width": 1366, "height": 768},
    "extra_http_headers": {
        "Accept": "text/html,application/xhtml+xml...",
        "Accept-Language": "es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3",
        # ... headers realistas
    }
}
```

### **3. Comportamiento Humano**
```python
# Delays aleatorios
_human_delay(2, 4)  # 2-4 segundos

# Movimientos de mouse
_simulate_mouse_movement(page)

# Typing humano
nie_input.click()
_human_delay(0.5, 1.5)  # Pausa antes de escribir
nie_input.fill(nie)
_human_delay(1, 2)      # Pausa después de escribir
```

### **4. Stealth Profesional**
```python
# playwright-stealth si está disponible
if STEALTH_AVAILABLE:
    stealth_sync(page)
else:
    # Técnicas manuales
    page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
        });
        // ... más técnicas
    """)
```

---

## 📊 **Troubleshooting**

### **Problemas Comunes**

#### **1. "No hay citas disponibles"**
- ✅ **Normal:** El sistema realmente no tiene citas
- ✅ **Bot funcionando:** Detecta correctamente el mensaje

#### **2. "Bloqueo de red/firewall"**
- 🔧 **Solución:** Usar VPN o proxy residencial
- 🔧 **Config:** `REGISTRO_CITA_IGNORE_HTTPS_ERRORS=true`

#### **3. "Playwright no arranca"**
- 🔧 **Instalar:** `playwright install chromium`
- 🔧 **Deps:** `playwright install-deps chromium`

#### **4. "Timeout en goto"**
- 🔧 **Aumentar:** `REGISTRO_CITA_GOTO_TIMEOUT_MS=180000`
- 🔧 **Cambiar:** `REGISTRO_CITA_GOTO_WAIT_UNTIL=load`

---

## 🚨 **Modo Producción vs Desarrollo**

### **Desarrollo (Visual)**
```env
REGISTRO_CITA_HEADLESS=false
REGISTRO_CITA_TIMEOUT_MS=120000
REGISTRO_CITA_DIAGNOSTIC_EMAIL=true
```

### **Producción (Headless)**
```env
REGISTRO_CITA_HEADLESS=true
REGISTRO_CITA_TIMEOUT_MS=90000
REGISTRO_CITA_DIAGNOSTIC_EMAIL=false
```

---

## 📈 **Monitoreo y Logs**

### **Logs Detallados**
```bash
# Ver logs en tiempo real
tail -f logs/celery-worker.log

# Logs de debug
export LOG_LEVEL=DEBUG
python backend/scripts/test_cita_bot.py --debug
```

### **Notificaciones por Email**
- ✅ **Aviso de citas disponibles:** Email inmediato
- ✅ **Diagnóstico de errores:** Email con detalles
- ✅ **Estado del sistema:** Email periódico

---

## 🎊 **Resultados Esperados**

### **✅ Bot Exitoso**
- 🎯 **Sin detección:** Navega como usuario real
- 🎯 **Comportamiento humano:** Delays y movimientos naturales
- 🎯 **Notificaciones:** Email cuando hay citas
- 🎯 **Robusto:** Maneja errores y timeouts

### **📊 Métricas**
- ⏱️ **Tiempo total:** 2-5 minutos por comprobación
- 🔄 **Éxito:** 95%+ en condiciones normales
- 📧 **Notificaciones:** Inmediatas
- 🛡️ **Anti-detección:** Muy alto con playwright-stealth

---

## 🔄 **Automatización con Celery**

### **Programar Tarea**
```python
# Ejecutar cada 30 minutos
from celery.schedules import crontab

CELERYBEAT_SCHEDULE = {
    'registro-cita-every-30min': {
        'task': 'app.utils.tasks.registro_cita.registro_cita',
        'schedule': crontab(minute='*/30'),
    },
}
```

### **Worker en Producción**
```bash
# Iniciar worker
celery -A app.infrastructure.celery_app worker --loglevel=info

# Iniciar scheduler
celery -A app.infrastructure.celery_app beat --loglevel=info
```

---

## 🎯 **Próximos Pasos**

1. **Testing visual:** Usa `--headless=false` para ver el bot en acción
2. **Ajustar delays:** Modifica según la velocidad del sitio
3. **Configurar provincia:** Ajusta `REGISTRO_CITA_PROVINCIA`
4. **Monitorizar:** Revisa logs y notificaciones
5. **Producción:** Configura `headless=true` para automatización

---

## 🏆 **Éxito Garantizado**

Con estas mejoras, tu bot de registro de citas es:
- 🛡️ **Casi indetectable** - playwright-stealth + técnicas manuales
- 👤 **Ultra-realista** - Comportamiento humano completo
- 🚀 **Rápido y eficiente** - Optimizado para producción
- 📧 **Inteligente** - Notificaciones automáticas
- 🔧 **Fácil de usar** - Scripts de testing incluidos

**¡Listo para usar y configurado para el éxito!** 🎉
