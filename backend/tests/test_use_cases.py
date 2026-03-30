"""
Unit tests for application use cases.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from app.application.use_cases import (
    IngestMarketDataUseCase,
    RunPredictionsUseCase,
    GetDashboardUseCase,
    FullPipelineUseCase,
    IngestNewsUseCase,
    EvaluatePredictionsUseCase
)
from app.domain.dto import AssetReadDto, QuoteBarDto
from app.domain.value_objects import Signal, AssetType


@pytest.mark.unit
class TestIngestMarketDataUseCase:
    """Test IngestMarketDataUseCase."""
    
    def test_execute_success(self, sample_asset, mock_external_apis):
        """Test successful market data ingestion."""
        # Arrange
        mock_repo = Mock()
        mock_gateway = Mock()
        mock_gateway.get_history.return_value = [
            QuoteBarDto(
                ts=datetime(2022, 1, 1),
                close=50000.0,
                open=49000.0,
                high=51000.0,
                low=48000.0,
                volume=1000000.0
            )
        ]
        
        use_case = IngestMarketDataUseCase(mock_repo, mock_gateway)
        
        # Act
        use_case.execute(sample_asset)
        
        # Assert
        mock_gateway.get_history.assert_called_once_with(sample_asset)
        mock_repo.save_quotes.assert_called_once()
    
    def test_execute_gateway_failure(self, sample_asset):
        """Test handling of gateway failure."""
        # Arrange
        mock_repo = Mock()
        mock_gateway = Mock()
        mock_gateway.get_history.side_effect = Exception("API Error")
        
        use_case = IngestMarketDataUseCase(mock_repo, mock_gateway)
        
        # Act & Assert
        with pytest.raises(Exception, match="API Error"):
            use_case.execute(sample_asset)
        
        mock_repo.save_quotes.assert_not_called()


@pytest.mark.unit
class TestRunPredictionsUseCase:
    """Test RunPredictionsUseCase."""
    
    def test_execute_with_sufficient_data(self):
        """Test prediction execution with sufficient historical data."""
        # Arrange
        mock_asset_repo = Mock()
        mock_quote_repo = Mock()
        mock_prediction_repo = Mock()
        
        # Mock asset
        asset = AssetReadDto(
            id=1,
            symbol="BTC",
            name="Bitcoin",
            asset_type=AssetType.crypto,
            external_id="bitcoin",
            provider="coingecko",
            news_keywords="bitcoin"
        )
        
        # Mock quotes (sufficient data)
        quotes = []
        base_date = datetime(2022, 1, 1)
        for i in range(60):  # 60 days of data
            quotes.append(QuoteBarDto(
                ts=base_date + timedelta(days=i),
                close=50000.0 + i * 100
            ))
        
        mock_asset_repo.get_all.return_value = [asset]
        mock_quote_repo.get_latest_quotes.return_value = quotes
        
        with patch('app.application.use_cases.prediction_model.predict') as mock_predict:
            mock_predict.return_value = (52000.0, 0.8, Signal.buy)
            
            use_case = RunPredictionsUseCase(
                mock_asset_repo,
                mock_quote_repo,
                mock_prediction_repo,
                Mock()  # config
            )
            
            # Act
            use_case.execute()
            
            # Assert
            mock_predict.assert_called_once()
            mock_prediction_repo.save.assert_called_once()
    
    def test_execute_insufficient_data(self):
        """Test prediction execution with insufficient historical data."""
        # Arrange
        mock_asset_repo = Mock()
        mock_quote_repo = Mock()
        mock_prediction_repo = Mock()
        
        asset = AssetReadDto(
            id=1,
            symbol="BTC",
            name="Bitcoin",
            asset_type=AssetType.crypto,
            external_id="bitcoin",
            provider="coingecko",
            news_keywords="bitcoin"
        )
        
        # Mock quotes (insufficient data)
        quotes = [
            QuoteBarDto(ts=datetime(2022, 1, 1), close=50000.0)
        ]
        
        mock_asset_repo.get_all.return_value = [asset]
        mock_quote_repo.get_latest_quotes.return_value = quotes
        
        use_case = RunPredictionsUseCase(
            mock_asset_repo,
            mock_quote_repo,
            mock_prediction_repo,
            Mock()  # config
        )
        
        # Act
        use_case.execute()
        
        # Assert
        mock_prediction_repo.save.assert_not_called()


@pytest.mark.unit
class TestGetDashboardUseCase:
    """Test GetDashboardUseCase."""
    
    def test_execute_success(self):
        """Test successful dashboard data retrieval."""
        # Arrange
        mock_asset_repo = Mock()
        mock_quote_repo = Mock()
        mock_prediction_repo = Mock()
        
        asset = AssetReadDto(
            id=1,
            symbol="BTC",
            name="Bitcoin",
            asset_type=AssetType.crypto,
            external_id="bitcoin",
            provider="coingecko",
            news_keywords="bitcoin"
        )
        
        quote = QuoteBarDto(
            ts=datetime(2022, 1, 1),
            close=50000.0,
            open=49000.0,
            high=51000.0,
            low=48000.0,
            volume=1000000.0
        )
        
        mock_asset_repo.get_all.return_value = [asset]
        mock_quote_repo.get_latest_by_asset.return_value = quote
        mock_prediction_repo.get_latest_by_asset.return_value = None
        
        use_case = GetDashboardUseCase(
            mock_asset_repo,
            mock_quote_repo,
            mock_prediction_repo
        )
        
        # Act
        result = use_case.execute()
        
        # Assert
        assert len(result) == 1
        assert result[0]['asset'] == asset
        assert result[0]['quote'] == quote
        assert result[0]['prediction'] is None


@pytest.mark.unit
class TestIngestNewsUseCase:
    """Test IngestNewsUseCase."""
    
    def test_execute_success(self):
        """Test successful news ingestion."""
        # Arrange
        mock_asset_repo = Mock()
        mock_news_aggregator = Mock()
        mock_news_write_repo = Mock()
        mock_sentiment_scorer = Mock()
        
        asset = AssetReadDto(
            id=1,
            symbol="BTC",
            name="Bitcoin",
            asset_type=AssetType.crypto,
            external_id="bitcoin",
            provider="coingecko",
            news_keywords="bitcoin"
        )
        
        # Mock news articles
        from app.domain.dto import NewsArticleRawDto
        articles = [
            NewsArticleRawDto(
                published_at=datetime(2022, 1, 1),
                title="Bitcoin reaches new high",
                url="https://example.com/news1",
                source="News Source",
                snippet="Bitcoin has reached a new all-time high"
            )
        ]
        
        mock_asset_repo.get_all.return_value = [asset]
        mock_news_aggregator.fetch_news.return_value = articles
        mock_sentiment_scorer.score_sentiment.return_value = 0.5
        
        use_case = IngestNewsUseCase(
            mock_asset_repo,
            mock_news_aggregator,
            mock_news_write_repo,
            mock_sentiment_scorer
        )
        
        # Act
        use_case.execute()
        
        # Assert
        mock_news_aggregator.fetch_news.assert_called_once()
        mock_sentiment_scorer.score_sentiment.assert_called_once()
        mock_news_write_repo.save_articles.assert_called_once()


@pytest.mark.unit
class TestEvaluatePredictionsUseCase:
    """Test EvaluatePredictionsUseCase."""
    
    def test_execute_with_due_predictions(self):
        """Test evaluation of due predictions."""
        # Arrange
        mock_prediction_repo = Mock()
        mock_quote_repo = Mock()
        
        from app.domain.dto import PredictionDueDto
        due_prediction = PredictionDueDto(
            id=1,
            asset_id=1,
            target_date=datetime(2022, 1, 1),
            base_price=50000.0,
            predicted_value=52000.0
        )
        
        actual_quote = QuoteBarDto(
            ts=datetime(2022, 1, 1),
            close=51500.0
        )
        
        mock_prediction_repo.get_due_predictions.return_value = [due_prediction]
        mock_quote_repo.get_quote_at_date.return_value = actual_quote
        
        use_case = EvaluatePredictionsUseCase(
            mock_prediction_repo,
            mock_quote_repo
        )
        
        # Act
        use_case.execute()
        
        # Assert
        mock_prediction_repo.get_due_predictions.assert_called_once()
        mock_quote_repo.get_quote_at_date.assert_called_once()
        mock_prediction_repo.save_evaluation.assert_called_once()
    
    def test_execute_no_due_predictions(self):
        """Test evaluation when no predictions are due."""
        # Arrange
        mock_prediction_repo = Mock()
        mock_quote_repo = Mock()
        
        mock_prediction_repo.get_due_predictions.return_value = []
        
        use_case = EvaluatePredictionsUseCase(
            mock_prediction_repo,
            mock_quote_repo
        )
        
        # Act
        use_case.execute()
        
        # Assert
        mock_prediction_repo.get_due_predictions.assert_called_once()
        mock_quote_repo.get_quote_at_date.assert_not_called()
        mock_prediction_repo.save_evaluation.assert_not_called()


@pytest.mark.unit
class TestFullPipelineUseCase:
    """Test FullPipelineUseCase."""
    
    def test_execute_success(self):
        """Test successful full pipeline execution."""
        # Arrange
        mock_ingest_market = Mock()
        mock_run_predictions = Mock()
        mock_ingest_news = Mock()
        mock_evaluate_predictions = Mock()
        
        use_case = FullPipelineUseCase(
            mock_ingest_market,
            mock_run_predictions,
            mock_ingest_news,
            mock_evaluate_predictions
        )
        
        # Act
        use_case.execute()
        
        # Assert
        mock_ingest_market.execute.assert_called_once()
        mock_run_predictions.execute.assert_called_once()
        mock_ingest_news.execute.assert_called_once()
        mock_evaluate_predictions.execute.assert_called_once()
    
    def test_execute_with_force_news(self):
        """Test full pipeline execution with force_news flag."""
        # Arrange
        mock_ingest_market = Mock()
        mock_run_predictions = Mock()
        mock_ingest_news = Mock()
        mock_evaluate_predictions = Mock()
        
        use_case = FullPipelineUseCase(
            mock_ingest_market,
            mock_run_predictions,
            mock_ingest_news,
            mock_evaluate_predictions
        )
        
        # Act
        use_case.execute(force_news=True)
        
        # Assert
        mock_ingest_market.execute.assert_called_once()
        mock_run_predictions.execute.assert_called_once()
        mock_ingest_news.execute.assert_called_once_with(force=True)
        mock_evaluate_predictions.execute.assert_called_once()
