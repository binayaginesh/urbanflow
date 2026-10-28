"""UrbanFlow Data & Network Modeling -- Module 1 (Alent Varkey).
Decision Intelligence layer added in Stage A (Mehrin Fathima).
"""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("urbanflow-data")
except PackageNotFoundError:
    __version__ = "0.1.0-dev"

from .config import load_config, get_config          # noqa: F401
from .network_bundle import NetworkBundle, load_network  # noqa: F401
from .decision_layer import (                        # noqa: F401
    ScenarioMetrics,
    score_scenario,
    verdict,
    explain,
    topsis_rank,
    monte_carlo_confidence,
)
from .optimizer import (                             # noqa: F401
    InterventionLibrary,
    SuggestedIntervention,
    suggest_top3,
)
from .ml_components import (                         # noqa: F401
    CongestionTrendPredictor,
    AnomalyDetector,
)
