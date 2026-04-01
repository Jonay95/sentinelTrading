# 🤖 Bot de Registro de Citas - Modo Automático

## 🎯 **Resumen**

Bot automático que verifica disponibilidad de citas cada 2 minutos y envía notificaciones por email cuando hay citas disponibles.

## 🚀 **Instalación y Configuración**

### **1. Instalar Redis**
```powershell
# Ejecutar como Administrador
.\scripts\install_redis.ps1
```

### **2. Activar Entorno Virtual**
```powershell
# En el directorio backend
.\venv\Scripts\Activate
```

### **3. Configurar Variables de Entorno**
```env
# Copiar .env.cita.example a .env
cp .env.cita.example .env

# Editar .env con tus datos:
REGISTRO_CITA_NIE=Y7223767X
REGISTRO_CITA_NOMBRE=Tu Nombre
REGISTRO_CITA_MAIL_TO=tu-email@ejemplo.com
REGISTRO_CITA_PROVINCIA=/icpplustieb/citar?p=8&locale=es  # Barcelona
```

### **4. Iniciar Bot Automático**
```powershell
# Con el venv activado
.\scripts\start_bot.ps1
```

## 🔄 **Funcionamiento**

### **Tareas Automáticas:**
- ⏰ **Cada 2 minutos:** Verifica disponibilidad de citas
- 📧 **Proceso completo:** 
  1. 📍 Selecciona Barcelona automáticamente
  2. 📝 Rellena formulario (NIE, Nombre, País)
  3. 🔍 Detecta disponibilidad
  4. 📧 Si hay citas → Envia email
  5. 😴 Si no hay citas → No hace nada

### **Notificaciones:**
- 📧 **Email automático:** Cuando hay citas disponibles
- 📸 **Screenshots:** Para debug y verificación
- 📊 **Logs:** Detalles de cada ejecución

## 📋 **Configuración Clave**

### **Variables Principales:**
```env
# Datos personales
REGISTRO_CITA_NIE=Y7223767X
REGISTRO_CITA_NOMBRE=Tu Nombre Completo
REGISTRO_CITA_MAIL_TO=email1@ejemplo.com,email2@ejemplo.com
REGISTRO_CITA_PAIS=248  # Venezuela

# Configuración
REGISTRO_CITA_PROVINCIA=/icpplustieb/citar?p=8&locale=es  # Barcelona
REGISTRO_CITA_SKIP_WIZARD=false  # Activar wizard de provincias
REGISTRO_CITA_HEADLESS=false  # Modo visible para debug
REGISTRO_CITA_STEALTH=true  # Anti-detección

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### **Email Configuration:**
```env
MAIL_DEFAULT_SENDER=no-reply@sentineltrading.com
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=tu-email@gmail.com
MAIL_PASSWORD=tu-app-password
```

## 🚨 **Troubleshooting**

### **Redis no inicia:**
```powershell
# Instalar Redis manualmente
choco install redis-64 -y
redis-server
```

### **Permisos PowerShell:**
```powershell
# Permitir scripts
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### **Verificar logs:**
```powershell
# Ver logs del worker
Get-Job -Name "CitaBotWorker" | Receive-Job

# Ver logs del beat
Get-Job -Name "CitaBotBeat" | Receive-Job
```

## 🎊 **Resultados Esperados**

### **✅ Funcionamiento Normal:**
- 😴 **"No hay citas disponibles"** → Bot continúa verificando
- 📸 **Screenshots** del mensaje de no disponibilidad
- 📊 **Logs** mostrando verificaciones cada 2 minutos

### **🎉 Cuando Hay Citas:**
- 📧 **Email automático** a `REGISTRO_CITA_MAIL_TO`
- 📸 **Screenshots** de las citas disponibles
- 🎯 **Oportunidad** de reservar rápidamente

## 🛠️ **Comandos Útiles**

### **Iniciar Bot:**
```powershell
.\scripts\start_bot.ps1
```

### **Detener Bot:**
```powershell
# Ctrl+C en la terminal donde corre el bot
```

### **Verificar Redis:**
```powershell
Test-NetConnection -ComputerName localhost -Port 6379
```

### **Limpiar Procesos:**
```powershell
Get-Process | Where-Object {$_.ProcessName -like "*celery*"} | Stop-Process -Force
```

## 🎯 **Ventajas del Modo Automático**

- ⚡ **Verificación constante** cada 2 minutos
- 📧 **Notificaciones inmediatas** cuando hay citas
- 🛡️ **Anti-detección** con playwright-stealth
- 📸 **Debug completo** con screenshots
- 🔄 **Ejecución 24/7** sin intervención manual
- 🎯 **Máxima oportunidad** de conseguir cita

---

## 🚀 **¡Listo para Usar!**

1. **Instalar Redis** → `.\scripts\install_redis.ps1`
2. **Activar venv** → `.\venv\Scripts\Activate`
3. **Configurar .env** → Tus datos personales
4. **Iniciar bot** → `.\scripts\start_bot.ps1`

**El bot trabajará por ti 24/7!** 🎉
