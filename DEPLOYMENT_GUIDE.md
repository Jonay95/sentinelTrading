# 🚀 Guía de Despliegue Completa - Sentinel Trading

## 📋 Requisitos Previos

### 1. Cuenta en GitHub
- Crear repositorio `sentinelTrading`
- Tener el código pusheado

### 2. Cuenta en Render
- Registrarse en https://render.com
- Conectar cuenta GitHub

### 3. Supabase Configurado
- ✅ Base de datos creada
- ✅ Schema ejecutado
- ✅ API keys disponibles

---

## 🎯 Paso 1: Preparar Repositorio GitHub

### 1.1 Crear Repositorio
```bash
# Si no tienes repositorio remoto:
git remote add origin https://github.com/TU_USERNAME/sentinelTrading.git
git branch -M main
git push -u origin main
```

### 1.2 Verificar que todo está en GitHub
```bash
git status
git push origin main
```

---

## 🎯 Paso 2: Desplegar Backend en Render

### 2.1 Crear Backend Service
1. **Ve a Render.com**
2. **Dashboard → New → Web Service**
3. **Connect GitHub** y selecciona `sentinelTrading`
4. **Configura el service:**

```yaml
Name: sentinel-trading-api
Environment: Python 3
Root Directory: backend
Build Command: pip install -r requirements_clean.txt
Start Command: gunicorn --bind 0.0.0.0:$PORT app:app
Instance Type: Free ($0/mes)
```

### 2.2 Variables de Entorno (Backend)
```bash
SUPABASE_URL=https://dqfuuycnzhqatkiwcecf.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRxZnV1eWNuemhxYXRraXdjZWNmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ4NjQ5MzMsImV4cCI6MjA5MDQ0MDkzM30.qYwxaPPy2O7L0QEVSJL4TZVlS62yjbfWlXAnmg5S3bE
SECRET_KEY=sentinel_render_production_secret_2024
FLASK_ENV=production
SQL_DEBUG=false
```

### 2.3 Health Check
- **Health Check Path:** `/api/health`
- **Auto-deploy:** ✅ Activado

---

## 🎯 Paso 3: Desplegar Frontend en Render

### 3.1 Crear Frontend Service
1. **Dashboard → New → Web Service**
2. **Mismo repositorio** `sentinelTrading`
3. **Configura el service:**

```yaml
Name: sentinel-trading-frontend
Environment: Static
Root Directory: frontend
Build Command: npm run build
Publish Directory: dist
Instance Type: Free ($0/mes)
```

### 3.2 Variables de Entorno (Frontend)
```bash
VITE_API_URL=https://sentinel-trading-api.onrender.com/api
```

### 3.3 Health Check
- **Health Check Path:** `/`
- **Auto-deploy:** ✅ Activado

---

## 🎯 Paso 4: Configurar Dominio Personalizado (Opcional)

### 4.1 Backend
1. **Service → Custom Domains**
2. **Add domain:** `api.sentrading.com`
3. **Configurar DNS** según instrucciones de Render

### 4.2 Frontend
1. **Service → Custom Domains**
2. **Add domain:** `sentrading.com`
3. **Configurar DNS** según instrucciones de Render

---

## 🎯 Paso 5: Verificar Despliegue

### 5.1 Backend Tests
```bash
# Test health endpoint
curl https://sentinel-trading-api.onrender.com/api/health

# Test assets endpoint
curl https://sentinel-trading-api.onrender.com/api/assets

# Test database connection
curl https://sentinel-trading-api.onrender.com/api/assets/1
```

### 5.2 Frontend Tests
- Visita: `https://sentinel-trading-frontend.onrender.com`
- Verifica que carga la interfaz
- Verifica que conecta con el backend

---

## 🔧 Troubleshooting

### Problemas Comunes

#### 1. Backend no inicia
```bash
# Revisar logs en Render Dashboard
# Verificar variables de entorno
# Revisar requirements.txt
```

#### 2. Frontend no conecta con backend
```bash
# Verificar VITE_API_URL
# Revisar CORS configuration
# Verificar que backend está corriendo
```

#### 3. Error de base de datos
```bash
# Verificar SUPABASE_URL y SUPABASE_ANON_KEY
# Revisar que schema esté creado en Supabase
# Testear conexión localmente
```

---

## 📊 URLs Finales (Ejemplo)

### Backend
- **URL:** `https://sentinel-trading-api.onrender.com`
- **Health:** `https://sentinel-trading-api.onrender.com/api/health`
- **API Docs:** `https://sentinel-trading-api.onrender.com/api/docs`

### Frontend
- **URL:** `https://sentinel-trading-frontend.onrender.com`
- **Dashboard:** `https://sentinel-trading-frontend.onrender.com/dashboard`

### Base de Datos
- **Supabase:** `https://dqfuuycnzhqatkiwcecf.supabase.co`
- **SQL Editor:** `https://dqfuuycnzhqatkiwcecf.supabase.co/project/sql`

---

## 🎉 Checklist Final

### Backend ✅
- [ ] Service creado en Render
- [ ] Variables de entorno configuradas
- [ ] Health check funcionando
- [ ] API endpoints respondiendo
- [ ] Conexión a Supabase funcionando

### Frontend ✅
- [ ] Service creado en Render
- [ ] Build exitoso
- [ ] Conexión con backend funcionando
- [ ] Interfaz cargando correctamente
- [ ] Todas las páginas funcionando

### General ✅
- [ ] Repositorio GitHub actualizado
- [ ] Auto-deploy activado
- [ ] Logs revisados
- [ ] Tests ejecutados
- [ ] Documentación actualizada

---

## 🚀 Siguientes Pasos

1. **Monitoreo:** Configurar alerts en Render
2. **Dominio:** Configurar dominio personalizado
3. **SSL:** Ya está incluido con Render
4. **Backup:** Configurar backups automáticos en Supabase
5. **Analytics:** Configurar Google Analytics

---

## 💡 Tips Importantes

- **Free Tier:** Render tiene límites de uso (750h/mes)
- **Cold Starts:** Los servicios gratuitos pueden tardar en iniciar
- **Logs:** Revisa los logs regularmente en Render Dashboard
- **Environment:** Mantén las variables de entorno seguras
- **Updates:** Los cambios se despliegan automáticamente con git push

---

## 🆘 Ayuda

Si tienes problemas:
1. **Revisa logs** en Render Dashboard
2. **Verifica variables** de entorno
3. **Testea localmente** antes de desplegar
4. **Consulta documentación** de Render y Supabase

---

## 🎊 ¡Felicidades!

🏆 **Tu Sentinel Trading está desplegado y funcionando en producción!**

- ✅ **Backend API** corriendo en Render
- ✅ **Frontend React** corriendo en Render  
- ✅ **Base de datos** en Supabase
- ✅ **Todo conectado** y funcionando
- ✅ **Gratis** para empezar
- ✅ **Escalable** cuando crezcas
