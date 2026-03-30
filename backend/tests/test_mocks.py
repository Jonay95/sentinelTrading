"""
Mock utilities for external API calls.
"""

import pytest
from unittest.mock import Mock, patch
import pandas as pd
from datetime import datetime, timedelta


class MockCoinGeckoAPI:
    """Mock CoinGecko API responses."""
    
    @staticmethod
    def get_price_history(coin_id="bitcoin", days=30):
        """Mock price history response."""
        base_date = datetime(2022, 1, 1)
        prices = []
        market_caps = []
        total_volumes = []
        
        for i in range(days):
            timestamp = int((base_date + timedelta(days=i)).timestamp() * 1000)
            base_price = 50000.0 + i * 100
            prices.append([timestamp, base_price])
            market_caps.append([timestamp, base_price * 19000000])  # ~19M BTC supply
            total_volumes.append([timestamp, 30000000000 + i * 100000000])  # 30B+ volume
        
        return {
            "prices": prices,
            "market_caps": market_caps,
            "total_volumes": total_volumes
        }
    
    @staticmethod
    def get_simple_price(coin_ids="bitcoin", vs_currencies="usd"):
        """Mock simple price response."""
        return {
            "bitcoin": {
                "usd": 50000.0
            }
        }


class MockYahooFinanceAPI:
    """Mock Yahoo Finance API responses."""
    
    @staticmethod
    def download_history(ticker="BTC-USD", period="1y"):
        """Mock download history response."""
        dates = pd.date_range('2022-01-01', periods=365, freq='D')
        base_price = 50000.0
        
        data = {
            'Open': [],
            'High': [],
            'Low': [],
            'Close': [],
            'Volume': []
        }
        
        for i, date in enumerate(dates):
            price = base_price + i * 10
            data['Open'].append(price * 0.99)
            data['High'].append(price * 1.02)
            data['Low'].append(price * 0.98)
            data['Close'].append(price)
            data['Volume'].append(30000000000 + i * 100000000)
        
        return pd.DataFrame(data, index=dates)


class MockNewsAPI:
    """Mock News API responses."""
    
    @staticmethod
    def get_news_articles(q="bitcoin", page_size=10):
        """Mock news articles response."""
        articles = []
        base_date = datetime(2022, 1, 1)
        
        for i in range(page_size):
            article = {
                "source": {"name": f"News Source {i+1}"},
                "author": f"Author {i+1}",
                "title": f"Bitcoin News Article {i+1}",
                "description": f"Description for Bitcoin news article {i+1}",
                "url": f"https://example.com/news/{i+1}",
                "urlToImage": f"https://example.com/images/{i+1}.jpg",
                "publishedAt": (base_date + timedelta(hours=i)).isoformat(),
                "content": f"Full content for Bitcoin news article {i+1}"
            }
            articles.append(article)
        
        return {
            "status": "ok",
            "totalResults": page_size,
            "articles": articles
        }


class MockFinnhubAPI:
    """Mock Finnhub API responses."""
    
    @staticmethod
    def get_company_news(symbol="BTC", from_date="2022-01-01", to_date="2022-01-02"):
        """Mock company news response."""
        articles = []
        base_date = datetime(2022, 1, 1)
        
        for i in range(5):
            article = {
                "category": "general",
                "datetime": int((base_date + timedelta(hours=i)).timestamp()),
                "headline": f"Bitcoin Headline {i+1}",
                "id": i + 1,
                "image": f"https://example.com/images/{i+1}.jpg",
                "related": "BTC",
                "source": "Finnhub",
                "summary": f"Summary for Bitcoin news {i+1}",
                "url": f"https://example.com/finnhub/{i+1}"
            }
            articles.append(article)
        
        return articles


@pytest.fixture
def mock_coingecko_api():
    """Fixture to mock CoinGecko API calls."""
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.json.side_effect = lambda: MockCoinGeckoAPI.get_price_history()
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        yield mock_get


@pytest.fixture
def mock_yahoo_finance_api():
    """Fixture to mock Yahoo Finance API calls."""
    with patch('yfinance.download') as mock_download:
        mock_download.return_value = MockYahooFinanceAPI.download_history()
        yield mock_download


@pytest.fixture
def mock_news_api():
    """Fixture to mock NewsAPI calls."""
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.json.side_effect = lambda: MockNewsAPI.get_news_articles()
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        yield mock_get


@pytest.fixture
def mock_finnhub_api():
    """Fixture to mock Finnhub API calls."""
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.json.side_effect = lambda: MockFinnhubAPI.get_company_news()
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        yield mock_get


@pytest.fixture
def mock_all_external_apis(mock_coingecko_api, mock_yahoo_finance_api, 
                           mock_news_api, mock_finnhub_api):
    """Fixture to mock all external APIs simultaneously."""
    return {
        'coingecko': mock_coingecko_api,
        'yahoo': mock_yahoo_finance_api,
        'newsapi': mock_news_api,
        'finnhub': mock_finnhub_api
    }


class MockAPIResponses:
    """Collection of mock API responses for testing."""
    
    COINGECKO_PRICE_HISTORY = MockCoinGeckoAPI.get_price_history()
    YAHOO_FINANCE_HISTORY = MockYahooFinanceAPI.download_history()
    NEWSAPI_ARTICLES = MockNewsAPI.get_news_articles()
    FINNHUB_NEWS = MockFinnhubAPI.get_company_news()
    
    @staticmethod
    def create_coingecko_failure():
        """Create a mock CoinGecko API failure response."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = Exception("CoinGecko API Error")
        return mock_response
    
    @staticmethod
    def create_yahoo_finance_failure():
        """Create a mock Yahoo Finance API failure response."""
        mock_response = Mock()
        mock_response.side_effect = Exception("Yahoo Finance API Error")
        return mock_response
    
    @staticmethod
    def create_newsapi_failure():
        """Create a mock NewsAPI failure response."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = Exception("NewsAPI Error")
        return mock_response


def setup_api_mocks():
    """Setup function to configure all API mocks."""
    return {
        'coingecko': MockCoinGeckoAPI(),
        'yahoo': MockYahooFinanceAPI(),
        'newsapi': MockNewsAPI(),
        'finnhub': MockFinnhubAPI()
    }
