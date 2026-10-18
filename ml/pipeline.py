"""Shared Estimation Pipeline classes for clean serialization and deserialization."""

from __future__ import annotations
from typing import Any
import numpy as np
import pandas as pd


class MedianBaselineEstimator:
    """Baseline calculator: predicts median of training actuals."""
    def __init__(self) -> None:
        self.median_value: float = 0.0

    def fit(self, X: Any, y: np.ndarray) -> MedianBaselineEstimator:
        self.median_value = float(np.median(y))
        return self

    def predict(self, X: Any) -> np.ndarray:
        n = len(X) if hasattr(X, "__len__") else 1
        return np.full(n, self.median_value)


class FullEstimationPipeline:
    """Encapsulates preprocessor and model estimator in one deployable unit."""
    def __init__(self, preprocessor: Any, estimator: Any, use_log_target: bool = True) -> None:
        self.preprocessor = preprocessor
        self.estimator = estimator
        self.use_log_target = use_log_target

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> FullEstimationPipeline:
        X_trans = self.preprocessor.fit_transform(X)
        if self.use_log_target:
            y_trans = np.log1p(np.maximum(y, 0.0))
            self.estimator.fit(X_trans, y_trans)
        else:
            self.estimator.fit(X_trans, y)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        X_trans = self.preprocessor.transform(X)
        raw_pred = self.estimator.predict(X_trans)
        if self.use_log_target:
            return np.maximum(np.expm1(raw_pred), 0.0)
        return np.maximum(raw_pred, 0.0)
