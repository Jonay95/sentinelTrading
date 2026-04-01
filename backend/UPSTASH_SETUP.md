# 🔧 Configuración de Upstash Redis para Bot de Citas

## 🎯 **Problema Actual**

El token de Redis parece estar incorrecto. Necesitas obtener el token correcto desde Upstash.

## 📋 **Pasos para Obtener el Token Correcto**

### **1. Acceder a Upstash**
1. Ve a [https://console.upstash.com/](https://console.upstash.com/)
2. Inicia sesión con tu cuenta

### **2. Navegar a tu Database**
1. En el dashboard, busca "Redis" en el menú izquierdo
2. Haz clic en tu database: `sentinelTradingCelery`

### **3. Obtener el Token**
1. En la página de la database, busca la sección "Connection Details"
2. Copia el **REST URL** o **TCP URL** completa
3. El formato debería ser:
   ```
   redis://default:TU_TOKEN_REAL@nearby-pheasant-89010.upstash.io:6379
   ```

### **4. Formatos de URL Posibles**

#### **Opción 1: TCP URL**
```
redis://default:TU_TOKEN_REAL@nearby-pheasant-89010.upstash.io:6379
```

#### **Opción 2: TLS URL**
```
rediss://default:TU_TOKEN_REAL@nearby-pheasant-89010.upstash.io:6379
```

#### **Opción 3: REST URL**
```
https://nearby-pheasant-89010.upstash.io/rest/TU_TOKEN_REAL
```

## 🔧 **Configuración en .env**

Una vez que tengas el token correcto, actualiza tu archivo `.env`:

```env
# Reemplaza TU_TOKEN_REAL con el token real de Upstash
CELERY_BROKER_URL=redis://default:TU_TOKEN_REAL@nearby-pheasant-89010.upstash.io:6379
CELERY_RESULT_BACKEND=redis://default:TU_TOKEN_REAL@nearby-pheasant-89010.upstash.io:6379
CELERY_BROKER_USE_SSL=true
CELERY_RESULT_BACKEND_USE_SSL=true
```

## 🧪 **Probar la Conexión**

Después de actualizar el `.env`, prueba la conexión:

```bash
python backend/scripts/test_simple_redis.py
```

## 🚨 **Troubleshooting**

### **Error: "Connection closed by server"**
- El token es incorrecto
- La database no está activa
- Firewall bloqueando la conexión

### **Error: "invalid username-password pair"**
- El formato de la URL es incorrecto
- El token está mal copiado

### **Error: "Connection refused"**
- La database no está corriendo
- El puerto está bloqueado

## 🎯 **Verificación en Upstash**

1. **Database Status**: Debe decir "Available"
2. **Region**: Frankfurt, Germany (eu-central-1)
3. **Plan**: Free Tier
4. **Endpoint**: nearby-pheasant-89010.upstash.io

## 📞 **Soporte Upstash**

Si sigues teniendo problemas:
1. Revisa la [documentación de Upstash](https://upstash.com/docs)
2. Contacta el soporte de Upstash
3. Verifica que la database esté activa

---

## 🚀 **Una Vez Configurado**

Cuando la conexión funcione:
1. ✅ El bot se conectará a Redis
2. ✅ Celery worker procesará tareas
3. ✅ Celery Beat ejecutará tareas cada 2 minutos
4. ✅ Recibirás emails cuando haya citas

**¡Importante: El token debe ser el real de Upstash, no el ejemplo!**
