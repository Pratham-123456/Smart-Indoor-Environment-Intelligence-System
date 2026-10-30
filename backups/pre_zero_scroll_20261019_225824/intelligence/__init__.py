"""SIEIS Intelligence Package.

Contains scoring algorithms, rolling baselines, trend detection,
anomaly tracking, short-horizon forecasting, and rule-based decision support.
"""

from .anomaly import AnomalyDetector
from .baseline import MQ135BaselineManager
from .decision import DecisionEngine
from .forecasting import TrendForecaster
from .scoring import EnvironmentalScorer
from .trends import TrendAnalyzer

__all__ = [
    "EnvironmentalScorer",
    "MQ135BaselineManager",
    "TrendAnalyzer",
    "AnomalyDetector",
    "TrendForecaster",
    "DecisionEngine",
]
