"""
Pytest configuration and fixtures for Sentinel Trading tests.
"""

import pytest
import tempfile
import os
from typing import Generator
from unittest.mock import Mock, patch

from app import create_app
from app.extensions import db
from app.config import Config


class TestConfig(Config):
    """Test configuration with in-memory SQLite database."""
    TESTING = True
    DATABASE_URL = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    COINGECKO_DAYS = 30
    YFINANCE_PERIOD = "1y"


@pytest.fixture
def app() -> Generator:
    """Create application for testing."""
    app = create_app(TestConfig)
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create CLI test runner."""
    return app.test_cli_runner()


@pytest.fixture
def mock_coingecko_response():
    """Mock CoinGecko API response."""
    return {
        "prices": [
            [1640995200000, 47686.81],
            [1641081600000, 46869.92],
            [1641168000000, 41707.65],
        ],
        "market_caps": [
            [1640995200000, 896426834976],
            [1641081600000, 880988592128],
            [1641168000000, 785626767104],
        ],
        "total_volumes": [
            [1640995200000, 29972683668],
            [1641081600000, 36916663041],
            [1641168000000, 42862386683],
        ]
    }


@pytest.fixture
def mock_yfinance_response():
    """Mock Yahoo Finance API response."""
    import pandas as pd
    dates = pd.date_range('2022-01-01', periods=3, freq='D')
    return pd.DataFrame({
        'Open': [47686.81, 46869.92, 41707.65],
        'High': [47756.23, 47234.56, 42890.12],
        'Low': [46543.21, 41234.56, 40987.65],
        'Close': [46869.92, 41707.65, 42890.12],
        'Volume': [29972683668, 36916663041, 42862386683]
    }, index=dates)


@pytest.fixture
def sample_asset():
    """Sample asset for testing."""
    from app.domain.dto import AssetCreateDTO
    return AssetCreateDTO(
        symbol="BTC",
        name="Bitcoin",
        asset_type="crypto",
        coingecko_id="bitcoin",
        yfinance_ticker="BTC-USD"
    )


@pytest.fixture
def mock_external_apis():
    """Mock all external API calls."""
    with patch('requests.get') as mock_get, \
         patch('yfinance.download') as mock_yf:
        
        # Mock CoinGecko response
        mock_coingecko = Mock()
        mock_coingecko.json.return_value = {
            "prices": [[1640995200000, 47686.81]],
            "market_caps": [[1640995200000, 896426834976]],
            "total_volumes": [[1640995200000, 29972683668]]
        }
        mock_coingecko.raise_for_status.return_value = None
        mock_get.return_value = mock_coingecko
        
        # Mock Yahoo Finance response
        import pandas as pd
        dates = pd.date_range('2022-01-01', periods=1, freq='D')
        mock_yf.return_value = pd.DataFrame({
            'Open': [47686.81],
            'High': [47756.23],
            'Low': [46543.21],
            'Close': [46869.92],
            'Volume': [29972683668]
        }, index=dates)
        
        yield mock_get, mock_yf
