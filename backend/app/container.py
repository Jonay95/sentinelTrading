"""
Raíz de composición (Composition Root): ensambla adaptadores concretos y casos de uso.

Aquí es el único sitio donde las dependencias concretas se eligen; el resto del código
depende de abstracciones (puertos). Debe ejecutarse dentro de `app_context` de Flask.
"""

from __future__ import annotations

from app.application.use_cases import (
    EvaluatePredictionsUseCase,
    FullPipelineUseCase,
    GetDashboardUseCase,
    IngestMarketDataUseCase,
    IngestNewsUseCase,
    RunPredictionsUseCase,
)
from app.application.walk_forward import WalkForwardAnalysisService
from app.config import Config
from app.extensions import db
from app.infrastructure.adapters.market_data import (
    CoinGeckoHistoryAdapter,
    CompositeMarketHistoryGateway,
    YahooFinanceHistoryAdapter,
)
from app.infrastructure.adapters.news_and_sentiment import (
    FinnhubRemoteSource,
    NewsAggregator,
    NewsApiRemoteSource,
    VaderSentimentScorer,
)
from app.infrastructure.persistence.api_read_queries import ApiReadQueries
from app.infrastructure.persistence.metrics_query_service import MetricsQueryService
from app.infrastructure.persistence.repositories import (
    SqlAlchemyAssetRepository,
    SqlAlchemyNewsReadRepository,
    SqlAlchemyNewsWriteRepository,
    SqlAlchemyPredictionRepository,
    SqlAlchemyQuoteRepository,
)


class AppContainer:
    """
    Contenedor de dependencias por petición (o por llamada a fábrica).

    Single Responsibility: solo construye el grafo; no contiene lógica de negocio.
    """

    def __init__(self) -> None:
        session = db.session
        self._session = session

        self.assets = SqlAlchemyAssetRepository(session)
        self.quotes = SqlAlchemyQuoteRepository(session)
        self.predictions = SqlAlchemyPredictionRepository(session)
        self.news_read = SqlAlchemyNewsReadRepository(session)
        self.news_write = SqlAlchemyNewsWriteRepository(session)

        cg = CoinGeckoHistoryAdapter()
        yh = YahooFinanceHistoryAdapter()
        self.market_gateway = CompositeMarketHistoryGateway(Config, cg, yh)

        newsapi = NewsApiRemoteSource(Config)
        finnhub = FinnhubRemoteSource(Config)
        self.news_aggregator = NewsAggregator(Config, newsapi, finnhub)
        self.sentiment_scorer = VaderSentimentScorer()

        self.ingest_market = IngestMarketDataUseCase(self.assets, self.quotes, self.market_gateway)
        self.ingest_news = IngestNewsUseCase(
            Config,
            self.assets,
            self.news_read,
            self.news_write,
            self.news_aggregator,
            self.sentiment_scorer,
        )
        self.run_predictions = RunPredictionsUseCase(
            Config,
            self.assets,
            self.quotes,
            self.predictions,
            self.news_read,
        )
        self.evaluate_predictions = EvaluatePredictionsUseCase(self.predictions, self.quotes)
        self.dashboard = GetDashboardUseCase(self.assets, self.quotes, self.predictions)
        self.full_pipeline = FullPipelineUseCase(
            self.ingest_market,
            self.ingest_news,
            self.run_predictions,
            self.evaluate_predictions,
            Config,
        )
        self.walk_forward = WalkForwardAnalysisService(Config, self.assets, self.quotes)
        self.metrics_queries = MetricsQueryService(session)
        self.api_reads = ApiReadQueries(session)


def get_container() -> AppContainer:
    """Fábrica pública usada por controladores Flask y el scheduler."""
    return AppContainer()
