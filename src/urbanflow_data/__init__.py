"""UrbanFlow Data & Network Modeling -- Module 1 (Alent Varkey)."""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("urbanflow-data")
except PackageNotFoundError:
    __version__ = "0.1.0-dev"

from .config import load_config, get_config          # noqa: F401
from .network_bundle import NetworkBundle, load_network  # noqa: F401
