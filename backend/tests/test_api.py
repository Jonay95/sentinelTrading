"""
Integration tests for API endpoints.
"""

import pytest
import json
from unittest.mock import patch, Mock

from app.domain.dto import AssetReadDto, QuoteBarDto
from app.domain.value_objects import Signal, AssetType


@pytest.mark.integration
class TestDashboardAPI:
    """Test dashboard API endpoints."""
    
    def test_get_dashboard_success(self, client, app):
        """Test GET /api/dashboard endpoint."""
        # Arrange
        with app.app_context():
            # Mock the use case
            mock_use_case = Mock()
            mock_use_case.execute.return_value = [
                {
                    'asset': AssetReadDto(
                        id=1,
                        symbol="BTC",
                        name="Bitcoin",
                        asset_type=AssetType.crypto,
                        external_id="bitcoin",
                        provider="coingecko",
                        news_keywords="bitcoin"
                    ),
                    'quote': QuoteBarDto(
                        ts=datetime(2022, 1, 1),
                        close=50000.0,
                        open=49000.0,
                        high=51000.0,
                        low=48000.0,
                        volume=1000000.0
                    ),
                    'prediction': None
                }
            ]
            
            with patch('app.api.dashboard.get_container') as mock_container:
                mock_container.return_value.get_dashboard_use_case.return_value = mock_use_case
                
                # Act
                response = client.get('/api/dashboard')
                
                # Assert
                assert response.status_code == 200
                data = json.loads(response.data)
                assert len(data) == 1
                assert data[0]['asset']['symbol'] == 'BTC'
                assert data[0]['quote']['close'] == 50000.0
    
    def test_get_dashboard_empty(self, client, app):
        """Test GET /api/dashboard with no data."""
        with app.app_context():
            mock_use_case = Mock()
            mock_use_case.execute.return_value = []
            
            with patch('app.api.dashboard.get_container') as mock_container:
                mock_container.return_value.get_dashboard_use_case.return_value = mock_use_case
                
                response = client.get('/api/dashboard')
                
                assert response.status_code == 200
                data = json.loads(response.data)
                assert data == []


@pytest.mark.integration
class TestAssetsAPI:
    """Test assets API endpoints."""
    
    def test_get_assets_success(self, client, app):
        """Test GET /api/assets endpoint."""
        with app.app_context():
            mock_repo = Mock()
            mock_repo.get_all.return_value = [
                AssetReadDto(
                    id=1,
                    symbol="BTC",
                    name="Bitcoin",
                    asset_type=AssetType.crypto,
                    external_id="bitcoin",
                    provider="coingecko",
                    news_keywords="bitcoin"
                )
            ]
            
            with patch('app.api.assets.get_container') as mock_container:
                mock_container.return_value.asset_repository.return_value = mock_repo
                
                response = client.get('/api/assets')
                
                assert response.status_code == 200
                data = json.loads(response.data)
                assert len(data) == 1
                assert data[0]['symbol'] == 'BTC'
    
    def test_get_asset_by_id_success(self, client, app):
        """Test GET /api/assets/{id} endpoint."""
        with app.app_context():
            mock_repo = Mock()
            mock_repo.get_by_id.return_value = AssetReadDto(
                id=1,
                symbol="BTC",
                name="Bitcoin",
                asset_type=AssetType.crypto,
                external_id="bitcoin",
                provider="coingecko",
                news_keywords="bitcoin"
            )
            
            with patch('app.api.assets.get_container') as mock_container:
                mock_container.return_value.asset_repository.return_value = mock_repo
                
                response = client.get('/api/assets/1')
                
                assert response.status_code == 200
                data = json.loads(response.data)
                assert data['symbol'] == 'BTC'
    
    def test_get_asset_by_id_not_found(self, client, app):
        """Test GET /api/assets/{id} with non-existent asset."""
        with app.app_context():
            mock_repo = Mock()
            mock_repo.get_by_id.return_value = None
            
            with patch('app.api.assets.get_container') as mock_container:
                mock_container.return_value.asset_repository.return_value = mock_repo
                
                response = client.get('/api/assets/999')
                
                assert response.status_code == 404


@pytest.mark.integration
class TestJobsAPI:
    """Test jobs API endpoints."""
    
    def test_post_full_pipeline_success(self, client, app):
        """Test POST /api/jobs/full-pipeline endpoint."""
        with app.app_context():
            mock_use_case = Mock()
            
            with patch('app.api.jobs.get_container') as mock_container:
                mock_container.return_value.full_pipeline_use_case.return_value = mock_use_case
                
                response = client.post('/api/jobs/full-pipeline')
                
                assert response.status_code == 202
                data = json.loads(response.data)
                assert 'message' in data
                mock_use_case.execute.assert_called_once()
    
    def test_post_full_pipeline_with_force_news(self, client, app):
        """Test POST /api/jobs/full-pipeline with force_news parameter."""
        with app.app_context():
            mock_use_case = Mock()
            
            with patch('app.api.jobs.get_container') as mock_container:
                mock_container.return_value.full_pipeline_use_case.return_value = mock_use_case
                
                response = client.post('/api/jobs/full-pipeline?force_news=1')
                
                assert response.status_code == 202
                mock_use_case.execute.assert_called_once_with(force_news=True)
    
    def test_post_ingest_market_data_success(self, client, app):
        """Test POST /api/jobs/market-data endpoint."""
        with app.app_context():
            mock_use_case = Mock()
            
            with patch('app.api.jobs.get_container') as mock_container:
                mock_container.return_value.ingest_market_data_use_case.return_value = mock_use_case
                
                response = client.post('/api/jobs/market-data')
                
                assert response.status_code == 202
                mock_use_case.execute.assert_called_once()
    
    def test_post_run_predictions_success(self, client, app):
        """Test POST /api/jobs/predictions endpoint."""
        with app.app_context():
            mock_use_case = Mock()
            
            with patch('app.api.jobs.get_container') as mock_container:
                mock_container.return_value.run_predictions_use_case.return_value = mock_use_case
                
                response = client.post('/api/jobs/predictions')
                
                assert response.status_code == 202
                mock_use_case.execute.assert_called_once()


@pytest.mark.integration
class TestMetricsAPI:
    """Test metrics API endpoints."""
    
    def test_get_walk_forward_success(self, client, app):
        """Test GET /api/metrics/walk-forward endpoint."""
        with app.app_context():
            mock_service = Mock()
            mock_service.run_walk_forward.return_value = {
                'total_assets': 1,
                'results': [
                    {
                        'asset_id': 1,
                        'symbol': 'BTC',
                        'mae': 0.02,
                        'directional_accuracy': 0.65,
                        'total_predictions': 100
                    }
                ]
            }
            
            with patch('app.api.metrics.get_container') as mock_container:
                mock_container.return_value.walk_forward_service.return_value = mock_service
                
                response = client.get('/api/metrics/walk-forward')
                
                assert response.status_code == 200
                data = json.loads(response.data)
                assert 'total_assets' in data
                assert 'results' in data
                assert len(data['results']) == 1
    
    def test_get_walk_forward_with_parameters(self, client, app):
        """Test GET /api/metrics/walk-forward with query parameters."""
        with app.app_context():
            mock_service = Mock()
            mock_service.run_walk_forward.return_value = {
                'total_assets': 1,
                'results': []
            }
            
            with patch('app.api.metrics.get_container') as mock_container:
                mock_container.return_value.walk_forward_service.return_value = mock_service
                
                response = client.get('/api/metrics/walk-forward?train_min=55&step=3&ensemble=1')
                
                assert response.status_code == 200
                mock_service.run_walk_forward.assert_called_once_with(
                    train_min=55, step=3, ensemble=1, asset_id=None
                )


@pytest.mark.integration
class TestNewsAPI:
    """Test news API endpoints."""
    
    def test_get_news_success(self, client, app):
        """Test GET /api/news endpoint."""
        with app.app_context():
            mock_repo = Mock()
            mock_repo.get_latest_articles.return_value = [
                {
                    'id': 1,
                    'title': 'Bitcoin reaches new high',
                    'url': 'https://example.com/news1',
                    'source': 'News Source',
                    'published_at': '2022-01-01T12:00:00',
                    'sentiment_score': 0.5
                }
            ]
            
            with patch('app.api.news.get_container') as mock_container:
                mock_container.return_value.news_read_repository.return_value = mock_repo
                
                response = client.get('/api/news')
                
                assert response.status_code == 200
                data = json.loads(response.data)
                assert len(data) == 1
                assert data[0]['title'] == 'Bitcoin reaches new high'
    
    def test_get_news_with_asset_filter(self, client, app):
        """Test GET /api/news with asset_id filter."""
        with app.app_context():
            mock_repo = Mock()
            mock_repo.get_latest_articles.return_value = []
            
            with patch('app.api.news.get_container') as mock_container:
                mock_container.return_value.news_read_repository.return_value = mock_repo
                
                response = client.get('/api/news?asset_id=1')
                
                assert response.status_code == 200
                mock_repo.get_latest_articles.assert_called_once_with(asset_id=1, limit=50)


@pytest.mark.integration
class TestPredictionsAPI:
    """Test predictions API endpoints."""
    
    def test_get_predictions_success(self, client, app):
        """Test GET /api/predictions endpoint."""
        with app.app_context():
            mock_repo = Mock()
            mock_repo.get_latest_by_asset.return_value = {
                'id': 1,
                'asset_id': 1,
                'target_date': '2022-01-02',
                'predicted_value': 52000.0,
                'confidence': 0.8,
                'signal': 'buy'
            }
            
            with patch('app.api.predictions.get_container') as mock_container:
                mock_container.return_value.prediction_repository.return_value = mock_repo
                
                response = client.get('/api/predictions?asset_id=1')
                
                assert response.status_code == 200
                data = json.loads(response.data)
                assert data['predicted_value'] == 52000.0
                assert data['signal'] == 'buy'
    
    def test_get_predictions_not_found(self, client, app):
        """Test GET /api/predictions when no prediction exists."""
        with app.app_context():
            mock_repo = Mock()
            mock_repo.get_latest_by_asset.return_value = None
            
            with patch('app.api.predictions.get_container') as mock_container:
                mock_container.return_value.prediction_repository.return_value = mock_repo
                
                response = client.get('/api/predictions?asset_id=1')
                
                assert response.status_code == 404


# Import datetime for test usage
from datetime import datetime
