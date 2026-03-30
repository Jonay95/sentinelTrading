"""
MLflow integration for model versioning and experiment tracking.
"""

import logging
import os
import json
import pickle
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import mlflow
import mlflow.sklearn
import mlflow.pytorch
import mlflow.tensorflow
from mlflow.tracking import MlflowClient
from mlflow.entities import ViewType
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, mean_squared_error, mean_absolute_error

from app.infrastructure.logging_config import LoggerMixin
from app.infrastructure.cache import get_cache
from app.infrastructure.metrics import get_metrics

logger = logging.getLogger(__name__)


class ModelType(Enum):
    """Model types supported by MLflow manager."""
    SKLEARN = "sklearn"
    PYTORCH = "pytorch"
    TENSORFLOW = "tensorflow"
    CUSTOM = "custom"


class ModelStage(Enum):
    """Model stages in MLflow."""
    DEVELOPMENT = "Development"
    STAGING = "Staging"
    PRODUCTION = "Production"
    ARCHIVED = "Archived"


@dataclass
class ModelMetadata:
    """Model metadata for MLflow tracking."""
    name: str
    version: str
    model_type: ModelType
    stage: ModelStage
    created_at: datetime
    description: str
    hyperparameters: Dict[str, Any]
    metrics: Dict[str, float]
    artifacts: List[str]
    tags: Dict[str, str]
    run_id: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = asdict(self)
        result['model_type'] = self.model_type.value
        result['stage'] = self.stage.value
        result['created_at'] = self.created_at.isoformat()
        return result


@dataclass
class ExperimentConfig:
    """Experiment configuration."""
    name: str
    description: str
    tags: Dict[str, str]
    artifact_location: Optional[str] = None


class MLflowManager(LoggerMixin):
    """MLflow manager for model versioning and experiment tracking."""
    
    def __init__(self, tracking_uri: str = None, experiment_name: str = "sentinel_trading"):
        self.tracking_uri = tracking_uri or os.environ.get('MLFLOW_TRACKING_URI', 'http://localhost:5000')
        self.experiment_name = experiment_name
        self.client = None
        self.active_experiment = None
        self.metrics = get_metrics()
        self.cache = get_cache()
        
        self._initialize_mlflow()
    
    def _initialize_mlflow(self):
        """Initialize MLflow tracking."""
        try:
            # Set tracking URI
            mlflow.set_tracking_uri(self.tracking_uri)
            
            # Initialize client
            self.client = MlflowClient(tracking_uri=self.tracking_uri)
            
            # Get or create experiment
            try:
                self.active_experiment = mlflow.get_experiment_by_name(self.experiment_name)
                if not self.active_experiment:
                    self.active_experiment = mlflow.create_experiment(
                        name=self.experiment_name,
                        tags={"project": "sentinel_trading", "environment": "production"}
                    )
                else:
                    # Set experiment as active
                    mlflow.set_experiment(self.experiment_name)
            except Exception as e:
                self.logger.error(f"Error setting up experiment: {e}")
                raise
            
            self.logger.info(f"MLflow initialized with tracking URI: {self.tracking_uri}")
            self.logger.info(f"Active experiment: {self.experiment_name}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize MLflow: {e}")
            raise
    
    def start_run(self, run_name: str = None, experiment_id: str = None, tags: Dict[str, str] = None) -> str:
        """Start a new MLflow run."""
        try:
            run = mlflow.start_run(
                run_name=run_name,
                experiment_id=experiment_id or self.active_experiment.experiment_id,
                tags=tags
            )
            
            self.logger.info(f"Started MLflow run: {run.info.run_id}")
            return run.info.run_id
            
        except Exception as e:
            self.logger.error(f"Error starting MLflow run: {e}")
            raise
    
    def end_run(self):
        """End the current MLflow run."""
        try:
            mlflow.end_run()
            self.logger.info("MLflow run ended")
        except Exception as e:
            self.logger.error(f"Error ending MLflow run: {e}")
    
    def log_model(self, model, model_name: str, model_type: ModelType, 
                  hyperparameters: Dict[str, Any] = None, metrics: Dict[str, float] = None,
                  artifacts: Dict[str, str] = None, tags: Dict[str, str] = None,
                  description: str = None) -> str:
        """Log a model to MLflow."""
        try:
            # Start run if not already active
            if not mlflow.active_run():
                self.start_run(f"model_training_{model_name}")
            
            run_id = mlflow.active_run().info.run_id
            
            # Log hyperparameters
            if hyperparameters:
                for key, value in hyperparameters.items():
                    mlflow.log_param(key, value)
            
            # Log metrics
            if metrics:
                for key, value in metrics.items():
                    mlflow.log_metric(key, value)
            
            # Log artifacts
            if artifacts:
                for name, path in artifacts.items():
                    mlflow.log_artifact(path, artifact_path=name)
            
            # Log model based on type
            if model_type == ModelType.SKLEARN:
                mlflow.sklearn.log_model(model, model_name)
            elif model_type == ModelType.PYTORCH:
                mlflow.pytorch.log_model(model, model_name)
            elif model_type == ModelType.TENSORFLOW:
                mlflow.tensorflow.log_model(model, model_name)
            elif model_type == ModelType.CUSTOM:
                # Save custom model
                model_path = f"models/{model_name}"
                os.makedirs(model_path, exist_ok=True)
                
                with open(f"{model_path}/model.pkl", 'wb') as f:
                    pickle.dump(model, f)
                
                mlflow.log_artifact(f"{model_path}/model.pkl", artifact_path=model_name)
            
            # Add tags and description
            if tags:
                mlflow.set_tags(tags)
            
            if description:
                mlflow.set_tag("description", description)
            
            # Log basic model info
            mlflow.set_tag("model_type", model_type.value)
            mlflow.set_tag("logged_at", datetime.utcnow().isoformat())
            
            self.logger.info(f"Model {model_name} logged to MLflow with run_id: {run_id}")
            
            # Record metrics
            self.metrics.record_trading_signal(
                signal_type="model_logged",
                asset_symbol=model_name
            )
            
            return run_id
            
        except Exception as e:
            self.logger.error(f"Error logging model {model_name}: {e}")
            raise
    
    def register_model(self, model_name: str, run_id: str, description: str = None,
                      tags: Dict[str, str] = None) -> ModelMetadata:
        """Register a model in MLflow Model Registry."""
        try:
            # Get model URI
            model_uri = f"runs:/{run_id}/{model_name}"
            
            # Register model
            model_version = mlflow.register_model(
                model_uri,
                model_name,
                tags=tags
            )
            
            # Add description
            if description:
                client = MlflowClient()
                client.update_model_version(
                    name=model_name,
                    version=model_version.version,
                    description=description
                )
            
            # Get model details
            model_details = client.get_model_version(model_name, model_version.version)
            
            # Create metadata
            metadata = ModelMetadata(
                name=model_name,
                version=model_version.version,
                model_type=ModelType(model_details.tags.get("model_type", "sklearn")),
                stage=ModelStage(model_details.current_stage),
                created_at=datetime.fromtimestamp(model_details.creation_time / 1000),
                description=description or "",
                hyperparameters={},  # Would need to fetch from run
                metrics={},  # Would need to fetch from run
                artifacts=[],  # Would need to fetch from run
                tags=model_details.tags or {},
                run_id=run_id
            )
            
            self.logger.info(f"Model {model_name} version {model_version.version} registered in stage {model_version.current_stage}")
            
            # Cache metadata
            cache_key = f"model_metadata:{model_name}:{model_version.version}"
            self.cache.set(cache_key, metadata.to_dict(), ttl=3600)  # 1 hour TTL
            
            return metadata
            
        except Exception as e:
            self.logger.error(f"Error registering model {model_name}: {e}")
            raise
    
    def transition_model_stage(self, model_name: str, version: str, stage: ModelStage,
                              archive_existing_versions: bool = False) -> bool:
        """Transition model to a new stage."""
        try:
            client = MlflowClient()
            
            # Transition stage
            client.transition_model_version_stage(
                name=model_name,
                version=version,
                stage=stage.value,
                archive_existing_versions=archive_existing_versions
            )
            
            self.logger.info(f"Model {model_name} version {version} transitioned to {stage.value}")
            
            # Update cache
            cache_key = f"model_metadata:{model_name}:{version}"
            cached_metadata = self.cache.get(cache_key)
            if cached_metadata:
                cached_metadata['stage'] = stage.value
                self.cache.set(cache_key, cached_metadata, ttl=3600)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error transitioning model {model_name} version {version} to {stage.value}: {e}")
            return False
    
    def get_model_metadata(self, model_name: str, version: str = None, stage: ModelStage = None) -> Optional[ModelMetadata]:
        """Get model metadata."""
        try:
            cache_key = f"model_metadata:{model_name}:{version or 'latest'}"
            cached_metadata = self.cache.get(cache_key)
            
            if cached_metadata:
                return ModelMetadata(**cached_metadata)
            
            client = MlflowClient()
            
            if version:
                model_version = client.get_model_version(model_name, version)
            elif stage:
                model_version = client.get_latest_versions(model_name, stages=[stage.value])[0]
            else:
                model_version = client.get_latest_versions(model_name, stages=["Production", "Staging", "Development"])[0]
            
            # Get run details
            run = client.get_run(model_version.run_id)
            
            metadata = ModelMetadata(
                name=model_name,
                version=model_version.version,
                model_type=ModelType(model_version.tags.get("model_type", "sklearn")),
                stage=ModelStage(model_version.current_stage),
                created_at=datetime.fromtimestamp(model_version.creation_time / 1000),
                description=model_version.description or "",
                hyperparameters=run.data.params or {},
                metrics=run.data.metrics or {},
                artifacts=[],  # Would need to fetch artifacts
                tags=model_version.tags or {},
                run_id=model_version.run_id
            )
            
            # Cache metadata
            self.cache.set(cache_key, metadata.to_dict(), ttl=3600)
            
            return metadata
            
        except Exception as e:
            self.logger.error(f"Error getting model metadata for {model_name}: {e}")
            return None
    
    def load_model(self, model_name: str, version: str = None, stage: ModelStage = None):
        """Load a model from MLflow."""
        try:
            metadata = self.get_model_metadata(model_name, version, stage)
            
            if not metadata:
                raise ValueError(f"Model {model_name} not found")
            
            # Construct model URI
            if version:
                model_uri = f"models:/{model_name}/{version}"
            else:
                model_uri = f"models:/{model_name}/{stage.value if stage else 'latest'}"
            
            # Load model based on type
            if metadata.model_type == ModelType.SKLEARN:
                return mlflow.sklearn.load_model(model_uri)
            elif metadata.model_type == ModelType.PYTORCH:
                return mlflow.pytorch.load_model(model_uri)
            elif metadata.model_type == ModelType.TENSORFLOW:
                return mlflow.tensorflow.load_model(model_uri)
            elif metadata.model_type == ModelType.CUSTOM:
                # Load custom model
                model_path = mlflow.artifacts.download_artifacts(model_uri)
                with open(f"{model_path}/model.pkl", 'rb') as f:
                    return pickle.load(f)
            
        except Exception as e:
            self.logger.error(f"Error loading model {model_name}: {e}")
            raise
    
    def list_models(self, stage: ModelStage = None) -> List[ModelMetadata]:
        """List all models."""
        try:
            client = MlflowClient()
            
            if stage:
                models = client.search_model_versions(f"name like '%' and stage='{stage.value}'")
            else:
                models = client.search_model_versions("name like '%'")
            
            model_metadata_list = []
            
            for model in models:
                # Get run details
                run = client.get_run(model.run_id)
                
                metadata = ModelMetadata(
                    name=model.name,
                    version=model.version,
                    model_type=ModelType(model.tags.get("model_type", "sklearn")),
                    stage=ModelStage(model.current_stage),
                    created_at=datetime.fromtimestamp(model.creation_time / 1000),
                    description=model.description or "",
                    hyperparameters=run.data.params or {},
                    metrics=run.data.metrics or {},
                    artifacts=[],
                    tags=model.tags or {},
                    run_id=model.run_id
                )
                
                model_metadata_list.append(metadata)
            
            return model_metadata_list
            
        except Exception as e:
            self.logger.error(f"Error listing models: {e}")
            return []
    
    def compare_models(self, model_names: List[str], metric: str = "accuracy") -> Dict[str, Any]:
        """Compare models based on a specific metric."""
        try:
            comparison = {}
            
            for model_name in model_names:
                metadata = self.get_model_metadata(model_name)
                
                if metadata and metric in metadata.metrics:
                    comparison[model_name] = {
                        "version": metadata.version,
                        "stage": metadata.stage.value,
                        "metric_value": metadata.metrics[metric],
                        "created_at": metadata.created_at.isoformat()
                    }
            
            # Sort by metric value (descending)
            sorted_comparison = dict(
                sorted(comparison.items(), key=lambda x: x[1]["metric_value"], reverse=True)
            )
            
            return {
                "metric": metric,
                "comparison": sorted_comparison,
                "best_model": max(comparison.items(), key=lambda x: x[1]["metric_value"])[0] if comparison else None
            }
            
        except Exception as e:
            self.logger.error(f"Error comparing models: {e}")
            return {}
    
    def get_experiment_history(self, experiment_name: str = None, max_results: int = 100) -> List[Dict[str, Any]]:
        """Get experiment run history."""
        try:
            exp_name = experiment_name or self.experiment_name
            
            runs = mlflow.search_runs(
                experiment_ids=[self.active_experiment.experiment_id],
                max_results=max_results,
                order_by=["start_time DESC"]
            )
            
            history = []
            
            for run in runs:
                history.append({
                    "run_id": run.info.run_id,
                    "status": run.info.status,
                    "start_time": datetime.fromtimestamp(run.info.start_time / 1000).isoformat(),
                    "end_time": datetime.fromtimestamp(run.info.end_time / 1000).isoformat() if run.info.end_time else None,
                    "params": run.data.params or {},
                    "metrics": run.data.metrics or {},
                    "tags": run.data.tags or {}
                })
            
            return history
            
        except Exception as e:
            self.logger.error(f"Error getting experiment history: {e}")
            return []
    
    def delete_model(self, model_name: str, version: str = None) -> bool:
        """Delete a model version or entire model."""
        try:
            client = MlflowClient()
            
            if version:
                # Delete specific version
                client.delete_model_version(model_name, version)
                self.logger.info(f"Model {model_name} version {version} deleted")
            else:
                # Delete all versions
                versions = client.search_model_versions(f"name='{model_name}'")
                for model_version in versions:
                    client.delete_model_version(model_name, model_version.version)
                
                self.logger.info(f"All versions of model {model_name} deleted")
            
            # Clear cache
            cache_pattern = f"model_metadata:{model_name}:*"
            cache_keys = self.cache.keys(cache_pattern)
            for key in cache_keys:
                self.cache.delete(key)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting model {model_name}: {e}")
            return False


# Global MLflow manager instance
mlflow_manager = MLflowManager()


def get_mlflow_manager() -> MLflowManager:
    """Get MLflow manager instance."""
    return mlflow_manager


# Utility functions for common MLflow operations
def log_training_run(model_name: str, model, model_type: ModelType, 
                    hyperparameters: Dict[str, Any], metrics: Dict[str, float],
                    description: str = None) -> str:
    """Log a complete training run."""
    try:
        run_id = mlflow_manager.start_run(f"training_{model_name}")
        
        try:
            # Log model
            mlflow_manager.log_model(
                model=model,
                model_name=model_name,
                model_type=model_type,
                hyperparameters=hyperparameters,
                metrics=metrics,
                description=description
            )
            
            # Register model
            metadata = mlflow_manager.register_model(
                model_name=model_name,
                run_id=run_id,
                description=description
            )
            
            return metadata.version
            
        finally:
            mlflow_manager.end_run()
            
    except Exception as e:
        logger.error(f"Error in training run: {e}")
        raise


def promote_to_production(model_name: str, version: str = None) -> bool:
    """Promote a model to production stage."""
    try:
        if version is None:
            # Get latest staging version
            metadata = mlflow_manager.get_model_metadata(model_name, stage=ModelStage.STAGING)
            if metadata:
                version = metadata.version
            else:
                raise ValueError(f"No staging version found for model {model_name}")
        
        return mlflow_manager.transition_model_stage(
            model_name=model_name,
            version=version,
            stage=ModelStage.PRODUCTION,
            archive_existing_versions=True
        )
        
    except Exception as e:
        logger.error(f"Error promoting model {model_name} to production: {e}")
        return False


def get_production_model(model_name: str):
    """Get the current production model."""
    try:
        return mlflow_manager.load_model(model_name, stage=ModelStage.PRODUCTION)
    except Exception as e:
        logger.error(f"Error loading production model {model_name}: {e}")
        raise


# Decorators for automatic MLflow logging
def mlflow_tracking(model_name: str, model_type: ModelType = ModelType.SKLEARN):
    """Decorator for automatic MLflow tracking."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            run_id = mlflow_manager.start_run(f"auto_{model_name}")
            
            try:
                # Execute function
                result = func(*args, **kwargs)
                
                # If function returns (model, hyperparameters, metrics), log them
                if isinstance(result, tuple) and len(result) == 3:
                    model, hyperparameters, metrics = result
                    
                    mlflow_manager.log_model(
                        model=model,
                        model_name=model_name,
                        model_type=model_type,
                        hyperparameters=hyperparameters,
                        metrics=metrics
                    )
                
                return result
                
            finally:
                mlflow_manager.end_run()
        
        return wrapper
    return decorator
