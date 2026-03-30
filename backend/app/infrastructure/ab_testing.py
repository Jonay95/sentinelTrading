"""
A/B testing framework for model comparison in Sentinel Trading.
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum
from scipy import stats
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from app.infrastructure.logging_config import LoggerMixin
from app.infrastructure.cache import get_cache
from app.infrastructure.metrics import get_metrics
from app.infrastructure.mlflow_manager import get_mlflow_manager

logger = logging.getLogger(__name__)


class TestStatus(Enum):
    """A/B test status."""
    PLANNED = "planned"
    RUNNING = "running"
    COMPLETED = "completed"
    STOPPED = "stopped"
    FAILED = "failed"


class TestType(Enum):
    """Types of A/B tests."""
    MODEL_COMPARISON = "model_comparison"
    FEATURE_COMPARISON = "feature_comparison"
    HYPERPARAMETER_COMPARISON = "hyperparameter_comparison"
    STRATEGY_COMPARISON = "strategy_comparison"


class StatisticalTest(Enum):
    """Statistical tests for significance."""
    T_TEST = "t_test"
    MANN_WHITNEY = "mann_whitney"
    CHI_SQUARE = "chi_square"
    KOLMOGOROV_SMIRNOV = "kolmogorov_smirnov"
    BOOTSTRAP = "bootstrap"


@dataclass
class TestGroup:
    """A/B test group configuration."""
    name: str
    model_name: str
    model_version: str
    traffic_split: float  # 0.0 to 1.0
    description: str
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ABTest:
    """A/B test configuration and results."""
    test_id: str
    name: str
    test_type: TestType
    status: TestStatus
    groups: List[TestGroup]
    start_time: datetime
    end_time: Optional[datetime]
    duration_days: int
    sample_size: int
    metrics: List[str]
    results: Dict[str, Any]
    statistical_tests: Dict[str, Any]
    winner: Optional[str]
    confidence_level: float
    min_sample_size: int
    created_at: datetime
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['test_type'] = self.test_type.value
        result['status'] = self.status.value
        result['start_time'] = self.start_time.isoformat()
        if self.end_time:
            result['end_time'] = self.end_time.isoformat()
        result['created_at'] = self.created_at.isoformat()
        result['groups'] = [group.to_dict() for group in self.groups]
        return result


class ABTestingFramework(LoggerMixin):
    """A/B testing framework for model comparison."""
    
    def __init__(self):
        self.metrics = get_metrics()
        self.cache = get_cache()
        self.mlflow_manager = get_mlflow_manager()
        self.tests = {}  # test_id -> ABTest
        self.active_tests = {}  # test_id -> ABTest
        self.test_results = {}  # test_id -> results
    
    def create_test(self, name: str, test_type: TestType, groups: List[TestGroup],
                   duration_days: int = 30, metrics: List[str] = None,
                   confidence_level: float = 0.95, min_sample_size: int = 1000) -> str:
        """Create a new A/B test."""
        try:
            import uuid
            
            test_id = str(uuid.uuid4())
            
            # Validate traffic splits
            total_split = sum(group.traffic_split for group in groups)
            if abs(total_split - 1.0) > 0.001:
                raise ValueError(f"Traffic splits must sum to 1.0, got {total_split}")
            
            # Validate models exist
            for group in groups:
                try:
                    self.mlflow_manager.get_model_metadata(group.model_name, group.model_version)
                except Exception:
                    raise ValueError(f"Model {group.model_name} version {group.model_version} not found")
            
            # Create test
            test = ABTest(
                test_id=test_id,
                name=name,
                test_type=test_type,
                status=TestStatus.PLANNED,
                groups=groups,
                start_time=datetime.utcnow(),
                end_time=None,
                duration_days=duration_days,
                sample_size=0,
                metrics=metrics or ['accuracy', 'precision', 'recall', 'f1_score'],
                results={},
                statistical_tests={},
                winner=None,
                confidence_level=confidence_level,
                min_sample_size=min_sample_size,
                created_at=datetime.utcnow(),
                metadata={}
            )
            
            self.tests[test_id] = test
            
            self.logger.info(f"Created A/B test: {name} (ID: {test_id})")
            
            # Record metrics
            self.metrics.record_trading_signal(
                signal_type="ab_test_created",
                asset_symbol=test_id
            )
            
            return test_id
            
        except Exception as e:
            self.logger.error(f"Error creating A/B test: {e}")
            raise
    
    def start_test(self, test_id: str) -> bool:
        """Start an A/B test."""
        try:
            if test_id not in self.tests:
                raise ValueError(f"Test {test_id} not found")
            
            test = self.tests[test_id]
            
            if test.status != TestStatus.PLANNED:
                raise ValueError(f"Test {test_id} is not in planned status")
            
            # Update test status
            test.status = TestStatus.RUNNING
            test.start_time = datetime.utcnow()
            test.end_time = test.start_time + timedelta(days=test.duration_days)
            
            # Move to active tests
            self.active_tests[test_id] = test
            
            self.logger.info(f"Started A/B test: {test.name} (ID: {test_id})")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error starting A/B test {test_id}: {e}")
            return False
    
    def stop_test(self, test_id: str, force: bool = False) -> bool:
        """Stop an A/B test."""
        try:
            if test_id not in self.active_tests:
                raise ValueError(f"Test {test_id} is not active")
            
            test = self.active_tests[test_id]
            
            if not force and test.status != TestStatus.RUNNING:
                raise ValueError(f"Test {test_id} is not running")
            
            # Update test status
            test.status = TestStatus.COMPLETED if not force else TestStatus.STOPPED
            test.end_time = datetime.utcnow()
            
            # Move from active to completed
            self.active_tests.pop(test_id, None)
            
            self.logger.info(f"Stopped A/B test: {test.name} (ID: {test_id})")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error stopping A/B test {test_id}: {e}")
            return False
    
    def add_test_result(self, test_id: str, group_name: str, prediction_data: List[Dict[str, Any]]) -> bool:
        """Add test results for a specific group."""
        try:
            if test_id not in self.active_tests:
                raise ValueError(f"Test {test_id} is not active")
            
            test = self.active_tests[test_id]
            
            # Find group
            group = next((g for g in test.groups if g.name == group_name), None)
            if not group:
                raise ValueError(f"Group {group_name} not found in test {test_id}")
            
            # Initialize results for group if needed
            if group_name not in test.results:
                test.results[group_name] = {
                    "predictions": [],
                    "metrics": {},
                    "sample_size": 0
                }
            
            # Add predictions
            test.results[group_name]["predictions"].extend(prediction_data)
            test.results[group_name]["sample_size"] = len(test.results[group_name]["predictions"])
            
            # Update total sample size
            test.sample_size = sum(result["sample_size"] for result in test.results.values())
            
            # Calculate metrics for this group
            self._calculate_group_metrics(test, group_name)
            
            self.logger.debug(f"Added {len(prediction_data)} results to group {group_name} in test {test_id}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error adding test results: {e}")
            return False
    
    def _calculate_group_metrics(self, test: ABTest, group_name: str):
        """Calculate metrics for a test group."""
        try:
            group_results = test.results[group_name]
            predictions = group_results["predictions"]
            
            if not predictions:
                return
            
            # Convert to DataFrame for easier analysis
            df = pd.DataFrame(predictions)
            
            # Calculate metrics
            metrics = {}
            
            for metric in test.metrics:
                if metric == 'accuracy':
                    if 'actual' in df.columns and 'predicted' in df.columns:
                        metrics[metric] = (df['actual'] == df['predicted']).mean()
                elif metric == 'precision':
                    if 'actual' in df.columns and 'predicted' in df.columns:
                        metrics[metric] = precision_score(df['actual'], df['predicted'], average='weighted')
                elif metric == 'recall':
                    if 'actual' in df.columns and 'predicted' in df.columns:
                        metrics[metric] = recall_score(df['actual'], df['predicted'], average='weighted')
                elif metric == 'f1_score':
                    if 'actual' in df.columns and 'predicted' in df.columns:
                        metrics[metric] = f1_score(df['actual'], df['predicted'], average='weighted')
                elif metric == 'mse':
                    if 'actual' in df.columns and 'predicted' in df.columns:
                        metrics[metric] = mean_squared_error(df['actual'], df['predicted'])
                elif metric == 'mae':
                    if 'actual' in df.columns and 'predicted' in df.columns:
                        metrics[metric] = mean_absolute_error(df['actual'], df['predicted'])
                elif metric == 'mean_return':
                    if 'return' in df.columns:
                        metrics[metric] = df['return'].mean()
                elif metric == 'volatility':
                    if 'return' in df.columns:
                        metrics[metric] = df['return'].std()
                elif metric == 'sharpe_ratio':
                    if 'return' in df.columns:
                        mean_return = df['return'].mean()
                        volatility = df['return'].std()
                        metrics[metric] = mean_return / volatility if volatility > 0 else 0
            
            group_results["metrics"] = metrics
            
        except Exception as e:
            self.logger.error(f"Error calculating group metrics: {e}")
    
    def run_statistical_tests(self, test_id: str) -> Dict[str, Any]:
        """Run statistical tests to determine significance."""
        try:
            if test_id not in self.active_tests:
                raise ValueError(f"Test {test_id} is not active")
            
            test = self.active_tests[test_id]
            
            if len(test.results) < 2:
                raise ValueError("Need at least 2 groups for statistical testing")
            
            statistical_results = {}
            
            # Get group names
            group_names = list(test.results.keys())
            
            if len(group_names) == 2:
                # Two-group comparison
                group1, group2 = group_names
                
                for metric in test.metrics:
                    if metric in test.results[group1]["metrics"] and metric in test.results[group2]["metrics"]:
                        # Get metric values for each prediction
                        values1 = [pred.get(metric) for pred in test.results[group1]["predictions"] if metric in pred]
                        values2 = [pred.get(metric) for pred in test.results[group2]["predictions"] if metric in pred]
                        
                        if values1 and values2:
                            # Run statistical tests
                            test_results = self._run_two_sample_test(values1, values2, test.confidence_level)
                            statistical_results[metric] = test_results
            else:
                # Multi-group comparison
                for metric in test.metrics:
                    group_values = {}
                    for group_name in group_names:
                        values = [pred.get(metric) for pred in test.results[group_name]["predictions"] if metric in pred]
                        if values:
                            group_values[group_name] = values
                    
                    if len(group_values) >= 2:
                        test_results = self._run_anova_test(group_values, test.confidence_level)
                        statistical_results[metric] = test_results
            
            test.statistical_tests = statistical_results
            
            # Determine winner
            test.winner = self._determine_winner(test, statistical_results)
            
            return statistical_results
            
        except Exception as e:
            self.logger.error(f"Error running statistical tests: {e}")
            return {}
    
    def _run_two_sample_test(self, values1: List[float], values2: List[float], confidence_level: float) -> Dict[str, Any]:
        """Run two-sample statistical tests."""
        try:
            results = {}
            
            # Convert to numpy arrays
            arr1 = np.array(values1)
            arr2 = np.array(values2)
            
            # T-test
            t_stat, t_pvalue = stats.ttest_ind(arr1, arr2)
            results['t_test'] = {
                'statistic': t_stat,
                'p_value': t_pvalue,
                'significant': t_pvalue < (1 - confidence_level),
                'confidence_level': confidence_level
            }
            
            # Mann-Whitney U test
            u_stat, u_pvalue = stats.mannwhitneyu(arr1, arr2, alternative='two-sided')
            results['mann_whitney'] = {
                'statistic': u_stat,
                'p_value': u_pvalue,
                'significant': u_pvalue < (1 - confidence_level),
                'confidence_level': confidence_level
            }
            
            # Kolmogorov-Smirnov test
            ks_stat, ks_pvalue = stats.ks_2samp(arr1, arr2)
            results['kolmogorov_smirnov'] = {
                'statistic': ks_stat,
                'p_value': ks_pvalue,
                'significant': ks_pvalue < (1 - confidence_level),
                'confidence_level': confidence_level
            }
            
            # Effect size (Cohen's d)
            pooled_std = np.sqrt(((len(arr1) - 1) * np.var(arr1, ddof=1) + 
                                 (len(arr2) - 1) * np.var(arr2, ddof=1)) / 
                                (len(arr1) + len(arr2) - 2))
            cohens_d = (np.mean(arr1) - np.mean(arr2)) / pooled_std if pooled_std > 0 else 0
            results['effect_size'] = {
                'cohens_d': cohens_d,
                'interpretation': self._interpret_effect_size(cohens_d)
            }
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error in two-sample test: {e}")
            return {}
    
    def _run_anova_test(self, group_values: Dict[str, List[float]], confidence_level: float) -> Dict[str, Any]:
        """Run ANOVA test for multiple groups."""
        try:
            results = {}
            
            # Prepare data for ANOVA
            groups = []
            group_labels = []
            
            for group_name, values in group_values.items():
                groups.append(np.array(values))
                group_labels.extend([group_name] * len(values))
            
            # Flatten all values
            all_values = np.concatenate(groups)
            
            # Create group indicators
            group_indicators = []
            for i, group in enumerate(groups):
                group_indicators.extend([i] * len(group))
            
            # One-way ANOVA
            f_stat, f_pvalue = stats.f_oneway(*groups)
            results['anova'] = {
                'statistic': f_stat,
                'p_value': f_pvalue,
                'significant': f_pvalue < (1 - confidence_level),
                'confidence_level': confidence_level
            }
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error in ANOVA test: {e}")
            return {}
    
    def _interpret_effect_size(self, cohens_d: float) -> str:
        """Interpret Cohen's d effect size."""
        abs_d = abs(cohens_d)
        
        if abs_d < 0.2:
            return "negligible"
        elif abs_d < 0.5:
            return "small"
        elif abs_d < 0.8:
            return "medium"
        else:
            return "large"
    
    def _determine_winner(self, test: ABTest, statistical_results: Dict[str, Any]) -> Optional[str]:
        """Determine the winning group based on statistical tests."""
        try:
            if not statistical_results:
                return None
            
            # For each metric, check if there's a significant difference
            significant_metrics = {}
            
            for metric, results in statistical_results.items():
                # Check if any test shows significance
                is_significant = any(
                    test_result.get('significant', False) 
                    for test_name, test_result in results.items() 
                    if test_name in ['t_test', 'mann_whitney', 'anova']
                )
                
                if is_significant:
                    significant_metrics[metric] = True
            
            # If no significant differences, no winner
            if not significant_metrics:
                return None
            
            # Determine winner based on primary metric (first in list)
            primary_metric = test.metrics[0]
            
            if primary_metric in significant_metrics:
                # Find group with best performance for primary metric
                best_group = None
                best_value = None
                
                for group_name, group_results in test.results.items():
                    metric_value = group_results["metrics"].get(primary_metric)
                    
                    if metric_value is not None:
                        if best_value is None or metric_value > best_value:
                            best_value = metric_value
                            best_group = group_name
                
                return best_group
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error determining winner: {e}")
            return None
    
    def get_test_results(self, test_id: str) -> Dict[str, Any]:
        """Get comprehensive test results."""
        try:
            if test_id not in self.tests:
                raise ValueError(f"Test {test_id} not found")
            
            test = self.tests[test_id]
            
            results = {
                "test_info": test.to_dict(),
                "summary": self._generate_test_summary(test),
                "visualizations": self._create_test_visualizations(test)
            }
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error getting test results: {e}")
            return {}
    
    def _generate_test_summary(self, test: ABTest) -> Dict[str, Any]:
        """Generate test summary statistics."""
        try:
            summary = {
                "test_id": test.test_id,
                "name": test.name,
                "status": test.status.value,
                "duration_days": test.duration_days,
                "sample_size": test.sample_size,
                "groups_count": len(test.groups),
                "metrics_count": len(test.metrics),
                "has_winner": test.winner is not None,
                "winner": test.winner,
                "statistical_significance": bool(test.statistical_tests),
                "confidence_level": test.confidence_level
            }
            
            # Add group performance summary
            if test.results:
                summary["group_performance"] = {}
                for group_name, group_results in test.results.items():
                    summary["group_performance"][group_name] = {
                        "sample_size": group_results["sample_size"],
                        "metrics": group_results["metrics"]
                    }
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error generating test summary: {e}")
            return {}
    
    def _create_test_visualizations(self, test: ABTest) -> Dict[str, str]:
        """Create visualizations for test results."""
        try:
            visualizations = {}
            
            if not test.results:
                return visualizations
            
            # Performance comparison chart
            fig = go.Figure()
            
            for group_name, group_results in test.results.items():
                metrics = group_results["metrics"]
                
                if metrics:
                    fig.add_trace(go.Bar(
                        name=group_name,
                        x=list(metrics.keys()),
                        y=list(metrics.values()),
                        text=[f"{v:.4f}" for v in metrics.values()],
                        textposition='auto'
                    ))
            
            fig.update_layout(
                title=f"Performance Comparison - {test.name}",
                xaxis_title="Metrics",
                yaxis_title="Value",
                barmode='group'
            )
            
            visualizations["performance_comparison"] = fig.to_html(include_plotlyjs='cdn')
            
            # Sample size comparison
            sample_sizes = [result["sample_size"] for result in test.results.values()]
            group_names = list(test.results.keys())
            
            fig2 = go.Figure(data=[go.Pie(
                labels=group_names,
                values=sample_sizes,
                title="Sample Size Distribution"
            )])
            
            visualizations["sample_distribution"] = fig2.to_html(include_plotlyjs='cdn')
            
            return visualizations
            
        except Exception as e:
            self.logger.error(f"Error creating visualizations: {e}")
            return {}
    
    def list_tests(self, status: TestStatus = None) -> List[Dict[str, Any]]:
        """List all tests, optionally filtered by status."""
        try:
            tests = []
            
            for test in self.tests.values():
                if status is None or test.status == status:
                    tests.append({
                        "test_id": test.test_id,
                        "name": test.name,
                        "test_type": test.test_type.value,
                        "status": test.status.value,
                        "start_time": test.start_time.isoformat(),
                        "end_time": test.end_time.isoformat() if test.end_time else None,
                        "sample_size": test.sample_size,
                        "groups": [group.name for group in test.groups],
                        "winner": test.winner
                    })
            
            return tests
            
        except Exception as e:
            self.logger.error(f"Error listing tests: {e}")
            return []
    
    def get_active_tests(self) -> List[Dict[str, Any]]:
        """Get all currently active tests."""
        return self.list_tests(TestStatus.RUNNING)


# Global A/B testing framework instance
ab_testing_framework = ABTestingFramework()


def get_ab_testing_framework() -> ABTestingFramework:
    """Get A/B testing framework instance."""
    return ab_testing_framework


# Utility functions
def create_model_comparison_test(test_name: str, model_a_name: str, model_a_version: str,
                                model_b_name: str, model_b_version: str,
                                traffic_split: float = 0.5, duration_days: int = 30) -> str:
    """Create a simple model comparison A/B test."""
    
    groups = [
        TestGroup(
            name="model_a",
            model_name=model_a_name,
            model_version=model_a_version,
            traffic_split=traffic_split,
            description="Model A (control)",
            metadata={}
        ),
        TestGroup(
            name="model_b",
            model_name=model_b_name,
            model_version=model_b_version,
            traffic_split=1.0 - traffic_split,
            description="Model B (variant)",
            metadata={}
        )
    ]
    
    return ab_testing_framework.create_test(
        name=test_name,
        test_type=TestType.MODEL_COMPARISON,
        groups=groups,
        duration_days=duration_days
    )


def add_prediction_results(test_id: str, group_name: str, predictions: List[Dict[str, Any]]) -> bool:
    """Add prediction results to an A/B test."""
    return ab_testing_framework.add_test_result(test_id, group_name, predictions)


def complete_test(test_id: str) -> Dict[str, Any]:
    """Complete an A/B test and get results."""
    try:
        # Run statistical tests
        ab_testing_framework.run_statistical_tests(test_id)
        
        # Stop the test
        ab_testing_framework.stop_test(test_id)
        
        # Get results
        return ab_testing_framework.get_test_results(test_id)
        
    except Exception as e:
        logger.error(f"Error completing test {test_id}: {e}")
        return {}


# Decorators for automatic A/B testing
def ab_test_model(test_name: str, comparison_model: str, traffic_split: float = 0.1):
    """Decorator for automatic A/B testing of models."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # This would integrate with the prediction pipeline
            # For now, just log the intent
            logger.info(f"A/B test requested: {test_name} vs {comparison_model}")
            return func(*args, **kwargs)
        return wrapper
    return decorator
