"""
Unit tests for domain models and value objects.
"""

import pytest
from datetime import datetime
from dataclasses import FrozenInstanceError

from app.domain.dto import AssetReadDto, QuoteBarDto, NewsArticleRawDto, PredictionDueDto
from app.domain.value_objects import AssetType, Signal


@pytest.mark.unit
class TestAssetReadDto:
    """Test AssetReadDto dataclass."""
    
    def test_asset_read_dto_creation(self):
        """Test creating AssetReadDto with valid data."""
        asset = AssetReadDto(
            id=1,
            symbol="BTC",
            name="Bitcoin",
            asset_type="crypto",
            external_id="bitcoin",
            provider="coingecko",
            news_keywords="bitcoin,cryptocurrency"
        )
        
        assert asset.id == 1
        assert asset.symbol == "BTC"
        assert asset.name == "Bitcoin"
        assert asset.asset_type == "crypto"
        assert asset.external_id == "bitcoin"
        assert asset.provider == "coingecko"
        assert asset.news_keywords == "bitcoin,cryptocurrency"
    
    def test_asset_read_dto_immutability(self):
        """Test that AssetReadDto is immutable."""
        asset = AssetReadDto(
            id=1,
            symbol="BTC",
            name="Bitcoin",
            asset_type="crypto",
            external_id=None,
            provider="yahoo",
            news_keywords=None
        )
        
        with pytest.raises(FrozenInstanceError):
            asset.symbol = "ETH"
    
    def test_asset_read_dto_optional_fields(self):
        """Test AssetReadDto with optional fields as None."""
        asset = AssetReadDto(
            id=1,
            symbol="AAPL",
            name="Apple Inc.",
            asset_type="stock",
            external_id=None,
            provider="yahoo",
            news_keywords=None
        )
        
        assert asset.external_id is None
        assert asset.news_keywords is None


@pytest.mark.unit
class TestQuoteBarDto:
    """Test QuoteBarDto dataclass."""
    
    def test_quote_bar_dto_creation_minimal(self):
        """Test creating QuoteBarDto with minimal required fields."""
        timestamp = datetime(2022, 1, 1, 12, 0, 0)
        quote = QuoteBarDto(
            ts=timestamp,
            close=50000.0
        )
        
        assert quote.ts == timestamp
        assert quote.close == 50000.0
        assert quote.open is None
        assert quote.high is None
        assert quote.low is None
        assert quote.volume is None
    
    def test_quote_bar_dto_creation_full(self):
        """Test creating QuoteBarDto with all fields."""
        timestamp = datetime(2022, 1, 1, 12, 0, 0)
        quote = QuoteBarDto(
            ts=timestamp,
            close=50000.0,
            open=49000.0,
            high=51000.0,
            low=48000.0,
            volume=1000000.0
        )
        
        assert quote.ts == timestamp
        assert quote.close == 50000.0
        assert quote.open == 49000.0
        assert quote.high == 51000.0
        assert quote.low == 48000.0
        assert quote.volume == 1000000.0
    
    def test_quote_bar_dto_immutability(self):
        """Test that QuoteBarDto is immutable."""
        timestamp = datetime(2022, 1, 1, 12, 0, 0)
        quote = QuoteBarDto(ts=timestamp, close=50000.0)
        
        with pytest.raises(FrozenInstanceError):
            quote.close = 51000.0


@pytest.mark.unit
class TestNewsArticleRawDto:
    """Test NewsArticleRawDto dataclass."""
    
    def test_news_article_dto_creation_full(self):
        """Test creating NewsArticleRawDto with all fields."""
        timestamp = datetime(2022, 1, 1, 12, 0, 0)
        news = NewsArticleRawDto(
            published_at=timestamp,
            title="Bitcoin reaches new all-time high",
            url="https://example.com/news/btc-high",
            source="Crypto News",
            snippet="Bitcoin has reached a new all-time high today..."
        )
        
        assert news.published_at == timestamp
        assert news.title == "Bitcoin reaches new all-time high"
        assert news.url == "https://example.com/news/btc-high"
        assert news.source == "Crypto News"
        assert news.snippet == "Bitcoin has reached a new all-time high today..."
    
    def test_news_article_dto_creation_minimal(self):
        """Test creating NewsArticleRawDto with minimal required fields."""
        timestamp = datetime(2022, 1, 1, 12, 0, 0)
        news = NewsArticleRawDto(
            published_at=timestamp,
            title="Bitcoin reaches new all-time high",
            url=None,
            source=None,
            snippet=None
        )
        
        assert news.published_at == timestamp
        assert news.title == "Bitcoin reaches new all-time high"
        assert news.url is None
        assert news.source is None
        assert news.snippet is None


@pytest.mark.unit
class TestPredictionDueDto:
    """Test PredictionDueDto dataclass."""
    
    def test_prediction_due_dto_creation(self):
        """Test creating PredictionDueDto."""
        target_date = datetime(2022, 1, 2, 12, 0, 0)
        prediction = PredictionDueDto(
            id=1,
            asset_id=1,
            target_date=target_date,
            base_price=50000.0,
            predicted_value=52000.0
        )
        
        assert prediction.id == 1
        assert prediction.asset_id == 1
        assert prediction.target_date == target_date
        assert prediction.base_price == 50000.0
        assert prediction.predicted_value == 52000.0


@pytest.mark.unit
class TestAssetType:
    """Test AssetType enum."""
    
    def test_asset_type_values(self):
        """Test AssetType enum values."""
        assert AssetType.crypto == "crypto"
        assert AssetType.stock == "stock"
        assert AssetType.commodity == "commodity"
    
    def test_asset_type_is_string_enum(self):
        """Test that AssetType is a string enum."""
        assert isinstance(AssetType.crypto, str)
        assert isinstance(AssetType.stock, str)
        assert isinstance(AssetType.commodity, str)
    
    def test_asset_type_iteration(self):
        """Test iterating over AssetType values."""
        values = list(AssetType)
        assert len(values) == 3
        assert AssetType.crypto in values
        assert AssetType.stock in values
        assert AssetType.commodity in values


@pytest.mark.unit
class TestSignal:
    """Test Signal enum."""
    
    def test_signal_values(self):
        """Test Signal enum values."""
        assert Signal.buy == "buy"
        assert Signal.sell == "sell"
        assert Signal.hold == "hold"
    
    def test_signal_is_string_enum(self):
        """Test that Signal is a string enum."""
        assert isinstance(Signal.buy, str)
        assert isinstance(Signal.sell, str)
        assert isinstance(Signal.hold, str)
    
    def test_signal_iteration(self):
        """Test iterating over Signal values."""
        values = list(Signal)
        assert len(values) == 3
        assert Signal.buy in values
        assert Signal.sell in values
        assert Signal.hold in values
