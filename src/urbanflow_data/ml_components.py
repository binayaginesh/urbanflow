"""
ml_components.py – Stage A: Machine-Learning Support Components
===============================================================

Provides two lightweight ML models that support the decision layer:

1. CongestionTrendPredictor
   Fits a Ridge regression on historical slot × road-class congestion
   ratios and predicts congestion for a given (time_slot, highway_class).

2. AnomalyDetector
   Fits an IsolationForest on SimResult metric vectors to flag scenarios
   that are statistical outliers.

Design rules (TEAM_PLAN.md):
  - No LLM computes or changes any number.
  - sklearn / numpy handle all arithmetic.
  - Both models guard against insufficient data (< 8 samples) and expose
    a `model_available` property so callers can degrade gracefully.
  - No data is invented; the predictor only trains on provided DataFrames.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from urbanflow_data.simulation_engine import SimResult

# Minimum samples needed before we attempt to train a model.
_MIN_SAMPLES = 8


# ── CongestionTrendPredictor ───────────────────────────────────────────────────
class CongestionTrendPredictor:
    """
    Predicts congestion ratio for a (time_slot, highway_class) pair.

    Input DataFrame columns expected in `fit()`:
        edge_id, time_slot, speed_kmh, congestion_ratio, source, highway (optional)

    If `highway` is absent the predictor falls back to slot-only features.

    Model: sklearn.linear_model.Ridge — simple, explainable, low-variance.
    """

    def __init__(self, alpha: float = 1.0) -> None:
        self._alpha = alpha
        self._model = None
        self._slots: list[str] = []
        self._classes: list[str] = []
        self._model_available = False
        self._n_samples = 0

    @property
    def model_available(self) -> bool:
        return self._model_available

    def fit(self, df: pd.DataFrame) -> "CongestionTrendPredictor":
        """
        Train the predictor on historical edge speed / congestion data.

        Parameters
        ----------
        df : DataFrame with columns: time_slot, congestion_ratio,
             and optionally highway.

        Returns
        -------
        self (for chaining)
        """
        from sklearn.linear_model import Ridge
        from sklearn.preprocessing import OneHotEncoder
        from sklearn.pipeline import Pipeline
        from sklearn.compose import ColumnTransformer

        if "congestion_ratio" not in df.columns or "time_slot" not in df.columns:
            self._model_available = False
            return self

        has_hw = "highway" in df.columns
        df = df.dropna(subset=["congestion_ratio", "time_slot"])

        if has_hw:
            df = df.dropna(subset=["highway"])
            features = df[["time_slot", "highway"]]
        else:
            features = df[["time_slot"]]

        target = df["congestion_ratio"].values

        if len(target) < _MIN_SAMPLES:
            self._model_available = False
            self._n_samples = len(target)
            return self

        cat_features = features.columns.tolist()
        preprocessor = ColumnTransformer([
            ("ohe", OneHotEncoder(handle_unknown="ignore", sparse_output=False), cat_features),
        ])
        pipeline = Pipeline([
            ("prep", preprocessor),
            ("ridge", Ridge(alpha=self._alpha)),
        ])
        pipeline.fit(features, target)

        self._model = pipeline
        self._slots = df["time_slot"].unique().tolist()
        self._classes = df["highway"].unique().tolist() if has_hw else []
        self._model_available = True
        self._n_samples = len(target)
        return self

    def predict(self, time_slot: str, highway_class: str | None = None) -> float:
        """
        Predict congestion ratio for a given slot and road class.

        Returns
        -------
        float (predicted congestion ratio), or raises RuntimeError if model
        is not available.
        """
        if not self._model_available or self._model is None:
            raise RuntimeError(
                f"CongestionTrendPredictor: model not available "
                f"(trained on {self._n_samples} samples, need ≥ {_MIN_SAMPLES})."
            )
        has_hw = bool(self._classes)
        if has_hw:
            row = pd.DataFrame([{"time_slot": time_slot, "highway": highway_class or "primary"}])
        else:
            row = pd.DataFrame([{"time_slot": time_slot}])
        pred = self._model.predict(row)[0]
        return float(max(1.0, pred))   # congestion ratio ≥ 1.0 by definition

    def __repr__(self) -> str:
        return (
            f"CongestionTrendPredictor("
            f"available={self._model_available}, "
            f"n_samples={self._n_samples})"
        )


# ── AnomalyDetector ───────────────────────────────────────────────────────────
@dataclass
class _SimVector:
    """Internal struct for a four-metric feature vector from a SimResult."""
    mean_congestion_ratio: float
    mean_speed_kmh: float
    bus_delay_s: float
    emissions_index: float

    def to_array(self) -> np.ndarray:
        return np.array([
            self.mean_congestion_ratio,
            self.mean_speed_kmh,
            self.bus_delay_s,
            self.emissions_index,
        ])


class AnomalyDetector:
    """
    Detects anomalous simulation scenarios using Isolation Forest.

    A scenario is 'anomalous' if its metric vector (congestion, speed,
    bus_delay, emissions) lies far from the training distribution.

    Usage
    -----
    detector = AnomalyDetector()
    detector.fit(list_of_sim_results)   # at least 8
    score = detector.score(one_sim_result)   # float, lower = more anomalous
    flag  = detector.is_anomaly(one_sim_result)  # bool
    """

    def __init__(
        self,
        contamination: float = 0.1,
        n_estimators: int = 100,
        random_state: int = 42,
    ) -> None:
        self._contamination = contamination
        self._n_estimators = n_estimators
        self._random_state = random_state
        self._model = None
        self._model_available = False
        self._n_samples = 0

    @property
    def model_available(self) -> bool:
        return self._model_available

    def fit(self, results: list["SimResult"]) -> "AnomalyDetector":
        """
        Train the detector on a list of SimResult instances.

        Parameters
        ----------
        results : list of SimResult (from simulation_engine).
                  Training is skipped if len(results) < 8.

        Returns
        -------
        self
        """
        from sklearn.ensemble import IsolationForest

        self._n_samples = len(results)
        if self._n_samples < _MIN_SAMPLES:
            self._model_available = False
            return self

        X = np.array([
            _SimVector(
                r.mean_congestion_ratio,
                r.mean_speed_kmh,
                r.bus_delay_s,
                r.emissions_index,
            ).to_array()
            for r in results
        ])

        model = IsolationForest(
            n_estimators=self._n_estimators,
            contamination=self._contamination,
            random_state=self._random_state,
        )
        model.fit(X)
        self._model = model
        self._model_available = True
        return self

    def score(self, result: "SimResult") -> float:
        """
        Return the anomaly score for a single SimResult.

        sklearn IsolationForest convention:
          - Positive score → inlier (normal)
          - Negative score → outlier (anomaly)

        Raises RuntimeError if model is not available.
        """
        if not self._model_available or self._model is None:
            raise RuntimeError(
                f"AnomalyDetector: model not available "
                f"(trained on {self._n_samples} samples, need ≥ {_MIN_SAMPLES})."
            )
        x = _SimVector(
            result.mean_congestion_ratio,
            result.mean_speed_kmh,
            result.bus_delay_s,
            result.emissions_index,
        ).to_array().reshape(1, -1)
        return float(self._model.decision_function(x)[0])

    def is_anomaly(self, result: "SimResult") -> bool:
        """Return True if the result is flagged as an anomaly (score < 0)."""
        return self.score(result) < 0

    def __repr__(self) -> str:
        return (
            f"AnomalyDetector("
            f"available={self._model_available}, "
            f"n_samples={self._n_samples}, "
            f"contamination={self._contamination})"
        )
