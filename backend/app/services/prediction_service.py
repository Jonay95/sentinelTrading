"""
Extracted prediction service for microservices architecture.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
import uuid
import json
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
import uvicorn

from app.infrastructure.logging_config import LoggerMixin
from app.infrastructure.cache import get_cache
from app.infrastructure.metrics import get_metrics
from app.infrastructure.mlflow_manager import get_mlflow_manager
from app.infrastructure.feature_engineering import get_feature_engineer
from app.infrastructure.model_explainability import get_explainability_manager
from app.container import get_container

logger = logging.getLogger(__name__)


class PredictionStatus(Enum):
    """Prediction request status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class PredictionType(Enum):
    """Types of predictions."""
    SINGLE_ASSET = "single_asset"
    PORTFOLIO = "portfolio"
    BATCH = "batch"
    REAL_TIME = "real_time"


@dataclass
class PredictionRequest:
    """Prediction request data."""
    request_id: str
    asset_symbols: List[str]
    prediction_type: PredictionType
    model_name: str
    model_version: str
    features: Dict[str, Any]
    timestamp: datetime
    status: PredictionStatus
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    processing_time: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['prediction_type'] = self.prediction_type.value
        result['status'] = self.status.value
        result['timestamp'] = self.timestamp.isoformat()
        return result


class PredictionRequestModel(BaseModel):
    """Pydantic model for prediction requests."""
    asset_symbols: List[str] = Field(..., description="List of asset symbols to predict")
    prediction_type: str = Field(default="single_asset", description="Type of prediction")
    model_name: str = Field(default="trading_model", description="Model name to use")
    model_version: Optional[str] = Field(default=None, description="Model version to use")
    features: Dict[str, Any] = Field(default={}, description="Additional features for prediction")
    priority: str = Field(default="normal", description="Request priority")


class PredictionResponseModel(BaseModel):
    """Pydantic model for prediction responses."""
    request_id: str
    status: str
    predictions: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    processing_time: Optional[float] = None
    timestamp: str


class PredictionService(LoggerMixin):
    """Extracted prediction service for microservices architecture."""
    
    def __init__(self):
        self.metrics = get_metrics()
        self.cache = get_cache()
        self.mlflow_manager = get_mlflow_manager()
        self.feature_engineer = get_feature_engineer()
        self.explainability_manager = get_explainability_manager()
        self.container = get_container()
        
        # Prediction request storage
        self.requests = {}  # request_id -> PredictionRequest
        self.request_queue = asyncio.Queue()
        self.processing = False
        
        # Model cache
        self.model_cache = {}
        self.model_cache_ttl = 3600  # 1 hour
    
    async def create_prediction_request(self, request_data: PredictionRequestModel) -> str:
        """Create a new prediction request."""
        try:
            request_id = str(uuid.uuid4())
            
            # Validate request
            if not request_data.asset_symbols:
                raise ValueError("Asset symbols are required")
            
            # Create prediction request
            request = PredictionRequest(
                request_id=request_id,
                asset_symbols=request_data.asset_symbols,
                prediction_type=PredictionType(request_data.prediction_type),
                model_name=request_data.model_name,
                model_version=request_data.model_version or "latest",
                features=request_data.features,
                timestamp=datetime.utcnow(),
                status=PredictionStatus.PENDING
            )
            
            # Store request
            self.requests[request_id] = request
            
            # Add to processing queue
            await self.request_queue.put(request_id)
            
            self.logger.info(f"Created prediction request {request_id} for {len(request_data.asset_symbols)} assets")
            
            # Record metrics
            self.metrics.record_trading_signal(
                signal_type="prediction_request_created",
                asset_symbol=request_id
            )
            
            return request_id
            
        except Exception as e:
            self.logger.error(f"Error creating prediction request: {e}")
            raise
    
    async def get_prediction_status(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a prediction request."""
        try:
            if request_id not in self.requests:
                return None
            
            request = self.requests[request_id]
            
            return {
                "request_id": request.request_id,
                "status": request.status.value,
                "asset_symbols": request.asset_symbols,
                "prediction_type": request.prediction_type.value,
                "timestamp": request.timestamp.isoformat(),
                "processing_time": request.processing_time,
                "error_message": request.error_message
            }
            
        except Exception as e:
            self.logger.error(f"Error getting prediction status: {e}")
            return None
    
    async def get_prediction_result(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Get prediction result."""
        try:
            if request_id not in self.requests:
                return None
            
            request = self.requests[request_id]
            
            if request.status != PredictionStatus.COMPLETED:
                return None
            
            return {
                "request_id": request.request_id,
                "predictions": request.result,
                "processing_time": request.processing_time,
                "timestamp": request.timestamp.isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting prediction result: {e}")
            return None
    
    async def process_predictions(self):
        """Process prediction requests from queue."""
        if self.processing:
            return
        
        self.processing = True
        
        try:
            while True:
                # Get request from queue
                try:
                    request_id = await asyncio.wait_for(self.request_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                
                if request_id not in self.requests:
                    continue
                
                request = self.requests[request_id]
                
                try:
                    # Update status to processing
                    request.status = PredictionStatus.PROCESSING
                    start_time = datetime.utcnow()
                    
                    # Process prediction
                    result = await self._process_prediction_request(request)
                    
                    # Update request with result
                    request.result = result
                    request.status = PredictionStatus.COMPLETED
                    request.processing_time = (datetime.utcnow() - start_time).total_seconds()
                    
                    self.logger.info(f"Completed prediction request {request_id}")
                    
                    # Record metrics
                    self.metrics.record_trading_signal(
                        signal_type="prediction_completed",
                        asset_symbol=request_id
                    )
                    
                except Exception as e:
                    # Update request with error
                    request.status = PredictionStatus.FAILED
                    request.error_message = str(e)
                    request.processing_time = (datetime.utcnow() - start_time).total_seconds()
                    
                    self.logger.error(f"Failed prediction request {request_id}: {e}")
                    
                    # Record error metrics
                    self.metrics.record_error("prediction_processing_error", request_id)
                
        except Exception as e:
            self.logger.error(f"Error in prediction processing loop: {e}")
        finally:
            self.processing = False
    
    async def _process_prediction_request(self, request: PredictionRequest) -> Dict[str, Any]:
        """Process a single prediction request."""
        try:
            # Load model
            model = await self._load_model(request.model_name, request.model_version)
            
            # Get market data for assets
            market_data = await self._get_market_data(request.asset_symbols)
            
            # Engineer features
            features = await self._engineer_features(market_data, request.features)
            
            # Generate predictions
            predictions = await self._generate_predictions(model, features, request.asset_symbols)
            
            # Add explanations if requested
            if "explainability" in request.features and request.features["explainability"]:
                explanations = await self._generate_explanations(model, features, request.asset_symbols)
                predictions["explanations"] = explanations
            
            # Add metadata
            predictions["metadata"] = {
                "model_name": request.model_name,
                "model_version": request.model_version,
                "prediction_type": request.prediction_type.value,
                "timestamp": datetime.utcnow().isoformat(),
                "asset_count": len(request.asset_symbols)
            }
            
            return predictions
            
        except Exception as e:
            self.logger.error(f"Error processing prediction request: {e}")
            raise
    
    async def _load_model(self, model_name: str, model_version: str):
        """Load model from MLflow."""
        try:
            cache_key = f"model:{model_name}:{model_version}"
            
            # Check cache first
            if cache_key in self.model_cache:
                return self.model_cache[cache_key]
            
            # Load from MLflow
            model = self.mlflow_manager.load_model(model_name, version=model_version)
            
            # Cache model
            self.model_cache[cache_key] = model
            
            return model
            
        except Exception as e:
            self.logger.error(f"Error loading model {model_name}:{model_version}: {e}")
            raise
    
    async def _get_market_data(self, asset_symbols: List[str]) -> Dict[str, Any]:
        """Get market data for assets."""
        try:
            market_data = {}
            
            for symbol in asset_symbols:
                # Get asset
                asset = self.container.asset_repository().get_by_symbol(symbol)
                if not asset:
                    continue
                
                # Get recent quotes
                end_date = datetime.utcnow()
                start_date = end_date - timedelta(days=60)  # Get 60 days of data
                
                quotes = self.container.quote_repository().get_by_asset_and_date_range(
                    asset.id, start_date, end_date
                )
                
                if quotes:
                    # Convert to DataFrame
                    df = pd.DataFrame([
                        {
                            'timestamp': q.timestamp,
                            'open': q.open,
                            'high': q.high,
                            'low': q.low,
                            'close': q.close,
                            'volume': q.volume
                        }
                        for q in quotes
                    ])
                    
                    market_data[symbol] = df
            
            return market_data
            
        except Exception as e:
            self.logger.error(f"Error getting market data: {e}")
            raise
    
    async def _engineer_features(self, market_data: Dict[str, Any], additional_features: Dict[str, Any]) -> Dict[str, Any]:
        """Engineer features for prediction."""
        try:
            engineered_features = {}
            
            for symbol, df in market_data.items():
                if df.empty:
                    continue
                
                # Use feature engineer
                features_df = self.feature_engineer.engineer_features(df)
                
                # Add additional features
                for key, value in additional_features.items():
                    if isinstance(value, (int, float)):
                        features_df[key] = value
                
                engineered_features[symbol] = features_df
            
            return engineered_features
            
        except Exception as e:
            self.logger.error(f"Error engineering features: {e}")
            raise
    
    async def _generate_predictions(self, model, features: Dict[str, Any], asset_symbols: List[str]) -> Dict[str, Any]:
        """Generate predictions using the model."""
        try:
            predictions = {}
            
            for symbol in asset_symbols:
                if symbol not in features:
                    continue
                
                features_df = features[symbol]
                
                if features_df.empty:
                    continue
                
                # Get latest features
                latest_features = features_df.iloc[-1:].values
                
                # Make prediction
                prediction = model.predict(latest_features)[0]
                
                # Get prediction probability if available
                probability = None
                if hasattr(model, 'predict_proba'):
                    probabilities = model.predict_proba(latest_features)[0]
                    probability = max(probabilities)
                
                predictions[symbol] = {
                    "prediction": prediction,
                    "probability": probability,
                    "timestamp": datetime.utcnow().isoformat(),
                    "features_used": features_df.columns.tolist()
                }
            
            return predictions
            
        except Exception as e:
            self.logger.error(f"Error generating predictions: {e}")
            raise
    
    async def _generate_explanations(self, model, features: Dict[str, Any], asset_symbols: List[str]) -> Dict[str, Any]:
        """Generate model explanations."""
        try:
            explanations = {}
            
            # Create explainer
            explainer = self.explainability_manager.create_explainer(
                model_name="prediction_model",
                model=model,
                feature_names=list(features.values())[0].columns.tolist() if features else [],
                X_background=list(features.values())[0].values if features else None
            )
            
            for symbol in asset_symbols:
                if symbol not in features:
                    continue
                
                features_df = features[symbol]
                
                if features_df.empty:
                    continue
                
                # Generate explanation
                explanation = self.explainability_manager.explain_prediction(
                    model_name="prediction_model",
                    X=features_df.values,
                    explanation_type="local",
                    instance_idx=-1  # Latest prediction
                )
                
                explanations[symbol] = explanation
            
            return explanations
            
        except Exception as e:
            self.logger.error(f"Error generating explanations: {e}")
            return {}
    
    async def batch_predict(self, asset_symbols: List[str], model_name: str = "trading_model") -> Dict[str, Any]:
        """Batch prediction for multiple assets."""
        try:
            request_data = PredictionRequestModel(
                asset_symbols=asset_symbols,
                prediction_type="batch",
                model_name=model_name
            )
            
            request_id = await self.create_prediction_request(request_data)
            
            # Wait for completion (with timeout)
            timeout = 300  # 5 minutes
            start_time = datetime.utcnow()
            
            while (datetime.utcnow() - start_time).total_seconds() < timeout:
                status = await self.get_prediction_status(request_id)
                
                if status and status["status"] == "completed":
                    return await self.get_prediction_result(request_id)
                elif status and status["status"] == "failed":
                    raise Exception(f"Prediction failed: {status.get('error_message')}")
                
                await asyncio.sleep(1)
            
            raise TimeoutError(f"Prediction request {request_id} timed out")
            
        except Exception as e:
            self.logger.error(f"Error in batch prediction: {e}")
            raise
    
    async def real_time_predict(self, asset_symbol: str, model_name: str = "trading_model") -> Dict[str, Any]:
        """Real-time prediction for a single asset."""
        try:
            request_data = PredictionRequestModel(
                asset_symbols=[asset_symbol],
                prediction_type="real_time",
                model_name=model_name,
                priority="high"
            )
            
            request_id = await self.create_prediction_request(request_data)
            
            # Wait for completion (shorter timeout for real-time)
            timeout = 30  # 30 seconds
            start_time = datetime.utcnow()
            
            while (datetime.utcnow() - start_time).total_seconds() < timeout:
                status = await self.get_prediction_status(request_id)
                
                if status and status["status"] == "completed":
                    return await self.get_prediction_result(request_id)
                elif status and status["status"] == "failed":
                    raise Exception(f"Prediction failed: {status.get('error_message')}")
                
                await asyncio.sleep(0.5)
            
            raise TimeoutError(f"Real-time prediction request {request_id} timed out")
            
        except Exception as e:
            self.logger.error(f"Error in real-time prediction: {e}")
            raise
    
    def get_service_stats(self) -> Dict[str, Any]:
        """Get service statistics."""
        try:
            total_requests = len(self.requests)
            completed_requests = sum(1 for req in self.requests.values() if req.status == PredictionStatus.COMPLETED)
            failed_requests = sum(1 for req in self.requests.values() if req.status == PredictionStatus.FAILED)
            pending_requests = sum(1 for req in self.requests.values() if req.status == PredictionStatus.PENDING)
            
            return {
                "total_requests": total_requests,
                "completed_requests": completed_requests,
                "failed_requests": failed_requests,
                "pending_requests": pending_requests,
                "success_rate": completed_requests / max(total_requests, 1),
                "queue_size": self.request_queue.qsize(),
                "processing": self.processing,
                "cached_models": len(self.model_cache),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting service stats: {e}")
            return {}


# FastAPI application
app = FastAPI(
    title="Sentinel Trading Prediction Service",
    description="Microservice for trading predictions",
    version="1.0.0"
)

# Global prediction service instance
prediction_service = PredictionService()


@app.on_event("startup")
async def startup_event():
    """Initialize prediction service."""
    # Start background processing
    asyncio.create_task(prediction_service.process_predictions())


@app.post("/predictions/request", response_model=Dict[str, str])
async def create_prediction_request(request: PredictionRequestModel):
    """Create a new prediction request."""
    try:
        request_id = await prediction_service.create_prediction_request(request)
        return {"request_id": request_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/predictions/{request_id}/status")
async def get_prediction_status(request_id: str):
    """Get prediction request status."""
    try:
        status = await prediction_service.get_prediction_status(request_id)
        if status is None:
            raise HTTPException(status_code=404, detail="Request not found")
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/predictions/{request_id}/result")
async def get_prediction_result(request_id: str):
    """Get prediction result."""
    try:
        result = await prediction_service.get_prediction_result(request_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Result not found or not completed")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predictions/batch")
async def batch_predict(request: Dict[str, Any]):
    """Batch prediction for multiple assets."""
    try:
        asset_symbols = request.get("asset_symbols", [])
        model_name = request.get("model_name", "trading_model")
        
        result = await prediction_service.batch_predict(asset_symbols, model_name)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predictions/realtime")
async def real_time_predict(request: Dict[str, Any]):
    """Real-time prediction for a single asset."""
    try:
        asset_symbol = request.get("asset_symbol")
        model_name = request.get("model_name", "trading_model")
        
        if not asset_symbol:
            raise HTTPException(status_code=400, detail="asset_symbol is required")
        
        result = await prediction_service.real_time_predict(asset_symbol, model_name)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        stats = prediction_service.get_service_stats()
        
        health = {
            "status": "healthy",
            "service": "prediction_service",
            "timestamp": datetime.utcnow().isoformat(),
            "stats": stats
        }
        
        # Determine health status based on queue size and error rate
        if stats["queue_size"] > 100:
            health["status"] = "degraded"
        
        if stats["success_rate"] < 0.8:
            health["status"] = "unhealthy"
        
        return health
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
async def get_service_stats():
    """Get service statistics."""
    try:
        return prediction_service.get_service_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Utility functions
def run_prediction_service(host: str = "0.0.0.0", port: int = 8001):
    """Run the prediction service."""
    uvicorn.run(app, host=host, port=port)


# Main execution
if __name__ == "__main__":
    run_prediction_service()
