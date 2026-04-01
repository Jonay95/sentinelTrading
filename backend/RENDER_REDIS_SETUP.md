# 🔧 Configuración de Redis de Render para Bot de Citas

## 🎯 **Problema Actual**

El hostname de Redis de Render no se resuelve: `red-d75rbl0ule4c73d0mjog:6379`

## 📋 **Pasos para Obtener la URL Correcta de Render**

### **1. Acceder a Render Dashboard**
1. Ve a [https://dashboard.render.com/](https://dashboard.render.com/)
2. Inicia sesión con tu cuenta

### **2. Buscar tu Servicio Redis**
1. En el dashboard, busca el servicio `sentinel-redis`
2. Haz clic en él para ver los detalles

### **3. Obtener la URL Completa**
1. En la página del servicio, busca "Connection URL" o "Internal URL"
2. La URL debería tener un formato como:
   ```
   redis://red-<random-chars>.a.render.com:6379
   ```
   O si tiene auth:
   ```
   redis://username:password@red-<random-chars>.a.render.com:6379
   ```

### **4. Formatos Posibles de Render**

#### **Opción 1: URL Interna (Recomendada)**
```
redis://red-d75rbl0ule4c73d0mjog.a.render.com:6379/0
```

#### **Opción 2: URL Externa**
```
redis://sentinel-redis.onrender.com:6379/0
```

#### **Opción 3: Con Autenticación**
```
redis://username:password@red-d75rbl0ule4c73d0mjog.a.render.com:6379/0
```

## 🔧 **Configuración en .env**

Una vez que tengas la URL correcta, actualiza tu `.env`:

```env
# Reemplaza con la URL real de Render
CELERY_BROKER_URL=redis://URL_COMPLETA_DE_RENDER:6379/0
CELERY_RESULT_BACKEND=redis://URL_COMPLETA_DE_RENDER:6379/0
CELERY_BROKER_USE_SSL=false
CELERY_RESULT_BACKEND_USE_SSL=false
```

## 🧪 **Probar la Conexión**

Después de actualizar el `.env`:

```bash
python backend/scripts/test_render_redis.py
```

## 🚨 **Troubleshooting**

### **Error: "getaddrinfo failed"**
- El hostname está incompleto
- Necesitas el dominio completo de Render
- Verifica que el servicio Redis esté corriendo

### **Error: "Connection refused"**
- El servicio Redis no está corriendo
- El puerto está bloqueado
- Firewall issues

### **Error: "Authentication required"**
- Necesitas username/password
- Revisa las credenciales en Render

## 🎯 **Verificación en Render**

1. **Service Status**: Debe decir "Deployed"
2. **Region**: Frankfurt (eu-central-1)
3. **Type**: Redis
4. **URL**: Copiada desde "Connection Details"

## 🔄 **Ventajas de Usar Redis de Render**

✅ **Integración perfecta** con otros servicios Render
✅ **Misma red** (menos latencia)
✅ **Sin configuración externa**
✅ **Monitoreo incluido**
✅ **Backup automático**

---

## 🚀 **Una Vez Configurado**

Cuando la conexión funcione:
1. ✅ Los workers de Render se conectarán automáticamente
2. ✅ Celery Beat ejecutará tareas cada 2 minutos
3. ✅ El bot verificará citas automáticamente
4. ✅ Recibirás emails cuando haya citas

**Importante: Necesitas la URL completa de Render, no solo el hostname parcial**
