"""
Model explainability using SHAP values for Sentinel Trading predictions.
"""

import logging
import numpy as np
import pandas as pd
import shap
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import base64
import io

from app.infrastructure.logging_config import LoggerMixin
from app.infrastructure.cache import get_cache
from app.infrastructure.metrics import get_metrics
from app.infrastructure.feature_engineering import get_feature_engineer

logger = logging.getLogger(__name__)


class ExplanationType(Enum):
    """Types of model explanations."""
    GLOBAL = "global"
    LOCAL = "local"
    FEATURE_IMPORTANCE = "feature_importance"
    INTERACTION = "interaction"
    COUNTERFACTUAL = "counterfactual"


class VisualizationFormat(Enum):
    """Visualization formats."""
    PLOTLY = "plotly"
    MATPLOTLIB = "matplotlib"
    DATAFRAME = "dataframe"
    JSON = "json"


@dataclass
class ExplanationResult:
    """Result of model explanation."""
    explanation_type: ExplanationType
    model_name: str
    timestamp: datetime
    shap_values: np.ndarray
    feature_values: np.ndarray
    feature_names: List[str]
    base_value: float
    predictions: np.ndarray
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = asdict(self)
        result['explanation_type'] = self.explanation_type.value
        result['timestamp'] = self.timestamp.isoformat()
        # Convert numpy arrays to lists for JSON serialization
        result['shap_values'] = self.shap_values.tolist()
        result['feature_values'] = self.feature_values.tolist()
        result['predictions'] = self.predictions.tolist()
        return result


class SHAPExplainer(LoggerMixin):
    """SHAP-based model explainer for trading predictions."""
    
    def __init__(self, model=None, feature_names: List[str] = None):
        self.model = model
        self.feature_names = feature_names or []
        self.explainer = None
        self.explanation_cache = {}
        self.metrics = get_metrics()
        self.cache = get_cache()
    
    def setup_explainer(self, X_background: np.ndarray, model_type: str = "sklearn"):
        """Setup SHAP explainer based on model type."""
        try:
            if model_type == "sklearn":
                # Use TreeExplainer for tree-based models
                if hasattr(self.model, 'feature_importances_'):
                    self.explainer = shap.TreeExplainer(self.model, X_background)
                else:
                    # Use KernelExplainer for other models
                    self.explainer = shap.KernelExplainer(self.model.predict, X_background)
            elif model_type == "linear":
                self.explainer = shap.LinearExplainer(self.model, X_background)
            elif model_type == "deep":
                self.explainer = shap.DeepExplainer(self.model, X_background)
            else:
                # Default to KernelExplainer
                self.explainer = shap.KernelExplainer(self.model.predict, X_background)
            
            self.logger.info(f"SHAP explainer setup complete for model type: {model_type}")
            
        except Exception as e:
            self.logger.error(f"Error setting up SHAP explainer: {e}")
            raise
    
    def explain_global(self, X: np.ndarray, predictions: np.ndarray = None) -> ExplanationResult:
        """Generate global model explanations."""
        try:
            if self.explainer is None:
                raise ValueError("Explainer not setup. Call setup_explainer() first.")
            
            # Calculate SHAP values
            shap_values = self.explainer.shap_values(X)
            
            # Handle multi-class case
            if isinstance(shap_values, list):
                # For classification, use the first class or average
                if len(shap_values) > 1:
                    shap_values = np.mean(shap_values, axis=0)
                else:
                    shap_values = shap_values[0]
            
            # Get base value
            if hasattr(self.explainer, 'expected_value'):
                base_value = self.explainer.expected_value
                if isinstance(base_value, list):
                    base_value = base_value[0]
            else:
                base_value = np.mean(predictions) if predictions is not None else 0.0
            
            # Get predictions if not provided
            if predictions is None:
                predictions = self.model.predict(X)
            
            result = ExplanationResult(
                explanation_type=ExplanationType.GLOBAL,
                model_name="trading_model",
                timestamp=datetime.utcnow(),
                shap_values=shap_values,
                feature_values=X,
                feature_names=self.feature_names,
                base_value=base_value,
                predictions=predictions,
                metadata={
                    "sample_count": X.shape[0],
                    "feature_count": X.shape[1],
                    "mean_shap_value": np.mean(np.abs(shap_values)),
                    "max_shap_value": np.max(np.abs(shap_values))
                }
            )
            
            # Cache result
            cache_key = f"global_explanation:{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            self.cache.set(cache_key, result.to_dict(), ttl=3600)  # 1 hour TTL
            
            self.logger.info(f"Global explanation generated for {X.shape[0]} samples")
            
            # Record metrics
            self.metrics.record_trading_signal(
                signal_type="global_explanation_generated",
                asset_symbol=f"samples_{X.shape[0]}"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error generating global explanation: {e}")
            raise
    
    def explain_local(self, X: np.ndarray, instance_idx: int = 0, predictions: np.ndarray = None) -> ExplanationResult:
        """Generate local explanation for a specific instance."""
        try:
            if self.explainer is None:
                raise ValueError("Explainer not setup. Call setup_explainer() first.")
            
            if instance_idx >= X.shape[0]:
                raise ValueError(f"Instance index {instance_idx} out of range")
            
            # Get single instance
            X_instance = X[instance_idx:instance_idx+1]
            
            # Calculate SHAP values for single instance
            shap_values = self.explainer.shap_values(X_instance)
            
            # Handle multi-class case
            if isinstance(shap_values, list):
                if len(shap_values) > 1:
                    shap_values = shap_values[0]  # Use first class
                else:
                    shap_values = shap_values[0]
            
            # Get base value
            if hasattr(self.explainer, 'expected_value'):
                base_value = self.explainer.expected_value
                if isinstance(base_value, list):
                    base_value = base_value[0]
            else:
                base_value = 0.0
            
            # Get prediction for instance
            if predictions is not None:
                prediction = predictions[instance_idx]
            else:
                prediction = self.model.predict(X_instance)[0]
            
            result = ExplanationResult(
                explanation_type=ExplanationType.LOCAL,
                model_name="trading_model",
                timestamp=datetime.utcnow(),
                shap_values=shap_values[0],  # Single instance
                feature_values=X_instance[0],
                feature_names=self.feature_names,
                base_value=base_value,
                predictions=np.array([prediction]),
                metadata={
                    "instance_idx": instance_idx,
                    "prediction": prediction,
                    "top_features": self._get_top_features(shap_values[0], self.feature_names)
                }
            )
            
            # Cache result
            cache_key = f"local_explanation:{instance_idx}:{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            self.cache.set(cache_key, result.to_dict(), ttl=3600)
            
            self.logger.info(f"Local explanation generated for instance {instance_idx}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error generating local explanation: {e}")
            raise
    
    def explain_feature_importance(self, X: np.ndarray) -> Dict[str, float]:
        """Calculate feature importance using SHAP values."""
        try:
            if self.explainer is None:
                raise ValueError("Explainer not setup. Call setup_explainer() first.")
            
            # Calculate SHAP values
            shap_values = self.explainer.shap_values(X)
            
            # Handle multi-class case
            if isinstance(shap_values, list):
                shap_values = np.mean(np.abs(shap_values), axis=0)
            
            # Calculate mean absolute SHAP values for each feature
            mean_shap_values = np.mean(np.abs(shap_values), axis=0)
            
            # Create feature importance dictionary
            feature_importance = {}
            for i, feature_name in enumerate(self.feature_names):
                feature_importance[feature_name] = mean_shap_values[i]
            
            # Sort by importance
            sorted_importance = dict(
                sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)
            )
            
            return sorted_importance
            
        except Exception as e:
            self.logger.error(f"Error calculating feature importance: {e}")
            return {}
    
    def _get_top_features(self, shap_values: np.ndarray, feature_names: List[str], top_k: int = 10) -> List[Dict[str, Any]]:
        """Get top contributing features for an explanation."""
        try:
            # Get absolute SHAP values
            abs_shap = np.abs(shap_values)
            
            # Get top indices
            top_indices = np.argsort(abs_shap)[-top_k:][::-1]
            
            top_features = []
            for idx in top_indices:
                top_features.append({
                    "feature": feature_names[idx],
                    "shap_value": shap_values[idx],
                    "abs_shap_value": abs_shap[idx],
                    "direction": "positive" if shap_values[idx] > 0 else "negative"
                })
            
            return top_features
            
        except Exception as e:
            self.logger.error(f"Error getting top features: {e}")
            return []
    
    def create_force_plot(self, explanation: ExplanationResult, instance_idx: int = 0) -> str:
        """Create SHAP force plot (returns HTML string)."""
        try:
            if explanation.explanation_type != ExplanationType.LOCAL:
                raise ValueError("Force plot only available for local explanations")
            
            # Create force plot
            shap.force_plot(
                explanation.base_value,
                explanation.shap_values,
                explanation.feature_values,
                feature_names=explanation.feature_names,
                matplotlib=True,
                show=False
            )
            
            # Save plot to base64 string
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', bbox_inches='tight')
            buffer.seek(0)
            plot_data = base64.b64encode(buffer.getvalue()).decode()
            plt.close()
            
            return f"data:image/png;base64,{plot_data}"
            
        except Exception as e:
            self.logger.error(f"Error creating force plot: {e}")
            return ""
    
    def create_summary_plot(self, explanation: ExplanationResult) -> str:
        """Create SHAP summary plot (returns HTML string)."""
        try:
            # Create summary plot
            shap.summary_plot(
                explanation.shap_values,
                explanation.feature_values,
                feature_names=explanation.feature_names,
                plot_type="bar",
                show=False,
                max_display=20
            )
            
            # Save plot to base64 string
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', bbox_inches='tight')
            buffer.seek(0)
            plot_data = base64.b64encode(buffer.getvalue()).decode()
            plt.close()
            
            return f"data:image/png;base64,{plot_data}"
            
        except Exception as e:
            self.logger.error(f"Error creating summary plot: {e}")
            return ""
    
    def create_waterfall_plot(self, explanation: ExplanationResult, instance_idx: int = 0) -> str:
        """Create SHAP waterfall plot (returns HTML string)."""
        try:
            if explanation.explanation_type != ExplanationType.LOCAL:
                raise ValueError("Waterfall plot only available for local explanations")
            
            # Create waterfall plot
            shap.waterfall_plot(
                explanation.base_value,
                explanation.shap_values,
                explanation.feature_values,
                feature_names=explanation.feature_names,
                max_display=20,
                show=False
            )
            
            # Save plot to base64 string
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', bbox_inches='tight')
            buffer.seek(0)
            plot_data = base64.b64encode(buffer.getvalue()).decode()
            plt.close()
            
            return f"data:image/png;base64,{plot_data}"
            
        except Exception as e:
            self.logger.error(f"Error creating waterfall plot: {e}")
            return ""
    
    def create_interaction_plot(self, X: np.ndarray, feature_idx: int) -> str:
        """Create SHAP interaction plot (returns HTML string)."""
        try:
            if self.explainer is None:
                raise ValueError("Explainer not setup. Call setup_explainer() first.")
            
            # Calculate SHAP interaction values
            shap_interaction_values = self.explainer.shap_interaction_values(X)
            
            # Create interaction plot
            shap.dependence_plot(
                feature_idx,
                shap_interaction_values,
                X,
                feature_names=self.feature_names,
                show=False
            )
            
            # Save plot to base64 string
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', bbox_inches='tight')
            buffer.seek(0)
            plot_data = base64.b64encode(buffer.getvalue()).decode()
            plt.close()
            
            return f"data:image/png;base64,{plot_data}"
            
        except Exception as e:
            self.logger.error(f"Error creating interaction plot: {e}")
            return ""


class ExplainabilityManager(LoggerMixin):
    """Manager for model explainability and visualizations."""
    
    def __init__(self):
        self.explainers = {}
        self.metrics = get_metrics()
        self.cache = get_cache()
    
    def create_explainer(self, model_name: str, model, feature_names: List[str], 
                        X_background: np.ndarray, model_type: str = "sklearn") -> SHAPExplainer:
        """Create and store a SHAP explainer for a model."""
        try:
            explainer = SHAPExplainer(model, feature_names)
            explainer.setup_explainer(X_background, model_type)
            
            self.explainers[model_name] = explainer
            
            self.logger.info(f"Created SHAP explainer for model: {model_name}")
            
            return explainer
            
        except Exception as e:
            self.logger.error(f"Error creating explainer for {model_name}: {e}")
            raise
    
    def explain_prediction(self, model_name: str, X: np.ndarray, explanation_type: str = "local",
                          instance_idx: int = None) -> Dict[str, Any]:
        """Generate explanation for a prediction."""
        try:
            if model_name not in self.explainers:
                raise ValueError(f"No explainer found for model: {model_name}")
            
            explainer = self.explainers[model_name]
            
            if explanation_type == "global":
                explanation = explainer.explain_global(X)
            elif explanation_type == "local":
                if instance_idx is None:
                    instance_idx = 0
                explanation = explainer.explain_local(X, instance_idx)
            else:
                raise ValueError(f"Unsupported explanation type: {explanation_type}")
            
            # Create visualizations
            visualizations = {}
            
            if explanation_type == "local":
                visualizations["force_plot"] = explainer.create_force_plot(explanation, instance_idx or 0)
                visualizations["waterfall_plot"] = explainer.create_waterfall_plot(explanation, instance_idx or 0)
            else:
                visualizations["summary_plot"] = explainer.create_summary_plot(explanation)
            
            return {
                "explanation": explanation.to_dict(),
                "visualizations": visualizations,
                "model_name": model_name,
                "explanation_type": explanation_type,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error explaining prediction: {e}")
            raise
    
    def get_feature_importance(self, model_name: str, X: np.ndarray) -> Dict[str, Any]:
        """Get feature importance for a model."""
        try:
            if model_name not in self.explainers:
                raise ValueError(f"No explainer found for model: {model_name}")
            
            explainer = self.explainers[model_name]
            importance = explainer.explain_feature_importance(X)
            
            return {
                "feature_importance": importance,
                "model_name": model_name,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting feature importance: {e}")
            return {}
    
    def compare_models(self, model_names: List[str], X: np.ndarray) -> Dict[str, Any]:
        """Compare feature importance across multiple models."""
        try:
            comparison = {}
            
            for model_name in model_names:
                if model_name in self.explainers:
                    importance = self.get_feature_importance(model_name, X)
                    comparison[model_name] = importance.get("feature_importance", {})
            
            # Calculate correlation between models
            correlation_matrix = self._calculate_importance_correlation(comparison)
            
            return {
                "model_importances": comparison,
                "correlation_matrix": correlation_matrix,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error comparing models: {e}")
            return {}
    
    def _calculate_importance_correlation(self, importance_dict: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
        """Calculate correlation between feature importance of different models."""
        try:
            if len(importance_dict) < 2:
                return {}
            
            # Create DataFrame from importance dictionaries
            df = pd.DataFrame(importance_dict).fillna(0)
            
            # Calculate correlation matrix
            correlation_matrix = df.corr()
            
            return correlation_matrix.to_dict()
            
        except Exception as e:
            self.logger.error(f"Error calculating importance correlation: {e}")
            return {}
    
    def get_explanation_summary(self, model_name: str) -> Dict[str, Any]:
        """Get summary of explanations for a model."""
        try:
            if model_name not in self.explainers:
                raise ValueError(f"No explainer found for model: {model_name}")
            
            # Get cached explanations
            cache_pattern = f"*explanation*:{model_name}*"
            cache_keys = self.cache.keys(cache_pattern)
            
            summary = {
                "model_name": model_name,
                "total_explanations": len(cache_keys),
                "feature_count": len(self.explainers[model_name].feature_names),
                "last_explanation": None,
                "explanation_types": {}
            }
            
            # Analyze cached explanations
            for key in cache_keys:
                explanation_data = self.cache.get(key)
                if explanation_data:
                    exp_type = explanation_data.get("explanation_type", "unknown")
                    summary["explanation_types"][exp_type] = summary["explanation_types"].get(exp_type, 0) + 1
                    
                    if summary["last_explanation"] is None:
                        summary["last_explanation"] = explanation_data.get("timestamp")
                    elif explanation_data.get("timestamp") > summary["last_explanation"]:
                        summary["last_explanation"] = explanation_data.get("timestamp")
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error getting explanation summary: {e}")
            return {}


# Global instances
explainability_manager = ExplainabilityManager()


def get_explainability_manager() -> ExplainabilityManager:
    """Get explainability manager instance."""
    return explainability_manager


# Utility functions
def explain_trading_model(model, X_train: np.ndarray, feature_names: List[str], 
                          X_test: np.ndarray = None, model_name: str = "trading_model") -> Dict[str, Any]:
    """Explain a trading model using SHAP."""
    try:
        # Create explainer
        explainer = explainability_manager.create_explainer(
            model_name=model_name,
            model=model,
            feature_names=feature_names,
            X_background=X_train,
            model_type="sklearn"
        )
        
        # Generate explanations
        explanations = {}
        
        # Global explanation
        global_exp = explainability_manager.explain_prediction(model_name, X_train, "global")
        explanations["global"] = global_exp
        
        # Local explanations (first 5 instances)
        if X_test is not None:
            local_explanations = []
            for i in range(min(5, X_test.shape[0])):
                local_exp = explainability_manager.explain_prediction(model_name, X_test, "local", i)
                local_explanations.append(local_exp)
            explanations["local"] = local_explanations
        
        # Feature importance
        importance = explainability_manager.get_feature_importance(model_name, X_train)
        explanations["feature_importance"] = importance
        
        return explanations
        
    except Exception as e:
        logger.error(f"Error explaining trading model: {e}")
        return {}


def create_explanation_dashboard(explanations: Dict[str, Any]) -> Dict[str, Any]:
    """Create a dashboard with multiple explanations."""
    try:
        dashboard = {
            "title": "Model Explainability Dashboard",
            "timestamp": datetime.utcnow().isoformat(),
            "sections": {}
        }
        
        # Global explanation section
        if "global" in explanations:
            dashboard["sections"]["global_explanation"] = {
                "type": "summary_plot",
                "data": explanations["global"]["visualizations"].get("summary_plot"),
                "metadata": explanations["global"]["explanation"]["metadata"]
            }
        
        # Local explanations section
        if "local" in explanations:
            dashboard["sections"]["local_explanations"] = []
            for i, local_exp in enumerate(explanations["local"]):
                dashboard["sections"]["local_explanations"].append({
                    "instance_idx": i,
                    "type": "force_plot",
                    "data": local_exp["visualizations"].get("force_plot"),
                    "prediction": local_exp["explanation"]["predictions"][0],
                    "top_features": local_exp["explanation"]["metadata"]["top_features"]
                })
        
        # Feature importance section
        if "feature_importance" in explanations:
            dashboard["sections"]["feature_importance"] = {
                "type": "bar_chart",
                "data": explanations["feature_importance"]["feature_importance"],
                "model_name": explanations["feature_importance"]["model_name"]
            }
        
        return dashboard
        
    except Exception as e:
        logger.error(f"Error creating explanation dashboard: {e}")
        return {}
