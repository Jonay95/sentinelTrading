# 🚀 Guía de Despliegue de Sentinel Trading

## 📋 Requisitos Previos

### 1. Base de Datos Gratuita
Opciones recomendadas:

#### 🏆 Supabase (Recomendado)
```bash
# 1. Crear cuenta en https://supabase.com
# 2. Crear nuevo proyecto
# 3. Obtener URL de conexión:
DATABASE_URL=postgresql://postgres:[PASSWORD]@db.[PROJECT_ID].supabase.co:5432/postgres
```

#### Alternativas:
- **Neon**: `postgresql://[USER]:[PASS]@[HOST].neon.tech/dbname`
- **MongoDB Atlas**: `mongodb+srv://[USER]:[PASS]@cluster.mongodb.net/dbname`
- **SQLite (desarrollo)**: `sqlite:///sentinel_trading.db`

### 2. Variables de Entorno
Crear `.env`:
```bash
# Database
DATABASE_URL=postgresql://postgres:[PASSWORD]@db.supabase.co:5432/postgres

# API Keys
ALPHA_VANTAGE_API_KEY=your_key_here
NEWS_API_KEY=your_key_here
TWITTER_API_KEY=your_key_here

# Security
SECRET_KEY=your_secret_key_here
JWT_SECRET_KEY=your_jwt_secret_here

# Redis (para caching)
REDIS_URL=redis://localhost:6379

# MLflow
MLFLOW_TRACKING_URI=http://localhost:5000
```

## 🐳 Despliegue con Docker (Recomendado)

### 1. Crear Dockerfile para Backend
```dockerfile
# backend/Dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 5000

# Run application
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
```

### 2. Crear Dockerfile para Frontend
```dockerfile
# frontend/Dockerfile
FROM node:18-alpine as build

WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production

COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### 3. Docker Compose para Producción
```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "5000:5000"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis

  frontend:
    build: ./frontend
    ports:
      - "80:80"
    depends_on:
      - backend

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

### 4. Desplegar
```bash
# Construir y levantar servicios
docker-compose -f docker-compose.prod.yml up -d

# Ver logs
docker-compose -f docker-compose.prod.yml logs -f
```

## ☁️ Opciones de Despliegue en la Nube

### 1. Vercel (Frontend)
```bash
# 1. Instalar Vercel CLI
npm i -g vercel

# 2. Desplegar frontend
cd frontend
vercel --prod

# 3. Configurar variables de entorno
vercel env add DATABASE_URL production
vercel env add API_KEY production
```

### 2. Railway (Backend + Base de Datos)
```bash
# 1. Instalar Railway CLI
npm install -g @railway/cli

# 2. Login
railway login

# 3. Crear proyecto
railway new

# 4. Desplegar backend
cd backend
railway up

# 5. Añadir variables de entorno
railway variables set DATABASE_URL=your_db_url
railway variables set SECRET_KEY=your_secret
```

### 3. Render (Backend + Frontend + Base de Datos)
```bash
# 1. Crear cuenta en https://render.com
# 2. Conectar repositorio GitHub
# 3. Configurar servicios:

# Backend Service:
- Build Command: pip install -r requirements.txt
- Start Command: gunicorn app:app
- Environment Variables: DATABASE_URL, SECRET_KEY, etc.

# Frontend Service:
- Build Command: npm run build
- Publish Directory: dist
- Environment Variables: VITE_API_URL

# PostgreSQL Database:
- Database Name: sentinel_trading
- User: postgres
```

### 4. Heroku (Alternativa)
```bash
# 1. Instalar Heroku CLI
# 2. Crear app
heroku create sentinel-trading

# 3. Añadir PostgreSQL
heroku addons:create heroku-postgresql:hobby-dev

# 4. Configurar variables
heroku config:set DATABASE_URL=$(heroku config:get DATABASE_URL)
heroku config:set SECRET_KEY=your_secret

# 5. Desplegar
git push heroku main
```

## 🔧 Configuración Específica

### 1. Base de Datos para Históricos

#### PostgreSQL (Supabase)
```sql
-- Crear tablas para datos históricos
CREATE TABLE market_data (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    open_price DECIMAL(10,2),
    high_price DECIMAL(10,2),
    low_price DECIMAL(10,2),
    close_price DECIMAL(10,2),
    volume BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_market_data_symbol_timestamp ON market_data(symbol, timestamp);

-- Tabla de predicciones
CREATE TABLE predictions (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    predicted_price DECIMAL(10,2),
    confidence_score DECIMAL(5,4),
    model_version VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_predictions_symbol_timestamp ON predictions(symbol, timestamp);
```

#### MongoDB Atlas
```javascript
// Colección para datos históricos
db.createCollection("market_data", {
  timeseries: {
    timeField: "timestamp",
    metaField: "symbol",
    granularity: "minutes"
  }
});

// Índices para rendimiento
db.market_data.createIndex({ "symbol": 1, "timestamp": -1 });
db.predictions.createIndex({ "symbol": 1, "timestamp": -1 });
```

### 2. Configuración de ML para Aprendizaje

#### MLflow para Tracking de Modelos
```bash
# 1. Iniciar MLflow
mlflow server --host 0.0.0.0 --port 5000 --default-artifact-root ./mlruns

# 2. Configurar en backend
export MLFLOW_TRACKING_URI=http://localhost:5000
```

#### Almacenamiento de Modelos
```python
# Guardar modelos entrenados
import joblib
import mlflow

# Guardar localmente
joblib.dump(model, 'models/trading_model_v1.pkl')

# Guardar en MLflow
mlflow.sklearn.log_model(
    model, 
    "trading_model",
    registered_model_name="sentinel_trading_model"
)
```

## 📊 Estrategia de Datos para Aprendizaje

### 1. Datos Históricos a Almacenar
- **Precios OHLCV**: Open, High, Low, Close, Volume
- **Predicciones**: Con timestamps y scores de confianza
- **Resultados**: Para validación de predicciones
- **Sentimiento**: Análisis de noticias y redes sociales
- **Eventos Económicos**: Calendario económico

### 2. Pipeline de Aprendizaje
```python
# 1. Recolectar datos históricos
historical_data = get_historical_data(symbols, period="5y")

# 2. Feature engineering
features = create_technical_indicators(historical_data)

# 3. Entrenar modelo
model = train_model(features, targets)

# 4. Validar
validation_score = validate_model(model, test_data)

# 5. Guardar si es mejor
if validation_score > best_score:
    save_model(model, version=f"v{get_next_version()}")
```

## 🌐 Configuración de Dominio

### 1. Dominio Personalizado
```bash
# En Vercel
vercel domains add sentinel-trading.com

# En Railway
railway domains add sentinel-trading.com

# En Render
# Configurar en dashboard de Render
```

### 2. HTTPS y SSL
- **Vercel**: Automático
- **Railway**: Automático
- **Render**: Automático
- **Propio**: Let's Encrypt con Certbot

## 📈 Monitoreo y Logs

### 1. Configurar Monitoring
```python
# Prometheus metrics
from prometheus_client import Counter, Histogram

REQUEST_COUNT = Counter('requests_total', 'Total requests')
REQUEST_LATENCY = Histogram('request_duration_seconds', 'Request latency')
```

### 2. Logs Centralizados
```bash
# Usar Sentry para errores
pip install sentry-sdk

# Configurar
import sentry_sdk
sentry_sdk.init(
    dsn="YOUR_SENTRY_DSN",
    traces_sample_rate=1.0
)
```

## 🚀 Checklist de Despliegue

### Pre-Despliegue
- [ ] Base de datos configurada y accesible
- [ ] Variables de entorno configuradas
- [ ] Tests pasando
- [ ] Build de frontend exitoso
- [ ] API endpoints funcionando

### Post-Despliegue
- [ ] Verificar conexión a base de datos
- [ ] Probar API endpoints
- [ ] Configurar monitoreo
- [ ] Setear backups automáticos
- [ ] Configurar dominio personalizado
- [ ] Probar flujo completo de usuario

## 💡 Recomendaciones

### Para Empezar (Gratis)
1. **Supabase** para base de datos
2. **Vercel** para frontend
3. **Railway** para backend
4. **MLflow local** para tracking de modelos

### Para Producción (Escalable)
1. **PostgreSQL en Supabase/Neon**
2. **Render/Railway** para backend
3. **Cloudflare CDN** para frontend
4. **Sentry** para monitoreo
5. **MLflow en la nube** para tracking

## 🔗 Enlaces Útiles

- [Supabase](https://supabase.com/)
- [Vercel](https://vercel.com/)
- [Railway](https://railway.app/)
- [Render](https://render.com/)
- [MLflow](https://mlflow.org/)
- [Sentry](https://sentry.io/)
