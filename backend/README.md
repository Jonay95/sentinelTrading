# Sentinel Trading — Backend

## APIs externas

| Proveedor | Uso | Clave |
|-----------|-----|--------|
| **CoinGecko** | Cotizaciones crypto (BTC, ETH, …) + volumen | No requiere clave para uso básico |
| **yfinance** | Acciones / ETFs / futuros vía Yahoo | Sin clave (no oficial; puede fallar) |
| **Finnhub** (opcional) | Noticias por ticker | [finnhub.io](https://finnhub.io/register) → `FINNHUB_API_KEY` |
| **NewsAPI** (opcional) | Noticias por keywords | [newsapi.org](https://newsapi.org) → `NEWS_API_KEY` |

Copia `.env.example` a `.env` y ajusta `DATABASE_URL` y orígenes CORS.

## Arquitectura hexagonal y SOLID (backend)

El código sigue **puertos y adaptadores** y la regla de dependencias hacia dentro:

| Capa | Carpeta | Rol |
|------|---------|-----|
| **Dominio** | `app/domain/` | Enums (`value_objects`), DTOs de frontera (`dto`), **puertos** (`ports/`), modelo estadístico puro (`services/prediction_model.py`). Sin Flask ni SQL. |
| **Aplicación** | `app/application/` | **Casos de uso** (`use_cases.py`, `walk_forward.py`): orquestan puertos; no conocen HTTP ni detalles de APIs externas. |
| **Infraestructura** | `app/infrastructure/` | **ORM** (`persistence/orm_models.py`), **repositorios** SQLAlchemy, **adaptadores** HTTP (CoinGecko, Yahoo, NewsAPI, Finnhub, VADER), consultas de lectura para la API. |
| **Presentación** | `app/api/` | Blueprints Flask delgados: parsean request → `get_container()` → caso de uso / consulta. |
| **Composición** | `app/container.py` | **Composition root**: único lugar donde se instancian implementaciones concretas (DIP). |

Principios aplicados: **S**RP por clase de caso de uso / adaptador; **O**CP vía nuevos adaptadores que cumplen `Protocol`; **L**SP con implementaciones sustituibles; **I**SG con puertos pequeños (`IQuoteRepository`, `IMarketHistoryGateway`, …); **D**IP con dependencias hacia abstracciones.

`app/models.py` reexporta el ORM y enums para **Alembic** y código legado (`seed`, `wsgi`). El paquete `app/services/` quedó vacío (solo nota de migración).

## Modelo predictivo (variables `.env`)

- **PRED_ENSEMBLE** (`1`/`0`): con historia suficiente (≥ 20 puntos), combina **ARIMA(1,0,1)** sobre retornos log y **suavizado exponencial Holt** (sin estacionalidad); si no, prioriza ARIMA / medias móviles.
- **MOMENTUM_BLEND**: ajuste leve del precio predicho según momentum 5d (`0` lo desactiva).
- **THRESHOLD_BASE_PCT**, **VOL_THRESHOLD_MULTIPLIER**, **THRESHOLD_MAX_PCT**: umbral de señal comprar/vender = `max(base, mult × volatilidad_20d_logret)`, acotado al máximo (más volatilidad → hace falta un movimiento esperado mayor para salir de “mantener”).
- Volatilidad extrema (vs histórico): se fuerza señal **mantener** y se reduce la confianza (**HIGH_VOL_CONFIDENCE_PENALTY**).
- **HORIZON_DAYS**: días hasta `target_date` de la predicción guardada.
- **COINGECKO_DAYS** (máx. 365 en intervalo diario) y **YFINANCE_PERIOD** (p. ej. `1y`, `2y`, `max`): más historia suele estabilizar el modelo.

## Backtest walk-forward (no escribe en BD)

Validación histórica: en cada paso solo se usan cotizaciones hasta `t`, se predice `t+1` y se compara con el cierre real.

- `GET /api/metrics/walk-forward?train_min=55&step=3&ensemble=1` — todos los activos.
- `GET /api/metrics/walk-forward?asset_id=1&step=2` — un activo.

En el frontend: página **Métricas** → botón *Ejecutar walk-forward*.

## Noticias y cuota gratuita

- **NEWS_MIN_INTERVAL_HOURS**: si ya hubo noticias ingestadas recientemente para el activo, se **omite** una nueva llamada a la API (ahorra límites del plan gratis).
- Forzar ingesta: `POST /api/jobs/news?force=1` o `POST /api/jobs/full-pipeline?force_news=1`.
- **NEWS_PAGE_SIZE**: artículos por petición a NewsAPI.

## Arranque

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
copy .env.example .env
python run.py
```

En el primer arranque se crean las tablas SQLite si no existen (`assets`, etc.) y se insertan activos por defecto.

Migraciones opcionales: `set FLASK_APP=wsgi:app` y `flask db migrate` / `flask db upgrade` cuando añadas modelos.

## Frontend (React)

En otra terminal, desde la raíz del repo:

```bash
cd frontend
npm install
npm run dev
```

Vite proxy reenvía `/api` a `http://127.0.0.1:5000`. En el panel pulsa **Actualizar datos y predicciones** o `POST /api/jobs/full-pipeline`.

## Jobs programados

Con `python run.py` se inicia APScheduler: ingesta diaria, predicciones, evaluación de predicciones vencidas y noticias (respetando `NEWS_MIN_INTERVAL_HOURS`).
