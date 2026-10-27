"""
tests/test_ml_components.py
Stage A – A3d: CongestionTrendPredictor and AnomalyDetector tests.
"""
from __future__ import annotations
import pytest
import pandas as pd
import numpy as np

from urbanflow_data.simulation_engine import SimResult
from urbanflow_data.ml_components import (
    CongestionTrendPredictor,
    AnomalyDetector,
)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _make_edge_speeds_df(n_rows: int = 20, seed: int = 0) -> pd.DataFrame:
    """Synthetic edge_speeds_by_slot DataFrame for training the predictor."""
    rng = np.random.default_rng(seed)
    slots    = ["night_offpeak", "morning_peak", "midday", "evening_peak"]
    highways = ["primary", "secondary", "tertiary", "residential"]
    rows = []
    for i in range(n_rows):
        slot = slots[i % len(slots)]
        hw   = highways[i % len(highways)]
        # Congestion varies by slot (morning/evening high, night low)
        base = {"night_offpeak": 1.1, "morning_peak": 2.5, "midday": 1.6, "evening_peak": 2.8}[slot]
        cong = base + rng.normal(0, 0.15)
        rows.append({
            "edge_id":          i,
            "time_slot":        slot,
            "speed_kmh":        30 / max(cong, 0.5),
            "congestion_ratio": max(1.0, cong),
            "source":           "synthetic",
            "highway":          hw,
        })
    return pd.DataFrame(rows)


def _make_sim_result(
    cong: float = 1.5,
    speed: float = 25.0,
    bus_delay: float = 60.0,
    emissions: float = 1.2,
    name: str = "Test",
) -> SimResult:
    return SimResult(
        scenario_name=name,
        time_slot="morning_peak",
        total_travel_time_s=3000.0,
        mean_congestion_ratio=cong,
        mean_speed_kmh=speed,
        bottleneck_edges=[],
        bus_delay_s=bus_delay,
        emissions_index=emissions,
        edge_speeds={},
        edge_volumes={},
    )


# ── CongestionTrendPredictor tests ────────────────────────────────────────────
class TestCongestionTrendPredictor:

    def test_model_unavailable_below_min_samples(self):
        predictor = CongestionTrendPredictor()
        df = _make_edge_speeds_df(n_rows=4)  # < 8
        predictor.fit(df)
        assert not predictor.model_available

    def test_model_available_with_enough_samples(self):
        predictor = CongestionTrendPredictor()
        df = _make_edge_speeds_df(n_rows=16)
        predictor.fit(df)
        assert predictor.model_available

    def test_predict_returns_float(self):
        predictor = CongestionTrendPredictor()
        df = _make_edge_speeds_df(n_rows=20)
        predictor.fit(df)
        result = predictor.predict("morning_peak", "primary")
        assert isinstance(result, float)

    def test_predict_at_least_one(self):
        """Predicted congestion ratio must be ≥ 1.0 by definition."""
        predictor = CongestionTrendPredictor()
        df = _make_edge_speeds_df(n_rows=20)
        predictor.fit(df)
        for slot in ["night_offpeak", "morning_peak", "midday", "evening_peak"]:
            assert predictor.predict(slot, "primary") >= 1.0

    def test_predict_higher_congestion_at_peak(self):
        """Morning peak congestion should exceed night off-peak."""
        predictor = CongestionTrendPredictor()
        df = _make_edge_speeds_df(n_rows=40)
        predictor.fit(df)
        peak  = predictor.predict("morning_peak",  "primary")
        night = predictor.predict("night_offpeak", "primary")
        assert peak > night, f"Morning peak ({peak:.2f}) should exceed night ({night:.2f})"

    def test_predict_raises_when_not_available(self):
        predictor = CongestionTrendPredictor()
        df = _make_edge_speeds_df(n_rows=3)  # < 8
        predictor.fit(df)
        with pytest.raises(RuntimeError, match="model not available"):
            predictor.predict("morning_peak", "primary")

    def test_fit_without_highway_column(self):
        """Predictor should work on slot-only features if highway column absent."""
        predictor = CongestionTrendPredictor()
        df = _make_edge_speeds_df(n_rows=20)[["edge_id", "time_slot", "congestion_ratio"]]
        predictor.fit(df)
        assert predictor.model_available
        result = predictor.predict("evening_peak")
        assert result >= 1.0

    def test_fit_missing_target_column_sets_unavailable(self):
        predictor = CongestionTrendPredictor()
        df = pd.DataFrame({"time_slot": ["morning_peak"] * 10})
        predictor.fit(df)
        assert not predictor.model_available

    def test_repr_contains_info(self):
        predictor = CongestionTrendPredictor()
        s = repr(predictor)
        assert "CongestionTrendPredictor" in s
        assert "available" in s


# ── AnomalyDetector tests ─────────────────────────────────────────────────────
class TestAnomalyDetector:

    def _normal_results(self, n: int = 20, seed: int = 0) -> list[SimResult]:
        rng = np.random.default_rng(seed)
        return [
            _make_sim_result(
                cong   = float(rng.normal(1.8, 0.1)),
                speed  = float(rng.normal(22.0, 1.5)),
                bus_delay = float(rng.normal(90, 10)),
                emissions = float(rng.normal(1.3, 0.05)),
                name   = f"Normal_{i}",
            )
            for i in range(n)
        ]

    def test_model_unavailable_below_min_samples(self):
        detector = AnomalyDetector()
        detector.fit(self._normal_results(n=4))
        assert not detector.model_available

    def test_model_available_with_enough_samples(self):
        detector = AnomalyDetector()
        detector.fit(self._normal_results(n=20))
        assert detector.model_available

    def test_score_returns_float(self):
        detector = AnomalyDetector()
        detector.fit(self._normal_results(n=20))
        s = detector.score(_make_sim_result())
        assert isinstance(s, float)

    def test_normal_result_is_not_anomaly(self):
        """A result drawn from the training distribution should not be flagged."""
        normals  = self._normal_results(n=30, seed=1)
        detector = AnomalyDetector(contamination=0.05, random_state=42)
        detector.fit(normals)
        # A typical result (close to training mean)
        typical = _make_sim_result(cong=1.8, speed=22.0, bus_delay=90.0, emissions=1.3)
        assert not detector.is_anomaly(typical), "Typical result should not be flagged"

    def test_extreme_outlier_is_anomaly(self):
        """A result with extreme values should be flagged as anomalous."""
        normals  = self._normal_results(n=30, seed=2)
        detector = AnomalyDetector(contamination=0.1, random_state=42)
        detector.fit(normals)
        # Very extreme values far from training distribution
        extreme = _make_sim_result(cong=99.0, speed=0.1, bus_delay=9999.0, emissions=99.0)
        assert detector.is_anomaly(extreme), "Extreme outlier must be flagged as anomaly"

    def test_score_raises_when_not_available(self):
        detector = AnomalyDetector()
        detector.fit(self._normal_results(n=3))  # < 8
        with pytest.raises(RuntimeError, match="model not available"):
            detector.score(_make_sim_result())

    def test_is_anomaly_raises_when_not_available(self):
        detector = AnomalyDetector()
        detector.fit([])
        with pytest.raises(RuntimeError, match="model not available"):
            detector.is_anomaly(_make_sim_result())

    def test_fit_empty_list(self):
        detector = AnomalyDetector()
        detector.fit([])
        assert not detector.model_available

    def test_repr_contains_info(self):
        detector = AnomalyDetector()
        s = repr(detector)
        assert "AnomalyDetector" in s
        assert "available" in s
