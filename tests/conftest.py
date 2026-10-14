"""tests/conftest.py – shared fixtures for pytest."""
from __future__ import annotations
import pytest
from pathlib import Path

# Project root is three levels up from this file (tests/ -> project root)
PROJECT_ROOT = Path(__file__).parent.parent.resolve()

@pytest.fixture
def project_root() -> Path:
    return PROJECT_ROOT

@pytest.fixture
def cfg(project_root):
    from urbanflow_data.config import load_config
    return load_config(root=project_root)
